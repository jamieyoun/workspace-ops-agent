"""End-to-end test: seed, analyze, generate, approve, apply, verify audit."""

import pytest
from fastapi.testclient import TestClient

from app.db import init_db, engine
from app.main import app
from app.models import Base
from scripts.seed import seed


@pytest.fixture
def e2e_client():
    """Fresh DB, run seed, yield test client."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    seed()
    with TestClient(app) as c:
        yield c


def test_e2e_seed_analyze_generate_approve_apply_audit(e2e_client):
    """Full flow: seed, analyze, generate, approve one, apply one, verify audit."""
    client = e2e_client

    # Get workspace id
    r = client.get("/workspaces")
    assert r.status_code == 200
    workspaces = r.json()
    assert len(workspaces) >= 1
    ws_id = workspaces[0]["id"]

    # Run analysis
    r = client.post(f"/workspaces/{ws_id}/analyze")
    assert r.status_code == 200
    data = r.json()
    assert data["pages_processed"] >= 1

    # Generate recommendations (heuristic fallback when no API key)
    r = client.post(f"/workspaces/{ws_id}/recommendations/generate")
    assert r.status_code == 200
    gen_data = r.json()
    assert gen_data["count"] >= 1
    assert gen_data["source"] in ("openai", "heuristic")

    # Get recommendations, find one we can approve and apply (assign_owner)
    r = client.get(f"/workspaces/{ws_id}/recommendations")
    assert r.status_code == 200
    recs = r.json()
    assert len(recs) >= 1

    # Prefer assign_owner (easiest to apply), else take first proposed
    assign_rec = next((r for r in recs if r["type"] == "assign_owner" and r["status"] == "proposed"), None)
    if not assign_rec:
        assign_rec = next((r for r in recs if r["status"] == "proposed"), recs[0])
    rec_id = assign_rec["id"]

    # Approve
    r = client.post(f"/recommendations/{rec_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # Apply (assign_owner needs owner in payload)
    payload = {"owner": "e2e-test@example.com"} if assign_rec["type"] == "assign_owner" else {}
    if assign_rec["type"] == "split_page":
        payload = {"section_text": "Extracted.", "new_title": "Part 2"}
    elif assign_rec["type"] == "archive":
        payload = {}
    elif assign_rec["type"] == "summarize":
        payload = {"summary_text": "Summary."}
    elif assign_rec["type"] == "standardize_template":
        payload = {}

    r = client.post(f"/recommendations/{rec_id}/apply", json=payload)
    assert r.status_code == 200
    apply_data = r.json()
    assert apply_data["applied"] is True or apply_data.get("idempotent") is True

    # Verify audit log has expected entries
    r = client.get(f"/workspaces/{ws_id}/audit")
    assert r.status_code == 200
    actions = r.json()
    assert isinstance(actions, list)
    assert len(actions) >= 1

    action_types = [a["action_type"] for a in actions]
    assert "run_analysis" in action_types
    assert "generate_recommendations" in action_types
    assert "approve" in action_types
    assert "apply" in action_types
