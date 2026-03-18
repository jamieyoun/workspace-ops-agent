"""Pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient

# Use temp file SQLite for tests (in-memory creates new DB per connection)
os.environ["DATABASE_URL"] = "sqlite:///./test_workspace_ops.db"

from app.main import app
from app.db import init_db, SessionLocal, engine
from app.models import Workspace, Page, Base


@pytest.fixture
def client():
    """Test client with fresh database."""
    # Drop and recreate tables for clean schema
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_client(client):
    """Test client with seed data loaded."""
    db = SessionLocal()
    try:
        ws = Workspace(name="Test Workspace")
        db.add(ws)
        db.commit()
        db.refresh(ws)
        db.add(Page(workspace_id=ws.id, title="Test Page", owner="test@example.com"))
        db.commit()
    finally:
        db.close()
    return client
