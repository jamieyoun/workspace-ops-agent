"""In-memory metrics store: request counts, avg latency, last run timestamps."""

import time
from collections import deque
from typing import Deque, Dict, List

# Rolling window of (timestamp, latency_ms) for last N requests
_latencies: Deque[tuple[float, float]] = deque(maxlen=1000)
# Per-endpoint counts
_endpoint_counts: Dict[str, int] = {}
# Last run timestamps for key operations
_last_run: Dict[str, float] = {}


def record_request(route: str, latency_ms: float) -> None:
    """Record a completed request."""
    _latencies.append((time.time(), latency_ms))
    _endpoint_counts[route] = _endpoint_counts.get(route, 0) + 1


def record_last_run(operation: str) -> None:
    """Record that an operation (e.g. analyze, generate) completed."""
    _last_run[operation] = time.time()


def get_metrics() -> dict:
    """Return metrics snapshot: counts, avg latency, last run timestamps."""
    now = time.time()
    # Only consider last 5 minutes for latency
    cutoff = now - 300
    recent = [(ts, lat) for ts, lat in _latencies if ts > cutoff]
    avg_latency = sum(lat for _, lat in recent) / len(recent) if recent else 0
    return {
        "request_count_total": sum(_endpoint_counts.values()),
        "request_count_by_route": dict(_endpoint_counts),
        "avg_latency_ms_last_5min": round(avg_latency, 2),
        "last_run": {k: round(v, 2) for k, v in _last_run.items()},
    }
