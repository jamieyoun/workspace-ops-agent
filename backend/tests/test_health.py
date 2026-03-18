"""Tests for health endpoint."""

import pytest


def test_health_endpoint(client):
    """Verify health endpoint returns ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "workspace-ops-backend" in data["service"]
