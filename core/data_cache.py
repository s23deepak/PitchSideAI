"""
TTL-based cache with namespace isolation. Prevents redundant calls within a run.

Supports in-memory (default) and Redis-compatible backends.
"""
from __future__ import annotations

import time
import threading
from typing import Any, Optional


class DataCache:
    """TTL-based cache with namespace isolation."""

    def __init__(self, ttl_seconds: int = 1800):
        self._store: dict[str, dict[str, tuple[float, Any]]] = {}
        self._default_ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        self._lock = threading.RLock()

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Returns None if expired or missing."""
        with self._lock:
            ns = self._store.get(namespace)
            if ns is None:
                self._misses += 1
                return None

            entry = ns.get(key)
            if entry is None:
                self._misses += 1
                return None

            expiry, value = entry
            if expiry < time.time():
                del ns[key]
                self._misses += 1
                return None

            self._hits += 1
            return value

    def set(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> None:
        """Sets with TTL (uses default if not specified)."""
        with self._lock:
            if namespace not in self._store:
                self._store[namespace] = {}
            expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._store[namespace][key] = (expiry, value)

    def invalidate(self, namespace: str) -> None:
        """Clears entire namespace."""
        with self._lock:
            self._store.pop(namespace, None)

    def clear(self) -> None:
        """Clears all namespaces."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, Any]:
        """Hit rate, miss rate, size."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / max(1, total)
            size = sum(len(ns) for ns in self._store.values())
            namespace_count = len(self._store)
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
            "total_entries": size,
            "namespace_count": namespace_count,
            "default_ttl_seconds": self._default_ttl,
        }