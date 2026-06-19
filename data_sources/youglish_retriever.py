"""
YouGlish Retriever — name pronunciation in YouTube context.

Queries YouGlish for real-world pronunciation examples of player names
in broadcast commentary contexts.
"""
from __future__ import annotations

from typing import Any

import httpx

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

YOUGLISH_API_BASE = "https://youglish.com/api/v1"
YOUGLISH_TIMEOUT = 10


class YouglishRetriever(BaseRetriever):
    def __init__(self, cache=None):
        super().__init__(
            source_name="youglish",
            source_tier=get_source_tier("youglish"),
            rate_limiter=RateLimiter(requests_per_minute=30),
            cache=cache,
        )

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        language = params.get("language", "en")
        accent = params.get("accent", "")

        async with httpx.AsyncClient(timeout=YOUGLISH_TIMEOUT) as client:
            resp = await client.get(
                f"{YOUGLISH_API_BASE}/pronunciation",
                params={"query": query, "language": language, "accent": accent},
            )
            raw_text = resp.text
            raw_bytes = len(raw_text.encode("utf-8"))

            if resp.status_code != 200:
                return {"error": f"YouGlish API returned {resp.status_code}"}, raw_bytes, []

            try:
                data = resp.json()
            except Exception:
                data = {"raw": raw_text[:500]}

            return data, raw_bytes, [str(resp.url)]