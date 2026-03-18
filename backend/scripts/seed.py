#!/usr/bin/env python3
"""Seed script to create demo Notion-like workspace data."""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Fixed seed for deterministic output (consistent screenshots and demos)
random.seed(42)

from app.db import SessionLocal, init_db
from app.models import (
    Workspace,
    Page,
    PageMetric,
    Issue,
    Recommendation,
    AgentAction,
)

# Sample content for varied page sizes
SHORT_CONTENT = """# Quick Notes
- Item 1
- Item 2
- Item 3
"""

MEDIUM_CONTENT = """# Project Overview
This document outlines the key aspects of our project.

## Background
We started this initiative in Q1 to improve documentation.

## Goals
1. Centralize knowledge
2. Reduce duplication
3. Improve discoverability

## Next Steps
- Review with stakeholders
- Implement feedback
"""

# Very long markdown for huge pages (~5000+ words)
LONG_PARAGRAPH = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris. "
) * 50

HUGE_CONTENT = f"""# Comprehensive Documentation

{LONG_PARAGRAPH}

## Section 2
{LONG_PARAGRAPH}

## Section 3
{LONG_PARAGRAPH}

## Section 4
{LONG_PARAGRAPH}

## Section 5
{LONG_PARAGRAPH}
"""

# Duplicate content for simulating duplicates
DUPLICATE_TITLE = "Meeting Notes"
DUPLICATE_CONTENT = """# Meeting Notes
- Attendees: Alice, Bob, Charlie
- Date: 2024-01-15
- Action items: TBD
"""


def seed():
    """Create demo workspace with pages, metrics, issues, recommendations, and actions."""
    init_db()
    db = SessionLocal()
    try:
        # Clear in reverse dependency order
        db.query(AgentAction).delete()
        db.query(Recommendation).delete()
        db.query(Issue).delete()
        db.query(PageMetric).delete()
        db.query(Page).delete()
        db.query(Workspace).delete()
        db.commit()

        now = datetime.utcnow()
        stale_threshold = now - timedelta(days=270)  # ~9 months

        # Create workspace
        ws = Workspace(name="Acme Corp Knowledge Base", created_at=now - timedelta(days=365))
        db.add(ws)
        db.commit()
        db.refresh(ws)

        pages_data = [
            # Stale pages (9+ months)
            ("Q1 Planning", MEDIUM_CONTENT, "alice@acme.com", -300),
            ("Legacy API Docs", SHORT_CONTENT, "bob@acme.com", -320),
            ("Deprecated Workflows", SHORT_CONTENT, None, -350),  # no owner
            ("Old Onboarding", MEDIUM_CONTENT, "charlie@acme.com", -400),
            ("Archive 2023", SHORT_CONTENT, None, -380),  # no owner
            # Recent pages
            ("Current Sprint", MEDIUM_CONTENT, "alice@acme.com", -5),
            ("Product Roadmap", MEDIUM_CONTENT, "bob@acme.com", -2),
            ("Engineering Standards", MEDIUM_CONTENT, "charlie@acme.com", -1),
            # Huge pages
            ("Master Documentation", HUGE_CONTENT, "alice@acme.com", -30),
            ("Complete API Reference", HUGE_CONTENT, "bob@acme.com", -15),
            ("Full Design System", HUGE_CONTENT, None, -20),  # no owner
            # Duplicates
            (DUPLICATE_TITLE, DUPLICATE_CONTENT, "alice@acme.com", -10),
            (DUPLICATE_TITLE, DUPLICATE_CONTENT, "bob@acme.com", -12),
            ("Meeting Notes", DUPLICATE_CONTENT, None, -8),  # duplicate, no owner
            # More varied
            ("Quick Reference", SHORT_CONTENT, "charlie@acme.com", -7),
            ("Team Handbook", MEDIUM_CONTENT, "alice@acme.com", -45),
            ("Incident Runbook", MEDIUM_CONTENT, "bob@acme.com", -60),
            ("Security Guidelines", MEDIUM_CONTENT, None, -90),  # no owner
            ("FAQ", SHORT_CONTENT, "charlie@acme.com", -3),
            ("Changelog", MEDIUM_CONTENT, "alice@acme.com", -1),
            ("Glossary", SHORT_CONTENT, "bob@acme.com", -120),
            ("Templates", MEDIUM_CONTENT, None, -200),  # no owner, stale
            ("External Links", SHORT_CONTENT, "charlie@acme.com", -30),
            ("Contributing Guide", MEDIUM_CONTENT, "alice@acme.com", -14),
            ("Release Notes", MEDIUM_CONTENT, "bob@acme.com", -2),
        ]

        pages = []
        for title, content, owner, days_ago in pages_data:
            created = now + timedelta(days=days_ago)
            # Stale pages (9+ months): last_updated = created (no updates)
            # Recent pages: last_updated = within last 2 weeks
            is_stale = days_ago <= -270
            last_updated = created if is_stale else now - timedelta(days=random.randint(1, 14))
            page = Page(
                workspace_id=ws.id,
                title=title,
                content_markdown=content,
                owner=owner,
                last_updated_at=last_updated,
                created_at=created,
            )
            db.add(page)
            pages.append(page)

        db.commit()
        for p in pages:
            db.refresh(p)

        # Page metrics - some with high embed_count / database_refs_count
        for i, page in enumerate(pages):
            word_count = len(page.content_markdown.split()) if page.content_markdown else 0
            embed_count = 0
            database_refs_count = 0
            if "Master" in page.title or "Complete" in page.title or "Full" in page.title:
                embed_count = random.randint(15, 45)
                database_refs_count = random.randint(5, 25)
            elif i % 4 == 0:
                embed_count = random.randint(3, 12)
                database_refs_count = random.randint(1, 8)
            elif "Templates" in page.title or "External" in page.title:
                embed_count = random.randint(20, 50)
                database_refs_count = random.randint(10, 30)

            block_count = word_count // 10 + random.randint(1, 20)
            db.add(
                PageMetric(
                    page_id=page.id,
                    word_count=word_count,
                    block_count=block_count,
                    embed_count=embed_count,
                    database_refs_count=database_refs_count,
                )
            )

        db.commit()

        # Issues
        stale_pages = [p for p in pages if p.last_updated_at < stale_threshold]
        no_owner_pages = [p for p in pages if p.owner is None]
        huge_pages = [p for p in pages if p.content_markdown and len(p.content_markdown) > 5000]

        issues = [
            Issue(
                workspace_id=ws.id,
                page_id=stale_pages[0].id if stale_pages else None,
                type="stale_content",
                severity=3,
                summary="Page not updated in 9+ months",
                details_json=json.dumps({"page_title": stale_pages[0].title}),
            ),
            Issue(
                workspace_id=ws.id,
                page_id=no_owner_pages[0].id if no_owner_pages else None,
                type="missing_owner",
                severity=2,
                summary="Page has no assigned owner",
                details_json=json.dumps({"page_title": no_owner_pages[0].title}),
            ),
            Issue(
                workspace_id=ws.id,
                page_id=huge_pages[0].id if huge_pages else None,
                type="oversized_page",
                severity=4,
                summary="Page exceeds recommended size",
                details_json=json.dumps({"word_count_approx": len(huge_pages[0].content_markdown.split())}),
            ),
            Issue(
                workspace_id=ws.id,
                page_id=None,
                type="duplicate_content",
                severity=2,
                summary="Multiple pages with identical titles",
                details_json=json.dumps({"titles": ["Meeting Notes"]}),
            ),
        ]
        db.add_all(issues)
        db.commit()

        # Recommendations
        recs = [
            Recommendation(
                workspace_id=ws.id,
                page_id=stale_pages[0].id if stale_pages else None,
                type="content_refresh",
                priority=3,
                title="Refresh stale documentation",
                rationale="Improve accuracy and relevance",
                proposed_changes_json=json.dumps({"action": "review_and_update"}),
                status="proposed",
            ),
            Recommendation(
                workspace_id=ws.id,
                page_id=no_owner_pages[0].id if no_owner_pages else None,
                type="assign_ownership",
                priority=2,
                title="Assign owners to unowned pages",
                rationale="Ensure accountability",
                proposed_changes_json=json.dumps({"action": "assign_owners"}),
                status="approved",
            ),
            Recommendation(
                workspace_id=ws.id,
                page_id=huge_pages[0].id if huge_pages else None,
                type="split_page",
                priority=4,
                title="Split oversized page into sections",
                rationale="Improve readability and maintainability",
                proposed_changes_json=json.dumps({"action": "split_into_subpages"}),
                status="proposed",
            ),
        ]
        db.add_all(recs)
        db.commit()
        for r in recs:
            db.refresh(r)

        # Agent actions
        actions = [
            AgentAction(
                workspace_id=ws.id,
                recommendation_id=recs[0].id,
                action_type="analyze",
                actor="agent",
                payload_json=json.dumps({"model": "workspace_scan"}),
            ),
            AgentAction(
                workspace_id=ws.id,
                recommendation_id=recs[1].id,
                action_type="approve",
                actor="user",
                payload_json=json.dumps({"user_id": "alice"}),
            ),
        ]
        db.add_all(actions)
        db.commit()

        print("✓ Seeded 1 workspace with 25 pages, metrics, issues, recommendations, and agent actions")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
