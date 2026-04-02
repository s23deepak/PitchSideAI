import time
from typing import Any, Dict, Optional

class DataCache:
    """Simple in-memory cache with TTL."""
    def __init__(self, ttl_seconds: int = 1800):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > self.ttl:
            del self._cache[key]
            return None
        return entry["data"]

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = {
            "timestamp": time.time(),
            "data": value
        }
