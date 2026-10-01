"""In-process sliding-window limiter."""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    """``allow(key)`` is False once ``key`` has made ``limit`` calls in the last ``window`` seconds.

    ponytail: per-process memory, never evicts idle keys. Fine for one web instance; move to
    Redis (or a DB table) when the service scales out or the key set grows without bound.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        recent = self.hits.setdefault(key, deque())
        while recent and recent[0] <= now - self.window:
            recent.popleft()
        if len(recent) >= self.limit:
            return False
        recent.append(now)
        return True
