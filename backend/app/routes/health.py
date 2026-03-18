"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Return service health status."""
    return {"status": "ok", "service": "workspace-ops-backend"}
