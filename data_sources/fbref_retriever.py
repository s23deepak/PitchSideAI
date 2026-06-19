"""
FBref Retriever — player season stats, xG, progressive carries, per-90 metrics.

Uses Tavily/Exa search with fbref.com domain filtering to extract
structured statistics. FBref is the gold standard for advanced soccer analytics.
"""
from __future__ import annotations

from typing import Any

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

FBREF_SEARCH_DOMAINS = ["fbref.com"]


class FbrefRetriever(BaseRetriever):
    def __init__(self, cache=None, search_service=None):
        super().__init__(
            source_name="fbref",
            source_tier=get_source_tier("fbref"),
            rate_limiter=RateLimiter(requests_per_minute=30),
            cache=cache,
        )
        self._search = search_service

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        if self._search is None:
            from data_sources.factory import get_search_service
            self._search = get_search_service()

        include_domains = params.get("include_domains", FBREF_SEARCH_DOMAINS)
        max_results = params.get("max_results", 5)

        result = await self._search.search(
            query=query,
            include_domains=include_domains,
            max_results=max_results,
        )

        raw_text = str(result)
        raw_bytes = len(raw_text.encode("utf-8"))
        urls = [r.get("url", "") for r in result.get("results", [])] if isinstance(result, dict) else []

        return result if isinstance(result, dict) else {"results": []}, raw_bytes, urls