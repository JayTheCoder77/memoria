from __future__ import annotations

import time
import uuid
from collections import defaultdict


class RateLimitExceeded(Exception):
    pass


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[uuid.UUID, list[float]] = defaultdict(list)

    def hit(self, key_id: uuid.UUID) -> None:
        now = time.monotonic()
        window = [stamp for stamp in self._hits[key_id] if now - stamp < self.window_seconds]
        if len(window) >= self.limit:
            self._hits[key_id] = window
            raise RateLimitExceeded
        window.append(now)
        self._hits[key_id] = window
