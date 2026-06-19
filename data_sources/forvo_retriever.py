"""
Forvo Retriever — pronunciation audio clips for player names.

Queries Forvo's API for authentic pronunciation recordings by native speakers.
Returns audio URLs and phonetic transcriptions.
"""
from __future__ import annotations

from typing import Any

import httpx

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

FORVO_API_BASE = "https://apifree.forvo.com"
FORVO_TIMEOUT = 10


class ForvoRetriever(BaseRetriever):
    def __init__(self, cache=None):
        super().__init__(
            source_name="forvo",
            source_tier=get_source_tier("forvo"),
            rate_limiter=RateLimiter(requests_per_minute=30),
            cache=cache,
        )
        self._client: httpx.AsyncClient | None = None

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        language = params.get("language", "en")
        key = params.get("api_key", "")

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=FORVO_TIMEOUT)

        url = f"{FORVO_API_BASE}/{key}/pronunciation/{language}/{query}/format/json"
        resp = await self._client.get(url)

        raw_text = resp.text
        raw_bytes = len(raw_text.encode("utf-8"))

        if resp.status_code != 200:
            return {"error": f"Forvo API returned {resp.status_code}"}, raw_bytes, []

        try:
            data = resp.json()
        except Exception:
            data = {"raw": raw_text[:500]}

        return data, raw_bytes, [url]