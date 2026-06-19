"""
Jina AI Reader Retriever — URL → clean markdown extraction.

Uses Jina AI's free reader API to convert any URL into LLM-ready
markdown. No API key required for basic usage.
"""
from __future__ import annotations

from typing import Any

import httpx

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

JINA_READER_BASE = "https://r.jina.ai"
JINA_TIMEOUT = 15


class JinaReaderRetriever(BaseRetriever):
    def __init__(self, cache=None):
        super().__init__(
            source_name="jina",
            source_tier=get_source_tier("jina"),
            rate_limiter=RateLimiter(requests_per_minute=30),
            cache=cache,
        )

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        target_url = params.get("url", query)
        if not target_url.startswith("http"):
            target_url = f"https://{target_url}"

        async with httpx.AsyncClient(timeout=JINA_TIMEOUT) as client:
            headers = {
                "Accept": "application/json",
                "X-Return-Format": "markdown",
            }
            api_key = params.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            resp = await client.get(
                f"{JINA_READER_BASE}/{target_url}",
                headers=headers,
            )
            raw_text = resp.text
            raw_bytes = len(raw_text.encode("utf-8"))

            if resp.status_code != 200:
                return {"error": f"Jina returned {resp.status_code}"}, raw_bytes, []

            try:
                data = resp.json()
            except Exception:
                data = {"raw_markdown": raw_text[:2000]}

            return data, raw_bytes, [target_url]

    async def close(self) -> None:
        pass