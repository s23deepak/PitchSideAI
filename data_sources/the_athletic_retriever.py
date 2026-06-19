"""
The Athletic Retriever — deep tactical analysis, long-form journalism.

Uses Tavily/Exa search with theathletic.com domain filtering.
Note: The Athletic is often paywalled; BrightData MCP can be used
as a fallback for paywall content extraction.
"""
from __future__ import annotations

from typing import Any

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

ATHLETIC_SEARCH_DOMAINS = ["theathletic.com"]


class AthleticRetriever(BaseRetriever):
    def __init__(self, cache=None, search_service=None):
        super().__init__(
            source_name="the_athletic",
            source_tier=get_source_tier("the_athletic"),
            rate_limiter=RateLimiter(requests_per_minute=20),
            cache=cache,
        )
        self._search = search_service

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        if self._search is None:
            from data_sources.factory import get_search_service
            self._search = get_search_service()

        include_domains = params.get("include_domains", ATHLETIC_SEARCH_DOMAINS)
        max_results = params.get("max_results", 3)

        result = await self._search.search(
            query=query,
            include_domains=include_domains,
            max_results=max_results,
        )

        raw_text = str(result)
        raw_bytes = len(raw_text.encode("utf-8"))
        urls = [r.get("url", "") for r in result.get("results", [])] if isinstance(result, dict) else []

        return result if isinstance(result, dict) else {"results": []}, raw_bytes, urls