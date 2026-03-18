"""Apply recommendation effects (demo implementation)."""

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Page, Recommendation


def _apply_assign_owner(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Update Page.owner."""
    if not rec.page_id:
        return {"applied": False, "reason": "No page_id"}
    page = db.query(Page).filter(Page.id == rec.page_id).first()
    if not page:
        return {"applied": False, "reason": "Page not found"}
    owner = payload.get("owner")
    if not owner or not str(owner).strip():
        return {"applied": False, "reason": "owner required in payload"}
    page.owner = str(owner).strip()
    page.last_updated_at = datetime.utcnow()
    return {"applied": True, "owner": page.owner}


def _apply_summarize(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Append summary section to Page.content_markdown."""
    if not rec.page_id:
        return {"applied": False, "reason": "No page_id"}
    page = db.query(Page).filter(Page.id == rec.page_id).first()
    if not page:
        return {"applied": False, "reason": "Page not found"}
    summary_text = payload.get("summary_text")
    if not summary_text:
        content = page.content_markdown or ""
        summary_text = content[:300] + "..." if len(content) > 300 else content
    if not summary_text.strip():
        summary_text = "(Summary placeholder)"
    section = f"\n\n---\n## Summary\n\n{summary_text.strip()}\n"
    page.content_markdown = (page.content_markdown or "") + section
    page.last_updated_at = datetime.utcnow()
    return {"applied": True}


def _apply_archive(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Mark Page as archived (set archived_at)."""
    if not rec.page_id:
        return {"applied": False, "reason": "No page_id"}
    page = db.query(Page).filter(Page.id == rec.page_id).first()
    if not page:
        return {"applied": False, "reason": "Page not found"}
    if page.archived_at:
        return {"applied": True, "already_archived": True}
    page.archived_at = datetime.utcnow()
    page.last_updated_at = datetime.utcnow()
    return {"applied": True}


def _apply_split_page(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Create new Page with extracted section text."""
    if not rec.page_id:
        return {"applied": False, "reason": "No page_id"}
    page = db.query(Page).filter(Page.id == rec.page_id).first()
    if not page:
        return {"applied": False, "reason": "Page not found"}
    section_text = payload.get("section_text")
    new_title = payload.get("new_title")
    if not section_text or not new_title:
        content = page.content_markdown or ""
        section_text = content[:500] + "..." if len(content) > 500 else content or "(Extracted section)"
        new_title = f"{page.title} (Part 2)"
    new_page = Page(
        workspace_id=page.workspace_id,
        title=str(new_title)[:500],
        content_markdown=section_text,
        owner=page.owner,
    )
    db.add(new_page)
    db.flush()
    return {"applied": True, "new_page_id": new_page.id}


def _apply_standardize_template(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Inject standard header (Purpose/Owner/Last Updated)."""
    if not rec.page_id:
        return {"applied": False, "reason": "No page_id"}
    page = db.query(Page).filter(Page.id == rec.page_id).first()
    if not page:
        return {"applied": False, "reason": "Page not found"}
    now = datetime.utcnow().strftime("%Y-%m-%d")
    header = (
        "---\n"
        "**Purpose:** (To be filled)\n"
        f"**Owner:** {page.owner or '(Unassigned)'}\n"
        f"**Last Updated:** {now}\n"
        "---\n\n"
    )
    content = page.content_markdown or ""
    if content.strip().startswith("---"):
        return {"applied": True, "already_has_header": True}
    page.content_markdown = header + content
    page.last_updated_at = datetime.utcnow()
    return {"applied": True}


def _apply_dedupe(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Demo: no-op for dedupe (would require merging logic)."""
    return {"applied": False, "reason": "Dedupe requires manual merge"}


APPLY_HANDLERS = {
    "assign_owner": _apply_assign_owner,
    "summarize": _apply_summarize,
    "archive": _apply_archive,
    "split_page": _apply_split_page,
    "standardize_template": _apply_standardize_template,
    "dedupe": _apply_dedupe,
}


def apply_recommendation(db: Session, rec: Recommendation, payload: dict) -> dict:
    """Apply a recommendation's effect. Returns result dict."""
    if rec.status == "applied":
        return {"applied": False, "reason": "Already applied", "idempotent": True}
    handler = APPLY_HANDLERS.get(rec.type)
    if not handler:
        return {"applied": False, "reason": f"Unknown type: {rec.type}"}
    result = handler(db, rec, payload)
    if result.get("applied"):
        rec.status = "applied"
    return result
