"""
Per-source async rate limiter for data retrieval.

Each data source gets its own RateLimiter instance to prevent
throttling and distribute load evenly across providers.

Uses a sliding-window counter with configurable RPM.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Async rate limiter for a single data source."""

    def __init__(self, requests_per_minute: int = 60):
        self._rpm = requests_per_minute
        self._window_start = time.monotonic()
        self._request_count = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if necessary to stay within the rate limit."""
        async with self._lock:
            now = time.monotonic()
            window_elapsed = now - self._window_start

            if window_elapsed >= 60:
                self._window_start = now
                self._request_count = 0

            if self._request_count >= self._rpm:
                sleep_for = 60 - window_elapsed + 0.5
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                    self._window_start = time.monotonic()
                    self._request_count = 0

            self._request_count += 1

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        elapsed = now - self._window_start
        if elapsed >= 60:
            return self._rpm
        return max(0, self._rpm - self._request_count)

    @property
    def is_throttled(self) -> bool:
        return self.remaining <= 0


def get_source_rate_limiter(
    source_name: str,
    default_rpm: int = 60,
    overrides: Optional[dict[str, int]] = None,
) -> RateLimiter:
    """Create a rate limiter with source-specific RPM overrides."""
    rpm = default_rpm
    if overrides and source_name in overrides:
        rpm = overrides[source_name]
    return RateLimiter(requests_per_minute=rpm)


# Default RPM values per source type
DEFAULT_SOURCE_RPM: dict[str, int] = {
    "espn": 120,
    "football_data_org": 10,
    "transfermarkt": 20,
    "sofascore": 30,
    "fbref": 30,
    "whoscored": 30,
    "11v11": 30,
    "open_meteo": 60,
    "tavily": 30,
    "exa": 30,
    "wikipedia": 60,
    "dbpedia": 60,
    "firecrawl": 30,
    "jina": 30,
    "brightdata_mcp": 30,
    "goal": 30,
    "rotowire": 30,
    "sky_sports": 30,
    "bbc_sport": 30,
    "the_athletic": 20,
    "sports_mole": 30,
    "onefootball": 30,
    "forvo": 30,
    "youglish": 30,
    "statsbomb": 60,
}