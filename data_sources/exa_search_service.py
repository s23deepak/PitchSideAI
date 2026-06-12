"""Exa search integration for evidence-first commentary notes."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from data_sources.cache import DataCache
from data_sources.retrieval_audit import audit_retrieval, monotonic_ms


logger = logging.getLogger(__name__)


DEFAULT_EXA_SEARCH_URL = "https://api.exa.ai/search"
MONTHLY_TTL_SECONDS = 31 * 24 * 60 * 60


class ExaSearchService:
    """Small async wrapper around Exa search with highlight extraction and caching."""

    def __init__(
        self,
        cache: DataCache | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_EXA_SEARCH_URL,
    ) -> None:
        self.api_key = api_key or os.getenv("EXA_API_KEY") or os.getenv("EXA_API")
        self.base_url = base_url
        self.cache = cache or DataCache(ttl_seconds=MONTHLY_TTL_SECONDS)

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(
        self,
        query: str,
        *,
        topic: str = "general",
        search_type: str = "auto",
        max_results: int = 5,
        include_domains: list[str] | None = None,
        start_published_date: str | None = None,
        cache_namespace: str = "exa",
    ) -> dict[str, Any]:
        """Search Exa and normalize results into the existing search-result shape."""
        include_domains = include_domains or []
        monthly_bucket = datetime.now(timezone.utc).strftime("%Y-%m")
        cache_key = "|".join(
            [
                monthly_bucket,
                query,
                topic,
                search_type,
                str(max_results),
                ",".join(sorted(include_domains)),
                start_published_date or "",
            ]
        )
        cached = self.cache.get(cache_namespace, cache_key)
        if cached:
            return {**cached, "source": "cache"}

        if not self.is_available:
            result = self._empty(query, topic, source="unavailable")
            self.cache.set(cache_namespace, cache_key, result)
            return result

        body: dict[str, Any] = {
            "query": query,
            "type": search_type,
            "numResults": max(1, min(max_results, 10)),
            "contents": {"highlights": True},
        }
        if include_domains:
            body["includeDomains"] = include_domains
        if start_published_date:
            body["startPublishedDate"] = start_published_date

        start_ms = monotonic_ms()
        try:
            response = await asyncio.to_thread(self._post_search, body)
            results = [self._normalize_result(item, topic) for item in response.get("results", [])]
            result = {
                "query": query,
                "topic": topic,
                "results": results,
                "source": "exa",
                "request_id": response.get("requestId", ""),
                "cost_dollars": response.get("costDollars", {}),
            }
            self.cache.set(cache_namespace, cache_key, result)
            await audit_retrieval(
                provider="exa",
                method="search",
                params={
                    "query": query,
                    "topic": topic,
                    "search_type": search_type,
                    "max_results": max_results,
                    "include_domains": include_domains,
                    "start_published_date": start_published_date,
                    "cache_hit": False,
                },
                result=result,
                duration_ms=monotonic_ms() - start_ms,
                source="search_service",
            )
            return result
        except Exception as exc:
            logger.warning("Exa search failed for %s: %s", topic, exc)
            result = self._empty(query, topic, source="error", error=str(exc))
            await audit_retrieval(
                provider="exa",
                method="search",
                params={"query": query, "topic": topic, "search_type": search_type},
                result=result,
                duration_ms=monotonic_ms() - start_ms,
                source="search_service",
            )
            return result

    def _post_search(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.base_url, json=body, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _normalize_result(item: dict[str, Any], topic: str) -> dict[str, Any]:
        highlights = item.get("highlights") if isinstance(item.get("highlights"), list) else []
        content = "\n".join(str(part) for part in highlights if part).strip()
        if not content:
            content = str(item.get("summary") or item.get("text") or "").strip()
        scores = item.get("highlightScores") if isinstance(item.get("highlightScores"), list) else []
        score = max((float(value) for value in scores if isinstance(value, (int, float))), default=0.0)
        return {
            "title": item.get("title") or "",
            "url": item.get("url") or item.get("id") or "",
            "content": content[:2500],
            "published_date": item.get("publishedDate") or "",
            "source": "exa",
            "topic": topic,
            "score": score,
        }

    @staticmethod
    def _empty(query: str, topic: str, *, source: str, error: str = "") -> dict[str, Any]:
        return {
            "query": query,
            "topic": topic,
            "results": [],
            "source": source,
            "error": error,
        }
