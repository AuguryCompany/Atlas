from __future__ import annotations

import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float, max_items: int = 256):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        expires, value = hit
        if expires < time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        if len(self._data) >= self.max_items:
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._data.pop(oldest, None)
        self._data[key] = (time.monotonic() + self.ttl, value)

    def clear(self) -> None:
        self._data.clear()
