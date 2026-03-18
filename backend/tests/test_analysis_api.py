"""Tests for analysis API endpoints."""

import pytest

from app.db import SessionLocal
from app.models import Workspace, Page


@pytest.fixture
def workspace_with_pages(client):
    """Client with a workspace and pages for analysis."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test Workspace")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        db.add(
            Page(
                workspace_id=ws.id,
                title="Test Page",
                content_markdown="Hello world. This is content.",
                owner="test@example.com",
            )
        )
        db.commit()
    finally:
        db.close()
    return client


def test_analyze_endpoint(workspace_with_pages):
    """POST /workspaces/{id}/analyze runs pipeline."""
    # Get workspace id from list
    r = workspace_with_pages.get("/workspaces")
    assert r.status_code == 200
    ws_id = r.json()[0]["id"]

    r = workspace_with_pages.post(f"/workspaces/{ws_id}/analyze")
    assert r.status_code == 200
    data = r.json()
    assert data["pages_processed"] >= 1
    assert data["metrics_updated"] >= 1


def test_issues_endpoint(workspace_with_pages):
    """GET /workspaces/{id}/issues returns issues."""
    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]

    r = workspace_with_pages.get(f"/workspaces/{ws_id}/issues")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_score_endpoint(workspace_with_pages):
    """GET /workspaces/{id}/score returns score and subscores."""
    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]

    r = workspace_with_pages.get(f"/workspaces/{ws_id}/score")
    assert r.status_code == 200
    data = r.json()
    assert "overall" in data
    assert "subscores" in data
    assert 0 <= data["overall"] <= 100
    assert len(data["subscores"]) == 4
    for s in data["subscores"]:
        assert "name" in s
        assert "score" in s
        assert "explanation" in s


def test_generate_recommendations_endpoint(workspace_with_pages):
    """POST /workspaces/{id}/recommendations/generate uses heuristic fallback (no API key)."""
    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]
    # Run analyze first to create issues
    workspace_with_pages.post(f"/workspaces/{ws_id}/analyze")

    r = workspace_with_pages.post(f"/workspaces/{ws_id}/recommendations/generate")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "source" in data
    assert data["source"] in ("openai", "heuristic")


def test_list_pages_endpoint(workspace_with_pages):
    """GET /workspaces/{id}/pages returns pages."""
    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_pages.get(f"/workspaces/{ws_id}/pages")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_get_page_endpoint(workspace_with_pages):
    """GET /pages/{id} returns page detail."""
    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]
    r = workspace_with_pages.get(f"/workspaces/{ws_id}/pages")
    pages = r.json()
    assert len(pages) >= 1
    page_id = pages[0]["id"]
    r = workspace_with_pages.get(f"/pages/{page_id}")
    assert r.status_code == 200
    assert r.json()["id"] == page_id
    assert "title" in r.json()


def test_list_recommendations_endpoint(workspace_with_pages):
    """GET /workspaces/{id}/recommendations returns list."""
    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]

    r = workspace_with_pages.get(f"/workspaces/{ws_id}/recommendations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_explain_recommendation_endpoint(workspace_with_pages):
    """POST /recommendations/{id}/explain uses heuristic fallback (no API key)."""
    from app.db import SessionLocal
    from app.models import Page

    r = workspace_with_pages.get("/workspaces")
    ws_id = r.json()[0]["id"]
    # Add page without owner to ensure we get issues + recommendations
    db = SessionLocal()
    try:
        db.add(Page(workspace_id=ws_id, title="Orphan Page", content_markdown="x", owner=None))
        db.commit()
    finally:
        db.close()

    workspace_with_pages.post(f"/workspaces/{ws_id}/analyze")
    workspace_with_pages.post(f"/workspaces/{ws_id}/recommendations/generate")

    r = workspace_with_pages.get(f"/workspaces/{ws_id}/recommendations")
    recs = r.json()
    assert len(recs) >= 1, "Need at least one recommendation to explain"
    rec_id = recs[0]["id"]

    r = workspace_with_pages.post(f"/recommendations/{rec_id}/explain")
    assert r.status_code == 200
    data = r.json()
    assert "why_this_matters" in data
    assert "risk_tradeoff" in data
    assert "expected_impact" in data
    assert "source" in data
    assert data["source"] in ("openai", "heuristic")
    assert len(data["why_this_matters"]) > 0
