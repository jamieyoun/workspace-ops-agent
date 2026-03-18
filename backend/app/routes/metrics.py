"""Metrics endpoint for observability."""

from fastapi import APIRouter

from app.metrics_store import get_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_metrics_endpoint():
    """Return simple JSON metrics: counts, avg latency, last run timestamps."""
    return get_metrics()
