"""Tests for enterprise guardrails: status transitions and apply effects."""

import pytest

from app.db import SessionLocal
from app.models import Workspace, Page, Recommendation, AgentAction


@pytest.fixture
def workspace_with_recommendation(client):
    """Client with workspace, page, and proposed recommendation."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test Workspace")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        page = Page(
            workspace_id=ws.id,
            title="Test Page",
            content_markdown="# Content\n\nSome text here.",
            owner=None,
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        rec = Recommendation(
            workspace_id=ws.id,
            page_id=page.id,
            type="assign_owner",
            priority=2,
            title="Assign owner",
            rationale="Page has no owner",
            status="proposed",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
    finally:
        db.close()
    return client


def test_approve_transition(workspace_with_recommendation):
    """Approve changes status from proposed to approved."""
    r = workspace_with_recommendation.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/recommendations")
    rec_id = r.json()[0]["id"]

    r = workspace_with_recommendation.post(f"/recommendations/{rec_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_dismiss_transition(workspace_with_recommendation):
    """Dismiss changes status to dismissed."""
    r = workspace_with_recommendation.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/recommendations")
    rec_id = r.json()[0]["id"]

    r = workspace_with_recommendation.post(f"/recommendations/{rec_id}/dismiss")
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"


def test_apply_assign_owner_effect(workspace_with_recommendation):
    """Apply assign_owner updates Page.owner."""
    r = workspace_with_recommendation.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/recommendations")
    rec_id = r.json()[0]["id"]

    r = workspace_with_recommendation.post(
        f"/recommendations/{rec_id}/apply",
        json={"owner": "admin@example.com"},
    )
    assert r.status_code == 200
    assert r.json()["applied"] is True

    db = SessionLocal()
    try:
        page = db.query(Page).filter(Page.workspace_id == ws_id).first()
        assert page.owner == "admin@example.com"
        rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
        assert rec.status == "applied"
    finally:
        db.close()


def test_apply_idempotency(workspace_with_recommendation):
    """Applying twice does nothing (idempotent)."""
    r = workspace_with_recommendation.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/recommendations")
    rec_id = r.json()[0]["id"]

    r1 = workspace_with_recommendation.post(
        f"/recommendations/{rec_id}/apply",
        json={"owner": "first@example.com"},
    )
    assert r1.status_code == 200
    assert r1.json()["applied"] is True

    r2 = workspace_with_recommendation.post(
        f"/recommendations/{rec_id}/apply",
        json={"owner": "second@example.com"},
    )
    assert r2.status_code == 200
    assert r2.json()["applied"] is False
    assert r2.json()["idempotent"] is True

    db = SessionLocal()
    try:
        page = db.query(Page).filter(Page.workspace_id == ws_id).first()
        assert page.owner == "first@example.com"
    finally:
        db.close()


def test_apply_archive_effect(client):
    """Apply archive sets Page.archived_at."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        page = Page(workspace_id=ws.id, title="To Archive", content_markdown="x", owner="a@b.com")
        db.add(page)
        db.commit()
        db.refresh(page)
        rec = Recommendation(
            workspace_id=ws.id,
            page_id=page.id,
            type="archive",
            priority=3,
            title="Archive this",
            rationale="Stale",
            status="approved",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        rec_id = rec.id
        page_id = page.id
    finally:
        db.close()

    r = client.post(f"/recommendations/{rec_id}/apply", json={})
    assert r.status_code == 200
    assert r.json()["applied"] is True

    db = SessionLocal()
    try:
        page = db.query(Page).filter(Page.id == page_id).first()
        assert page.archived_at is not None
    finally:
        db.close()


def test_audit_endpoint(workspace_with_recommendation):
    """GET /workspaces/{id}/audit returns actions."""
    r = workspace_with_recommendation.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/recommendations")
    rec_id = r.json()[0]["id"]
    workspace_with_recommendation.post(f"/recommendations/{rec_id}/approve")

    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/audit")
    assert r.status_code == 200
    actions = r.json()
    assert isinstance(actions, list)
    assert any(a["action_type"] == "approve" and a["actor"] == "user" for a in actions)


def test_cannot_approve_non_proposed(workspace_with_recommendation):
    """Cannot approve when status is not proposed."""
    r = workspace_with_recommendation.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_recommendation.get(f"/workspaces/{ws_id}/recommendations")
    rec_id = r.json()[0]["id"]

    workspace_with_recommendation.post(f"/recommendations/{rec_id}/approve")
    r = workspace_with_recommendation.post(f"/recommendations/{rec_id}/approve")
    assert r.status_code == 400


def test_apply_summarize_effect(client):
    """Apply summarize appends summary section to content_markdown."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        page = Page(
            workspace_id=ws.id,
            title="Long Page",
            content_markdown="# Intro\n\nFirst paragraph.",
            owner="a@b.com",
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        rec = Recommendation(
            workspace_id=ws.id,
            page_id=page.id,
            type="summarize",
            priority=3,
            title="Add summary",
            rationale="Long content",
            status="approved",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        rec_id = rec.id
        page_id = page.id
    finally:
        db.close()

    r = client.post(f"/recommendations/{rec_id}/apply", json={"summary_text": "TL;DR: Key points."})
    assert r.status_code == 200
    assert r.json()["applied"] is True

    db = SessionLocal()
    try:
        page = db.query(Page).filter(Page.id == page_id).first()
        assert "## Summary" in page.content_markdown
        assert "TL;DR" in page.content_markdown
    finally:
        db.close()


def test_apply_standardize_template_effect(client):
    """Apply standardize_template injects header."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        page = Page(
            workspace_id=ws.id,
            title="Doc",
            content_markdown="Body content",
            owner="a@b.com",
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        rec = Recommendation(
            workspace_id=ws.id,
            page_id=page.id,
            type="standardize_template",
            priority=3,
            title="Add header",
            rationale="Standardize",
            status="approved",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        rec_id = rec.id
        page_id = page.id
    finally:
        db.close()

    r = client.post(f"/recommendations/{rec_id}/apply", json={})
    assert r.status_code == 200
    assert r.json()["applied"] is True

    db = SessionLocal()
    try:
        page = db.query(Page).filter(Page.id == page_id).first()
        assert "**Purpose:**" in page.content_markdown
        assert "**Owner:**" in page.content_markdown
        assert "**Last Updated:**" in page.content_markdown
    finally:
        db.close()


def test_apply_split_page_effect(client):
    """Apply split_page creates new Page."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        page = Page(
            workspace_id=ws.id,
            title="Big Page",
            content_markdown="Section 1 content. More text.",
            owner="a@b.com",
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        rec = Recommendation(
            workspace_id=ws.id,
            page_id=page.id,
            type="split_page",
            priority=4,
            title="Split page",
            rationale="Too large",
            status="approved",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        rec_id = rec.id
        ws_id = ws.id
    finally:
        db.close()

    r = client.post(
        f"/recommendations/{rec_id}/apply",
        json={"section_text": "Extracted section.", "new_title": "Part 2"},
    )
    assert r.status_code == 200
    assert r.json()["applied"] is True
    assert r.json()["new_page_id"] is not None

    db = SessionLocal()
    try:
        pages = db.query(Page).filter(Page.workspace_id == ws_id).all()
        assert len(pages) == 2
        new_page = next(p for p in pages if p.title == "Part 2")
        assert new_page.content_markdown == "Extracted section."
    finally:
        db.close()
