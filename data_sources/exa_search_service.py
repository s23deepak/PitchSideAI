"""Exa search integration for evidence-first commentary notes."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from data_sources.cache import DataCache
from data_sources.retrieval_audit import audit_retrieval, monotonic_ms, get_audit_run_id
from core.retrieval_ledger import get_ledger
from core.source_catalog import get_source_tier


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
        self._ledger = get_ledger()

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
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="targeted_evidence",
                agent_name="exa_search",
                source_name="exa",
                source_tier=get_source_tier("exa"),
                query_text=query,
                query_params={
                    "topic": topic,
                    "search_type": search_type,
                    "max_results": max_results,
                    "include_domains": include_domains if include_domains else [],
                },
                duration_ms=0,
                response_bytes=len(str(cached)),
                status="success",
                data_completeness=0.9,
                data_quality=0.9,
                cache_hit=True,
            )
            return {**cached, "source": "cache"}

        if not self.is_available:
            result = self._empty(query, topic, source="unavailable")
            self.cache.set(cache_namespace, cache_key, result)
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="targeted_evidence",
                agent_name="exa_search",
                source_name="exa",
                source_tier=get_source_tier("exa"),
                query_text=query,
                query_params={
                    "topic": topic,
                    "search_type": search_type,
                    "max_results": max_results,
                    "include_domains": include_domains if include_domains else [],
                },
                duration_ms=0,
                response_bytes=0,
                status="empty",
                error_message="EXA_API_KEY not configured",
                data_completeness=0.0,
                data_quality=0.0,
            )
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
            response = await asyncio.to_thread(self._post_search_with_domain_retry, body)
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
            duration_ms = int(monotonic_ms() - start_ms)
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="targeted_evidence",
                agent_name="exa_search",
                source_name="exa",
                source_tier=get_source_tier("exa"),
                query_text=query,
                query_params={"topic": topic, "search_type": search_type, "max_results": max_results},
                duration_ms=duration_ms,
                response_bytes=len(str(result)),
                status="success",
                data_completeness=0.8,
                data_quality=0.8,
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
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="targeted_evidence",
                agent_name="exa_search",
                source_name="exa",
                source_tier=get_source_tier("exa"),
                query_text=query,
                query_params={"topic": topic, "search_type": search_type, "max_results": max_results},
                duration_ms=int(monotonic_ms() - start_ms),
                response_bytes=0,
                status="error",
                error_message=str(exc),
                data_completeness=0.0,
                data_quality=0.0,
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

    def _post_search_with_domain_retry(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._post_search(body)
        except httpx.HTTPStatusError as exc:
            blocked_domains = self._blocked_domains_from_response(exc.response)
            include_domains = body.get("includeDomains")
            if exc.response.status_code != 403 or not blocked_domains or not isinstance(include_domains, list):
                raise
            allowed_domains = [
                domain for domain in include_domains
                if str(domain).lower() not in blocked_domains
            ]
            if len(allowed_domains) == len(include_domains):
                raise
            retry_body = {**body}
            if allowed_domains:
                retry_body["includeDomains"] = allowed_domains
            else:
                retry_body.pop("includeDomains", None)
            logger.info(
                "Retrying Exa search without unavailable domains: %s",
                ", ".join(sorted(blocked_domains)),
            )
            return self._post_search(retry_body)

    @staticmethod
    def _blocked_domains_from_response(response: httpx.Response) -> set[str]:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict) and payload.get("tag") != "SOURCE_NOT_AVAILABLE":
            return set()
        error_text = str(payload.get("error") if isinstance(payload, dict) else response.text)
        match = re.search(
            r"requested domains are not available:\s*(.*?)(?:\.\s*Remove|\.$|$)",
            error_text,
            re.I,
        )
        if not match:
            return set()
        return {
            domain.strip().lower()
            for domain in re.split(r",|\band\b", match.group(1))
            if domain.strip()
        }

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
