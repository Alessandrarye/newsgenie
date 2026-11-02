"""Tiny in-memory caches.

TTLCache keeps fresh results so repeated category clicks are instant and do not
burn API quota. The "last good" store keeps the most recent successful result
per key with no expiry, so when every live provider fails we can still show
something, clearly labeled as stale.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}
        self._last_good: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            hit = self._data.get(key)
            if not hit:
                return None
            stored_at, value = hit
            if time.time() - stored_at > self.ttl:
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        now = time.time()
        with self._lock:
            self._data[key] = (now, value)
            self._last_good[key] = (now, value)

    def get_stale(self, key: str) -> tuple[float, Any] | None:
        """Return (timestamp, value) of the last good result, ignoring TTL."""
        with self._lock:
            return self._last_good.get(key)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._last_good.clear()
