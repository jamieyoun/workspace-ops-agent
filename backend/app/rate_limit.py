"""Simple in-memory rate limiter for generate recommendations endpoint."""

import time
from collections import defaultdict
from typing import Dict, Tuple

# (workspace_id -> (count, window_start))
_limiter: Dict[int, Tuple[int, float]] = {}
# 5 requests per minute per workspace
RATE_LIMIT_REQUESTS = 5
RATE_LIMIT_WINDOW_SEC = 60


def check_rate_limit(workspace_id: int) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    if workspace_id not in _limiter:
        _limiter[workspace_id] = (1, now)
        return True
    count, window_start = _limiter[workspace_id]
    if now - window_start >= RATE_LIMIT_WINDOW_SEC:
        _limiter[workspace_id] = (1, now)
        return True
    if count >= RATE_LIMIT_REQUESTS:
        return False
    _limiter[workspace_id] = (count + 1, window_start)
    return True
