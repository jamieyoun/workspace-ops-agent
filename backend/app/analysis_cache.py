"""In-memory cache for analysis results (score, issues) per workspace. TTL 5 minutes."""

import time
from typing import Any, Dict, Optional

_cache: Dict[int, Dict[str, Any]] = {}
TTL_SEC = 300  # 5 minutes


def get_cached(workspace_id: int, key: str) -> Optional[Any]:
    """Return cached value if present and not expired."""
    if workspace_id not in _cache:
        return None
    entry = _cache[workspace_id].get(key)
    if not entry:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _cache[workspace_id][key]
        return None
    return value


def set_cached(workspace_id: int, key: str, value: Any) -> None:
    """Store value with TTL."""
    if workspace_id not in _cache:
        _cache[workspace_id] = {}
    _cache[workspace_id][key] = (value, time.time() + TTL_SEC)


def invalidate_workspace(workspace_id: int) -> None:
    """Invalidate all cached data for a workspace (e.g. after new analysis)."""
    if workspace_id in _cache:
        del _cache[workspace_id]
