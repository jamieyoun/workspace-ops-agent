"""Tests for analysis heuristics."""

from datetime import datetime, timedelta

import pytest

from app.analysis.heuristics import (
    PageInfo,
    PageMetricData,
    compute_page_metrics,
    detect_issues,
    _jaccard_similarity,
    STALE_PAGE,
    MISSING_OWNER,
    HUGE_PAGE,
    DUPLICATE_PAGE,
    HIGH_COMPLEXITY,
)


def test_compute_page_metrics_word_count():
    """word_count splits on whitespace."""
    content = "one two three four five"
    m = compute_page_metrics(content)
    assert m.word_count == 5
    assert isinstance(m, PageMetricData)


def test_compute_page_metrics_embed_count():
    """embed_count detects images and iframes."""
    content = """
    ![alt](http://example.com/img.png)
    <img src="x.jpg" />
    <iframe src="http://embed.com"></iframe>
    """
    m = compute_page_metrics(content)
    assert m.embed_count == 3


def test_compute_page_metrics_database_refs():
    """database_refs_count detects /database/ and @database."""
    content = "See /database/123 and @database for more. Also /database/456."
    m = compute_page_metrics(content)
    assert m.database_refs_count == 3


def test_compute_page_metrics_empty():
    """Empty content returns zeros."""
    m = compute_page_metrics("")
    assert m.word_count == 0
    assert m.block_count == 0
    assert m.embed_count == 0
    assert m.database_refs_count == 0

    m2 = compute_page_metrics(None)
    assert m2.word_count == 0


def test_jaccard_similarity():
    """Jaccard similarity between token sets."""
    assert _jaccard_similarity("a b c", "a b c") == 1.0
    assert _jaccard_similarity("a b", "c d") == 0.0
    assert 0 < _jaccard_similarity("a b c", "a b d") < 1.0


def test_detect_issues_stale_page():
    """STALE_PAGE detected when last_updated > 180 days."""
    old = datetime.utcnow() - timedelta(days=200)
    pages = [
        PageInfo(
            id=1,
            workspace_id=1,
            title="Old",
            content_markdown="x",
            owner="a@b.com",
            last_updated_at=old,
            word_count=1,
            block_count=1,
            embed_count=0,
            database_refs_count=0,
        ),
    ]
    issues = detect_issues(pages)
    stale = [i for i in issues if i.type == STALE_PAGE]
    assert len(stale) == 1
    assert stale[0].severity >= 3


def test_detect_issues_missing_owner():
    """MISSING_OWNER detected when owner is null/empty."""
    now = datetime.utcnow()
    pages = [
        PageInfo(
            id=1,
            workspace_id=1,
            title="No Owner",
            content_markdown="x",
            owner=None,
            last_updated_at=now,
            word_count=1,
            block_count=1,
            embed_count=0,
            database_refs_count=0,
        ),
    ]
    issues = detect_issues(pages)
    missing = [i for i in issues if i.type == MISSING_OWNER]
    assert len(missing) == 1


def test_detect_issues_huge_page():
    """HUGE_PAGE detected when word_count > 2000 or block_count > 400."""
    now = datetime.utcnow()
    pages = [
        PageInfo(
            id=1,
            workspace_id=1,
            title="Huge",
            content_markdown="x",
            owner="a@b.com",
            last_updated_at=now,
            word_count=2500,
            block_count=100,
            embed_count=0,
            database_refs_count=0,
        ),
    ]
    issues = detect_issues(pages)
    huge = [i for i in issues if i.type == HUGE_PAGE]
    assert len(huge) == 1


def test_detect_issues_high_complexity():
    """HIGH_COMPLEXITY when embed_count + database_refs_count >= 30."""
    now = datetime.utcnow()
    pages = [
        PageInfo(
            id=1,
            workspace_id=1,
            title="Complex",
            content_markdown="x",
            owner="a@b.com",
            last_updated_at=now,
            word_count=10,
            block_count=5,
            embed_count=20,
            database_refs_count=15,
        ),
    ]
    issues = detect_issues(pages)
    high = [i for i in issues if i.type == HIGH_COMPLEXITY]
    assert len(high) == 1


def test_detect_issues_duplicate():
    """DUPLICATE_PAGE when title/content similarity is high."""
    now = datetime.utcnow()
    pages = [
        PageInfo(
            id=1,
            workspace_id=1,
            title="Meeting Notes",
            content_markdown="Attendees: Alice Bob. Date: 2024-01-15.",
            owner="a@b.com",
            last_updated_at=now,
            word_count=5,
            block_count=1,
            embed_count=0,
            database_refs_count=0,
        ),
        PageInfo(
            id=2,
            workspace_id=1,
            title="Meeting Notes",
            content_markdown="Attendees: Alice Bob. Date: 2024-01-15.",
            owner="b@b.com",
            last_updated_at=now,
            word_count=5,
            block_count=1,
            embed_count=0,
            database_refs_count=0,
        ),
    ]
    issues = detect_issues(pages)
    dup = [i for i in issues if i.type == DUPLICATE_PAGE]
    assert len(dup) >= 1
