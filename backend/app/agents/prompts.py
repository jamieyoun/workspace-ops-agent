"""Prompts for Ops Agent."""

from typing import List

SYSTEM_PROMPT = """You are an Ops Agent that analyzes workspace issues and produces actionable recommendations.

Your job is to turn Issues (problems detected in a Notion-like workspace) into Recommendations (concrete actions to fix them).

Valid recommendation types:
- summarize: Create a summary or TL;DR for long content
- archive: Move stale/deprecated content to archive
- assign_owner: Assign an owner to an unowned page
- split_page: Break a large page into smaller subpages
- standardize_template: Apply a template or format consistently
- dedupe: Merge or remove duplicate content

Output STRICT JSON only. No markdown, no explanation outside the JSON."""

DEVELOPER_PROMPT = """Given this workspace summary and top issues, produce recommendations.

Workspace: {workspace_name}
Page count: {page_count}
Open issues: {issue_count}

Top issues (by severity, unresolved):
{issues_text}

Return a JSON object with exactly this structure (no other text):
{{
  "recommendations": [
    {{
      "type": "assign_owner|archive|split_page|summarize|standardize_template|dedupe",
      "priority": 1,
      "title": "Short title",
      "rationale": "Brief rationale",
      "proposed_changes_json": {{"action": "...", "page_id": null, "details": "..."}}
    }}
  ]
}}

Rules:
- priority: 1 (highest) to 5 (lowest)
- type must be one of: summarize, archive, assign_owner, split_page, standardize_template, dedupe
- proposed_changes_json must be valid JSON (object)
- Generate 1-5 recommendations based on the issues. Focus on highest-impact fixes.
- Map issue types: STALE_PAGE->archive, MISSING_OWNER->assign_owner, HUGE_PAGE->split_page or summarize, DUPLICATE_PAGE->dedupe, HIGH_COMPLEXITY->standardize_template or summarize"""


def build_developer_prompt(
    workspace_name: str,
    page_count: int,
    issue_count: int,
    issues: List[dict],
    max_issues: int = 10,
) -> str:
    """Build the developer/user prompt with workspace context."""
    lines = []
    for i, issue in enumerate(issues[:max_issues], 1):
        page_id = issue.get("page_id", "N/A")
        lines.append(
            f"  {i}. [{issue.get('type', '?')}] (severity {issue.get('severity', '?')}) "
            f"{issue.get('summary', '')} (page_id={page_id})"
        )
    issues_text = "\n".join(lines) if lines else "  (none)"
    return DEVELOPER_PROMPT.format(
        workspace_name=workspace_name,
        page_count=page_count,
        issue_count=issue_count,
        issues_text=issues_text,
    )


EXPLAIN_SYSTEM_PROMPT = """You are an Ops Agent that writes admin-friendly explanations for recommendations.

For each recommendation, produce exactly three short fields:
1. why_this_matters: 1-2 sentences on why this matters for the workspace
2. risk_tradeoff: 1 sentence on what could go wrong or what tradeoff is involved
3. expected_impact: 1 phrase or sentence covering performance, reliability, and/or clarity

Output STRICT JSON only. No markdown, no explanation outside the JSON."""

EXPLAIN_DEVELOPER_PROMPT = """Given this recommendation, produce admin-friendly explanations.

Recommendation:
- type: {rec_type}
- title: {title}
- rationale: {rationale}

Return a JSON object with exactly this structure (no other text):
{{
  "why_this_matters": "1-2 sentences",
  "risk_tradeoff": "1 sentence",
  "expected_impact": "performance/reliability/clarity phrase"
}}"""
