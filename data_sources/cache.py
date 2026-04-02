"""
Caching layer for data retrieval operations.

Reduces API calls for frequently requested data (teams, players, weather).
"""

import json
import time
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from functools import wraps


class DataCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time to live for cached items (default: 1 hour)
        """
        self.ttl = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, namespace: str, identifier: str) -> str:
        """Generate cache key from namespace and identifier."""
        return f"{namespace}:{identifier}"

    def get(self, namespace: str, identifier: str) -> Optional[Any]:
        """
        Retrieve cached value if not expired.

        Args:
            namespace: Cache namespace (e.g., 'espn_team', 'weather_venue')
            identifier: Item identifier (e.g., team_name, venue_name)

        Returns:
            Cached value or None if expired/not found
        """
        key = self._get_key(namespace, identifier)
        if key not in self.cache:
            return None

        entry = self.cache[key]
        if time.time() - entry["timestamp"] > self.ttl:
            del self.cache[key]
            return None

        return entry["data"]

    def set(self, namespace: str, identifier: str, value: Any) -> None:
        """
        Store value in cache with current timestamp.

        Args:
            namespace: Cache namespace
            identifier: Item identifier
            value: Data to cache
        """
        key = self._get_key(namespace, identifier)
        self.cache[key] = {
            "data": value,
            "timestamp": time.time(),
        }

    def clear(self, namespace: Optional[str] = None) -> None:
        """
        Clear cache entries.

        Args:
            namespace: Clear only this namespace. If None, clear all.
        """
        if namespace is None:
            self.cache.clear()
            return

        keys_to_delete = [k for k in self.cache.keys() if k.startswith(namespace)]
        for key in keys_to_delete:
            del self.cache[key]

    def cached(self, namespace: str, ttl: Optional[int] = None):
        """
        Decorator for caching function results.

        Args:
            namespace: Cache namespace
            ttl: Override default TTL for this function

        Usage:
            @cache.cached("espn_team", ttl=3600)
            async def get_team_data(team_name):
                return fetch_from_espn(team_name)
        """

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Use first positional arg as cache key identifier
                identifier = args[0] if args else str(kwargs)

                # Try to get from cache
                cached_value = self.get(namespace, str(identifier))
                if cached_value is not None:
                    return cached_value

                # Call function and cache result
                result = await func(*args, **kwargs)
                self.set(namespace, str(identifier), result)
                return result

            return wrapper

        return decorator
