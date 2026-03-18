"""Tests for workspace scoring."""

import pytest

from app.analysis.scoring import compute_workspace_score, Subscore
from app.analysis.heuristics import STALE_PAGE, MISSING_OWNER, HUGE_PAGE, DUPLICATE_PAGE, HIGH_COMPLEXITY


def test_compute_workspace_score_perfect():
    """Perfect score when no issues."""
    score = compute_workspace_score(total_pages=10, issues=[])
    assert score.overall == 100.0
    assert score.open_issue_count == 0
    for s in score.subscores:
        assert s.score == 100.0


def test_compute_workspace_score_all_stale():
    """Low freshness when all pages stale."""
    issues = [{"type": STALE_PAGE, "resolved_at": None}] * 10
    score = compute_workspace_score(total_pages=10, issues=issues)
    assert score.subscores[0].name == "freshness"
    assert score.subscores[0].score == 0.0
    assert "stale" in score.subscores[0].explanation.lower()


def test_compute_workspace_score_missing_owners():
    """Ownership subscore penalizes missing owners."""
    issues = [
        {"type": MISSING_OWNER, "resolved_at": None},
        {"type": MISSING_OWNER, "resolved_at": None},
    ]
    score = compute_workspace_score(total_pages=10, issues=issues)
    ownership = next(s for s in score.subscores if s.name == "ownership")
    assert ownership.score < 100
    assert "2" in ownership.explanation


def test_compute_workspace_score_resolved_ignored():
    """Resolved issues do not affect score."""
    issues = [
        {"type": STALE_PAGE, "resolved_at": "2024-01-01"},
        {"type": MISSING_OWNER, "resolved_at": "2024-01-01"},
    ]
    score = compute_workspace_score(total_pages=10, issues=issues)
    assert score.open_issue_count == 0
    assert score.overall == 100.0


def test_compute_workspace_score_weighted_overall():
    """Overall score is weighted average of subscores."""
    issues = [
        {"type": STALE_PAGE, "resolved_at": None},
        {"type": STALE_PAGE, "resolved_at": None},
    ]
    score = compute_workspace_score(total_pages=10, issues=issues)
    # Freshness = 80 (2/10 stale), others = 100
    # overall = 0.3*80 + 0.25*100 + 0.25*100 + 0.2*100 = 24 + 25 + 25 + 20 = 94
    assert 90 <= score.overall <= 100
    assert score.issue_count == 2
    assert score.open_issue_count == 2
