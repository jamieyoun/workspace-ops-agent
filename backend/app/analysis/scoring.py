"""Workspace health scoring."""

from dataclasses import dataclass
from typing import List

from app.analysis.heuristics import STALE_PAGE, MISSING_OWNER, HUGE_PAGE, DUPLICATE_PAGE, HIGH_COMPLEXITY


@dataclass
class Subscore:
    """Category subscore with explanation."""

    name: str
    score: float  # 0-100
    weight: float
    explanation: str


@dataclass
class WorkspaceScore:
    """Full workspace health score."""

    overall: float  # 0-100
    subscores: List[Subscore]
    issue_count: int
    open_issue_count: int


def _freshness_score(
    total_pages: int,
    stale_count: int,
    stale_issues: List[dict],
) -> tuple[float, str]:
    """Freshness subscore: penalize stale pages."""
    if total_pages == 0:
        return 100.0, "No pages to evaluate."
    ratio = 1.0 - (stale_count / total_pages)
    score = max(0, min(100, ratio * 100))
    if stale_count == 0:
        explanation = "All pages have been updated within the last 180 days."
    else:
        explanation = f"{stale_count} of {total_pages} pages are stale (not updated in 180+ days)."
    return score, explanation


def _ownership_score(total_pages: int, missing_owner_count: int) -> tuple[float, str]:
    """Ownership subscore: penalize pages without owners."""
    if total_pages == 0:
        return 100.0, "No pages to evaluate."
    ratio = 1.0 - (missing_owner_count / total_pages)
    score = max(0, min(100, ratio * 100))
    if missing_owner_count == 0:
        explanation = "All pages have assigned owners."
    else:
        explanation = f"{missing_owner_count} of {total_pages} pages lack an owner."
    return score, explanation


def _performance_risk_score(
    total_pages: int,
    huge_count: int,
    high_complexity_count: int,
) -> tuple[float, str]:
    """Performance risk subscore: penalize huge/complex pages."""
    if total_pages == 0:
        return 100.0, "No pages to evaluate."
    risk_count = huge_count + high_complexity_count
    ratio = 1.0 - (risk_count / total_pages)
    score = max(0, min(100, ratio * 100))
    if risk_count == 0:
        explanation = "No oversized or high-complexity pages detected."
    else:
        parts = []
        if huge_count:
            parts.append(f"{huge_count} oversized")
        if high_complexity_count:
            parts.append(f"{high_complexity_count} high-complexity")
        explanation = f"{', '.join(parts)} page(s) may impact performance."
    return score, explanation


def _duplication_score(total_pages: int, duplicate_count: int) -> tuple[float, str]:
    """Duplication subscore: penalize duplicate content."""
    if total_pages == 0:
        return 100.0, "No pages to evaluate."
    # Each duplicate "pair" affects 2 pages
    affected = min(duplicate_count * 2, total_pages)
    ratio = 1.0 - (affected / total_pages)
    score = max(0, min(100, ratio * 100))
    if duplicate_count == 0:
        explanation = "No duplicate content detected."
    else:
        explanation = f"{duplicate_count} duplicate pair(s) found."
    return score, explanation


def compute_workspace_score(
    total_pages: int,
    issues: List[dict],
) -> WorkspaceScore:
    """
    Compute workspace health score (0-100) with category subscores.
    issues: list of dicts with 'type', 'resolved_at' keys.
    """
    open_issues = [i for i in issues if i.get("resolved_at") is None]
    open_issue_count = len(open_issues)
    issue_count = len(issues)

    stale_count = sum(1 for i in open_issues if i.get("type") == STALE_PAGE)
    missing_owner_count = sum(1 for i in open_issues if i.get("type") == MISSING_OWNER)
    huge_count = sum(1 for i in open_issues if i.get("type") == HUGE_PAGE)
    high_complexity_count = sum(1 for i in open_issues if i.get("type") == HIGH_COMPLEXITY)
    duplicate_count = sum(1 for i in open_issues if i.get("type") == DUPLICATE_PAGE)

    freshness_score_val, freshness_expl = _freshness_score(total_pages, stale_count, open_issues)
    ownership_score_val, ownership_expl = _ownership_score(total_pages, missing_owner_count)
    perf_score_val, perf_expl = _performance_risk_score(total_pages, huge_count, high_complexity_count)
    dup_score_val, dup_expl = _duplication_score(total_pages, duplicate_count)

    subscores = [
        Subscore("freshness", freshness_score_val, 0.3, freshness_expl),
        Subscore("ownership", ownership_score_val, 0.25, ownership_expl),
        Subscore("performance_risk", perf_score_val, 0.25, perf_expl),
        Subscore("duplication", dup_score_val, 0.2, dup_expl),
    ]

    overall = sum(s.weight * s.score for s in subscores)
    overall = max(0, min(100, round(overall, 1)))

    return WorkspaceScore(
        overall=overall,
        subscores=subscores,
        issue_count=issue_count,
        open_issue_count=open_issue_count,
    )
