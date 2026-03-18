"""Ops Agent: turns Issues into Recommendations."""

import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.analysis.heuristics import (
    STALE_PAGE,
    MISSING_OWNER,
    HUGE_PAGE,
    DUPLICATE_PAGE,
    HIGH_COMPLEXITY,
)
from app.agents.prompts import (
    SYSTEM_PROMPT,
    EXPLAIN_SYSTEM_PROMPT,
    EXPLAIN_DEVELOPER_PROMPT,
    build_developer_prompt,
)
from app.config import get_settings

logger = logging.getLogger(__name__)

VALID_TYPES = {"summarize", "archive", "assign_owner", "split_page", "standardize_template", "dedupe"}


@dataclass
class AgentRecommendation:
    """Recommendation produced by the agent."""

    type: str
    priority: int
    title: str
    rationale: str
    proposed_changes_json: dict
    page_id: Optional[int] = None


def _issue_to_heuristic_recommendation(issue: dict) -> Optional[AgentRecommendation]:
    """Map an issue to a deterministic heuristic recommendation."""
    itype = issue.get("type", "")
    page_id = issue.get("page_id")
    summary = issue.get("summary", "")

    if itype == STALE_PAGE:
        return AgentRecommendation(
            type="archive",
            priority=3,
            title="Archive stale page",
            rationale=f"Page has not been updated recently: {summary}",
            proposed_changes_json={"action": "archive", "page_id": page_id, "reason": "stale"},
            page_id=page_id,
        )
    if itype == MISSING_OWNER:
        return AgentRecommendation(
            type="assign_owner",
            priority=2,
            title="Assign owner to page",
            rationale=summary,
            proposed_changes_json={"action": "assign_owner", "page_id": page_id},
            page_id=page_id,
        )
    if itype == HUGE_PAGE:
        return AgentRecommendation(
            type="split_page",
            priority=4,
            title="Split oversized page",
            rationale=summary,
            proposed_changes_json={"action": "split_page", "page_id": page_id, "suggested_sections": []},
            page_id=page_id,
        )
    if itype == DUPLICATE_PAGE:
        return AgentRecommendation(
            type="dedupe",
            priority=2,
            title="Merge duplicate content",
            rationale=summary,
            proposed_changes_json={"action": "dedupe", "page_id": None, "details_json": issue.get("details_json")},
            page_id=None,
        )
    if itype == HIGH_COMPLEXITY:
        return AgentRecommendation(
            type="standardize_template",
            priority=3,
            title="Simplify page structure",
            rationale=summary,
            proposed_changes_json={"action": "standardize", "page_id": page_id},
            page_id=page_id,
        )
    return None


def _heuristic_recommendations(
    workspace_name: str,
    issues: List[dict],
    max_recommendations: int = 5,
) -> List[AgentRecommendation]:
    """Generate deterministic recommendations from issues (offline fallback)."""
    seen_keys = set()  # (type, page_id) to avoid duplicates
    recs = []
    sorted_issues = sorted(issues, key=lambda i: (i.get("severity", 5), i.get("page_id") or 0))
    for issue in sorted_issues:
        if len(recs) >= max_recommendations:
            break
        rec = _issue_to_heuristic_recommendation(issue)
        if rec:
            key = (rec.type, rec.page_id)
            if key not in seen_keys:
                seen_keys.add(key)
                recs.append(rec)
    return recs[:max_recommendations]


def _parse_and_validate_response(text: str) -> Optional[List[AgentRecommendation]]:
    """Parse JSON response and validate structure. Returns None if invalid."""
    try:
        # Strip markdown code blocks if present
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines)
        data = json.loads(stripped)
        if not isinstance(data, dict) or "recommendations" not in data:
            return None
        recs = []
        for r in data["recommendations"]:
            if not isinstance(r, dict):
                continue
            rtype = r.get("type", "")
            if rtype not in VALID_TYPES:
                continue
            priority = r.get("priority", 3)
            if not isinstance(priority, (int, float)):
                priority = 3
            priority = max(1, min(5, int(priority)))
            title = str(r.get("title", ""))[:500]
            rationale = str(r.get("rationale", ""))[:1000]
            changes = r.get("proposed_changes_json")
            if isinstance(changes, dict):
                changes = changes
            elif isinstance(changes, str):
                try:
                    changes = json.loads(changes)
                except json.JSONDecodeError:
                    changes = {"action": str(changes)[:200]}
            else:
                changes = {}
            page_id = r.get("page_id") if isinstance(r.get("page_id"), int) else None
            if title:
                recs.append(
                    AgentRecommendation(
                        type=rtype,
                        priority=priority,
                        title=title,
                        rationale=rationale,
                        proposed_changes_json=changes,
                        page_id=page_id,
                    )
                )
        return recs if recs else None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Failed to parse agent response: %s", e)
        return None


def _call_openai(
    workspace_name: str,
    page_count: int,
    issues: List[dict],
) -> Optional[List[AgentRecommendation]]:
    """Call OpenAI API. Returns None on failure."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed")
        return None

    api_key = get_settings().openai_api_key
    if not api_key or not api_key.strip():
        return None

    client = OpenAI(api_key=api_key)
    user_prompt = build_developer_prompt(
        workspace_name=workspace_name,
        page_count=page_count,
        issue_count=len(issues),
        issues=issues,
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if not content:
            return None
        return _parse_and_validate_response(content)
    except Exception as e:
        logger.warning("OpenAI API error: %s", e)
        return None


def generate_recommendations(
    workspace_name: str,
    page_count: int,
    issues: List[dict],
) -> Tuple[List[AgentRecommendation], str]:
    """
    Generate recommendations from issues.
    Uses OpenAI if API key is set; otherwise falls back to heuristic recommendations.
    Retries once on invalid JSON, then falls back to heuristics.
    Returns (recommendations, source) where source is "openai" or "heuristic".
    """
    recs = _call_openai(workspace_name, page_count, issues)
    if recs:
        return recs, "openai"
    recs = _call_openai(workspace_name, page_count, issues)
    if recs:
        return recs, "openai"
    return _heuristic_recommendations(workspace_name, issues), "heuristic"


# --- Explain recommendation ---

@dataclass
class RecommendationExplanation:
    """Admin-friendly explanation for a recommendation."""

    why_this_matters: str
    risk_tradeoff: str
    expected_impact: str


def _heuristic_explanation(rec_type: str, title: str, rationale: str) -> RecommendationExplanation:
    """Generate deterministic explanation by recommendation type (fallback)."""
    templates = {
        "archive": RecommendationExplanation(
            why_this_matters="Stale content can mislead readers and clutter search results. Archiving keeps the workspace focused on current, relevant information.",
            risk_tradeoff="Archived content may be harder to find; ensure important historical context is preserved elsewhere.",
            expected_impact="Clarity: cleaner workspace. Reliability: reduced confusion from outdated info.",
        ),
        "assign_owner": RecommendationExplanation(
            why_this_matters="Pages without owners lack accountability. Assigning owners ensures someone is responsible for keeping content accurate and up to date.",
            risk_tradeoff="The assigned owner may not have bandwidth; consider workload before assigning.",
            expected_impact="Reliability: clearer ownership. Clarity: easier to know who to contact.",
        ),
        "split_page": RecommendationExplanation(
            why_this_matters="Oversized pages are hard to navigate and maintain. Splitting improves readability and makes updates easier.",
            risk_tradeoff="Splitting may fragment related content; use clear cross-links between subpages.",
            expected_impact="Performance: faster loading. Clarity: better structure. Reliability: easier maintenance.",
        ),
        "summarize": RecommendationExplanation(
            why_this_matters="Long content benefits from a TL;DR so readers can quickly grasp key points before diving in.",
            risk_tradeoff="Summaries can become stale if the main content changes; keep them in sync.",
            expected_impact="Clarity: faster comprehension. Performance: quicker scanning.",
        ),
        "standardize_template": RecommendationExplanation(
            why_this_matters="Inconsistent structure makes content harder to find and maintain. Standardizing improves predictability.",
            risk_tradeoff="Templates may not fit every use case; allow flexibility where needed.",
            expected_impact="Clarity: consistent structure. Reliability: easier onboarding.",
        ),
        "dedupe": RecommendationExplanation(
            why_this_matters="Duplicate content causes confusion and maintenance burden. Merging or removing duplicates reduces redundancy.",
            risk_tradeoff="Ensure no unique information is lost when merging; review both versions first.",
            expected_impact="Clarity: single source of truth. Reliability: no conflicting information.",
        ),
    }
    return templates.get(rec_type, RecommendationExplanation(
        why_this_matters=rationale or f"This recommendation addresses: {title}.",
        risk_tradeoff="Review the proposed changes before applying.",
        expected_impact="Improves workspace organization and maintainability.",
    ))


def _parse_explain_response(text: str) -> Optional[RecommendationExplanation]:
    """Parse JSON explanation response."""
    try:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines)
        data = json.loads(stripped)
        if not isinstance(data, dict):
            return None
        why = str(data.get("why_this_matters", ""))[:1000]
        risk = str(data.get("risk_tradeoff", ""))[:500]
        impact = str(data.get("expected_impact", ""))[:500]
        if why and risk and impact:
            return RecommendationExplanation(why_this_matters=why, risk_tradeoff=risk, expected_impact=impact)
        return None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Failed to parse explain response: %s", e)
        return None


def _call_openai_explain(rec_type: str, title: str, rationale: str) -> Optional[RecommendationExplanation]:
    """Call OpenAI for explanation. Returns None on failure."""
    try:
        from openai import OpenAI
    except ImportError:
        return None
    api_key = get_settings().openai_api_key
    if not api_key or not api_key.strip():
        return None
    user_prompt = EXPLAIN_DEVELOPER_PROMPT.format(
        rec_type=rec_type,
        title=title,
        rationale=rationale or "",
    )
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if not content:
            return None
        return _parse_explain_response(content)
    except Exception as e:
        logger.warning("OpenAI explain error: %s", e)
        return None


def explain_recommendation(rec_type: str, title: str, rationale: str) -> Tuple[RecommendationExplanation, str]:
    """
    Generate admin-friendly explanation for a recommendation.
    Returns (explanation, source) where source is "openai" or "heuristic".
    Retries once on invalid JSON, then falls back to heuristics.
    """
    expl = _call_openai_explain(rec_type, title, rationale)
    if expl:
        return expl, "openai"
    expl = _call_openai_explain(rec_type, title, rationale)
    if expl:
        return expl, "openai"
    return _heuristic_explanation(rec_type, title, rationale), "heuristic"
