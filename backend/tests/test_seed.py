"""Tests for seed data loading."""

import pytest


def test_seed_data_loading(seeded_client):
    """Verify seed data is loaded and workspaces endpoint returns data."""
    response = seeded_client.get("/workspaces")
    assert response.status_code == 200
    workspaces = response.json()
    assert len(workspaces) >= 1
    assert workspaces[0]["name"] == "Test Workspace"
    assert "id" in workspaces[0]
    assert "stats" in workspaces[0]
    assert workspaces[0]["stats"]["page_count"] >= 1
