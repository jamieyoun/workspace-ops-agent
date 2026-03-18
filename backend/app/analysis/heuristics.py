"""Pure functions for computing PageMetrics and detecting Issues."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

# Issue type constants
STALE_PAGE = "STALE_PAGE"
MISSING_OWNER = "MISSING_OWNER"
HUGE_PAGE = "HUGE_PAGE"
DUPLICATE_PAGE = "DUPLICATE_PAGE"
HIGH_COMPLEXITY = "HIGH_COMPLEXITY"

# Thresholds
STALE_DAYS = 180
HUGE_WORD_COUNT = 2000
HUGE_BLOCK_COUNT = 400
HIGH_COMPLEXITY_THRESHOLD = 30
DUPLICATE_SIMILARITY_THRESHOLD = 0.7


@dataclass
class PageMetricData:
    """Computed page metrics."""

    word_count: int
    block_count: int
    embed_count: int
    database_refs_count: int


def compute_page_metrics(content_markdown: Optional[str]) -> PageMetricData:
    """Compute PageMetric from content_markdown."""
    if not content_markdown:
        return PageMetricData(0, 0, 0, 0)

    # word_count: split on whitespace
    words = content_markdown.split()
    word_count = len(words)

    # block_count: approx from markdown lines (headers, list items, code blocks, paragraphs)
    lines = [l.strip() for l in content_markdown.splitlines() if l.strip()]
    block_count = 0
    in_code_block = False
    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            block_count += 1
        elif not in_code_block:
            if line.startswith("#") or line.startswith("-") or line.startswith("*") or line.startswith("1."):
                block_count += 1
            elif line:
                block_count += 1

    # embed_count: image links ![alt](url), <img>, <iframe>
    img_pattern = r"!\[.*?\]\(.*?\)|<img[^>]*>|<iframe[^>]*>"
    embed_count = len(re.findall(img_pattern, content_markdown, re.IGNORECASE))

    # database_refs_count: /database/ or @database
    db_ref_pattern = r"/database/|@database"
    database_refs_count = len(re.findall(db_ref_pattern, content_markdown, re.IGNORECASE))

    return PageMetricData(
        word_count=word_count,
        block_count=max(block_count, 1),
        embed_count=embed_count,
        database_refs_count=database_refs_count,
    )


def _jaccard_similarity(a: str, b: str) -> float:
    """Token-based Jaccard similarity between two strings."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _content_similarity(content_a: Optional[str], content_b: Optional[str]) -> float:
    """Similarity between two content strings (title + content)."""
    a = (content_a or "").strip()
    b = (content_b or "").strip()
    if len(a) > 500:
        a = a[:500]
    if len(b) > 500:
        b = b[:500]
    return _jaccard_similarity(a, b)


def _days_since(dt: datetime) -> int:
    """Days since last update."""
    now = datetime.utcnow()
    delta = now - dt
    return delta.days


def _stale_severity(days_old: int) -> int:
    """Severity 1-5 based on age. 180+ days = 3, 365+ = 4, 730+ = 5."""
    if days_old < STALE_DAYS:
        return 0
    if days_old < 365:
        return 3
    if days_old < 730:
        return 4
    return 5


@dataclass
class PageInfo:
    """Minimal page info for issue detection."""

    id: int
    workspace_id: int
    title: str
    content_markdown: Optional[str]
    owner: Optional[str]
    last_updated_at: datetime
    word_count: int
    block_count: int
    embed_count: int
    database_refs_count: int


@dataclass
class DetectedIssue:
    """Issue detected by heuristics."""

    workspace_id: int
    page_id: Optional[int]
    type: str
    severity: int
    summary: str
    details_json: Optional[str]
    issue_key: str


def detect_issues(pages: List[PageInfo]) -> List[DetectedIssue]:
    """Generate issues from pages using heuristics."""
    issues: List[DetectedIssue] = []

    for page in pages:
        # STALE_PAGE
        days_old = _days_since(page.last_updated_at)
        if days_old >= STALE_DAYS:
            severity = _stale_severity(days_old)
            issues.append(
                DetectedIssue(
                    workspace_id=page.workspace_id,
                    page_id=page.id,
                    type=STALE_PAGE,
                    severity=severity,
                    summary=f"Page not updated in {days_old} days",
                    details_json=json.dumps({"days_old": days_old, "page_title": page.title}),
                    issue_key=f"{page.workspace_id}|{page.id}|{STALE_PAGE}",
                )
            )

        # MISSING_OWNER
        if not page.owner or not str(page.owner).strip():
            issues.append(
                DetectedIssue(
                    workspace_id=page.workspace_id,
                    page_id=page.id,
                    type=MISSING_OWNER,
                    severity=2,
                    summary="Page has no assigned owner",
                    details_json=json.dumps({"page_title": page.title}),
                    issue_key=f"{page.workspace_id}|{page.id}|{MISSING_OWNER}",
                )
            )

        # HUGE_PAGE
        if page.word_count > HUGE_WORD_COUNT or page.block_count > HUGE_BLOCK_COUNT:
            issues.append(
                DetectedIssue(
                    workspace_id=page.workspace_id,
                    page_id=page.id,
                    type=HUGE_PAGE,
                    severity=4,
                    summary=f"Page exceeds recommended size (words={page.word_count}, blocks={page.block_count})",
                    details_json=json.dumps(
                        {"word_count": page.word_count, "block_count": page.block_count, "page_title": page.title}
                    ),
                    issue_key=f"{page.workspace_id}|{page.id}|{HUGE_PAGE}",
                )
            )

        # HIGH_COMPLEXITY
        total = page.embed_count + page.database_refs_count
        if total >= HIGH_COMPLEXITY_THRESHOLD:
            issues.append(
                DetectedIssue(
                    workspace_id=page.workspace_id,
                    page_id=page.id,
                    type=HIGH_COMPLEXITY,
                    severity=3,
                    summary=f"High complexity (embeds={page.embed_count}, db_refs={page.database_refs_count})",
                    details_json=json.dumps(
                        {"embed_count": page.embed_count, "database_refs_count": page.database_refs_count}
                    ),
                    issue_key=f"{page.workspace_id}|{page.id}|{HIGH_COMPLEXITY}",
                )
            )

    # DUPLICATE_PAGE: pairwise comparison
    for i, p1 in enumerate(pages):
        for p2 in pages[i + 1 :]:
            title_sim = _jaccard_similarity(p1.title, p2.title)
            content_sim = _content_similarity(p1.content_markdown, p2.content_markdown)
            combined = 0.5 * title_sim + 0.5 * content_sim
            if combined >= DUPLICATE_SIMILARITY_THRESHOLD:
                page_ids = sorted([p1.id, p2.id])
                key = f"{p1.workspace_id}|{page_ids[0]},{page_ids[1]}|{DUPLICATE_PAGE}"
                issues.append(
                    DetectedIssue(
                        workspace_id=p1.workspace_id,
                        page_id=None,
                        type=DUPLICATE_PAGE,
                        severity=2,
                        summary=f"Duplicate content: '{p1.title}' and '{p2.title}'",
                        details_json=json.dumps(
                            {"page_ids": page_ids, "titles": [p1.title, p2.title], "similarity": round(combined, 2)}
                        ),
                        issue_key=key,
                    )
                )

    return issues
