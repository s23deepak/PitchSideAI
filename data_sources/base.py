"""
Base Retriever Interface — PitchSideAI
Two interfaces:

1. RetrieverProtocol — domain-specific structural interface with 7 async methods
   (get_match_context, get_team_squad, get_recent_form, get_player_stats,
    get_head_to_head, get_team_news, get_injuries)

2. BaseRetriever (ABC) — fetch infrastructure base for every data source.
   Every concrete retriever inherits from this ABC and implements fetch().
   The fetch() template method handles: cache → rate limit → HTTP call →
   response scoring → ledger logging → return FetchResult.
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Protocol

from core.retrieval_ledger import get_ledger
from core.data_cache import DataCache
from core.source_health import get_source_health_registry
from core.source_catalog import get_source_tier
from quality.response_scorer import score_response
from data_sources.result import FetchResult
from data_sources.rate_limiter import RateLimiter
from data_sources.retrieval_audit import get_audit_run_id

logger = logging.getLogger(__name__)


class RetrieverProtocol(Protocol):
    """Domain-specific data retriever interface — what agents call."""

    async def get_match_context(self, team_name: str, sport: str) -> Dict[str, Any]:
        """Fetch exact datetime and venue for the active match."""
        ...

    async def get_team_squad(self, team_name: str, sport: str) -> Dict[str, Any]:
        """Fetch squad roster with key stats."""
        ...

    async def get_recent_form(self, team_name: str, sport: str, num_games: int = 5) -> Dict[str, Any]:
        """Fetch recent W/D/L form and goals/points."""
        ...

    async def get_player_stats(self, player_name: str, team_name: str, sport: str) -> Dict[str, Any]:
        """Fetch individual player statistics."""
        ...

    async def get_head_to_head(self, home_team: str, away_team: str, sport: str) -> Dict[str, Any]:
        """Fetch historical H2H record."""
        ...

    async def get_team_news(self, team_name: str, sport: str) -> List[Dict[str, Any]]:
        """Fetch recent news articles."""
        ...

    async def get_injuries(self, team_name: str, sport: str) -> List[Dict[str, Any]]:
        """Fetch current injury status for players."""
        ...


class BaseRetriever(ABC):
    """Every data source has: fetch → log → score → return

    Concrete retrievers implement _do_fetch() for the actual HTTP call.
    The template method fetch() handles caching, rate limiting, response
    scoring, and ledger logging automatically.
    """

    source_name: str
    source_tier: int
    rate_limiter: Optional[RateLimiter] = None

    def __init__(
        self,
        source_name: str,
        source_tier: int | None = None,
        rate_limiter: RateLimiter | None = None,
        cache: DataCache | None = None,
    ):
        self.source_name = source_name
        self.source_tier = source_tier if source_tier is not None else get_source_tier(source_name)
        self.rate_limiter = rate_limiter
        self._cache = cache or DataCache()
        self._ledger = get_ledger()
        self._health = get_source_health_registry()

    async def fetch(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        run_id: str = "",
        agent_name: str = "",
        phase: str = "parallel_gather",
    ) -> FetchResult:
        """Template method — all fetches flow through here.

        1. Check cache
        2. Acquire rate limit slot
        3. Make the actual HTTP call (via _do_fetch())
        4. Score the response
        5. Log to ledger + source health registry
        6. Return FetchResult
        """
        params = params or {}
        run_id = run_id or get_audit_run_id()
        cache_key = f"{self.source_name}|{query}|{str(sorted(params.items()))}"

        cached = self._cache.get(self.source_name, cache_key)
        if cached is not None:
            if isinstance(cached, FetchResult):
                cached.cache_hit = True
                return cached
            return FetchResult(
                data=cached,
                raw_bytes=len(str(cached)),
                status="success",
                source_name=self.source_name,
                source_tier=self.source_tier,
                cache_hit=True,
                completeness=0.9,
                quality=0.9,
            )

        if self.rate_limiter:
            await self.rate_limiter.acquire()

        start_ms = int(time.monotonic() * 1000)
        try:
            raw_data, raw_bytes, source_urls = await self._do_fetch(query, params)
            duration_ms = int(time.monotonic() * 1000) - start_ms

            extracted_fields = self._extract_fields(raw_data)
            completeness, quality = score_response(
                response_bytes=raw_bytes,
                extracted_fields=extracted_fields,
                status="success",
                source_tier=self.source_tier,
            )

            result = FetchResult(
                data=raw_data,
                raw_bytes=raw_bytes,
                status="success",
                source_name=self.source_name,
                source_tier=self.source_tier,
                duration_ms=duration_ms,
                completeness=completeness,
                quality=quality,
                source_urls=source_urls,
                placeholder_count=extracted_fields.get("placeholder_count", 0),
                extracted_fields=extracted_fields,
            )

            self._ledger.log_fetch(
                run_id=run_id,
                phase=phase,
                agent_name=agent_name,
                source_name=self.source_name,
                source_tier=self.source_tier,
                query_text=query,
                query_params=params,
                duration_ms=duration_ms,
                response_bytes=raw_bytes,
                status="success",
                data_completeness=completeness,
                data_quality=quality,
                placeholder_count=extracted_fields.get("placeholder_count", 0),
                extracted_fields=extracted_fields,
                source_urls=source_urls,
                cache_hit=False,
            )

            self._health.record_fetch(
                source_name=self.source_name,
                success=True,
                duration_ms=duration_ms,
                response_bytes=raw_bytes,
                completeness=completeness,
                quality=quality,
            )

            self._cache.set(self.source_name, cache_key, result, ttl=self._cache._default_ttl)
            return result

        except Exception as exc:
            duration_ms = int(time.monotonic() * 1000) - start_ms
            error_msg = str(exc)

            status = "error"
            if "timeout" in error_msg.lower():
                status = "timeout"
            elif "rate" in error_msg.lower() and ("limit" in error_msg.lower() or "throttl" in error_msg.lower()):
                status = "rate_limited"
            elif "block" in error_msg.lower() or "403" in error_msg:
                status = "blocked"

            result = FetchResult(
                data={},
                raw_bytes=0,
                status=status,
                error_message=error_msg,
                source_name=self.source_name,
                source_tier=self.source_tier,
                duration_ms=duration_ms,
                completeness=0.0,
                quality=0.0,
            )

            self._ledger.log_fetch(
                run_id=run_id,
                phase=phase,
                agent_name=agent_name,
                source_name=self.source_name,
                source_tier=self.source_tier,
                query_text=query,
                query_params=params,
                duration_ms=duration_ms,
                response_bytes=0,
                status=status,
                error_message=error_msg,
                data_completeness=0.0,
                data_quality=0.0,
                cache_hit=False,
            )

            self._health.record_fetch(
                source_name=self.source_name,
                success=False,
                duration_ms=duration_ms,
                response_bytes=0,
                completeness=0.0,
                quality=0.0,
            )

            return result

    @abstractmethod
    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        """Execute the actual HTTP call / scrape.

        Returns:
            (raw_data_dict, raw_bytes_int, source_urls_list)
        """
        ...

    def _extract_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract structured fields from raw data for scoring."""
        placeholder_count = 0
        for value in data.values():
            if isinstance(value, str) and value.lower() in {
                "unknown", "tbd", "player 1", "n/a", "unavailable", "[insert]",
            }:
                placeholder_count += 1
            elif isinstance(value, list):
                placeholder_count += sum(
                    1 for v in value
                    if isinstance(v, str) and v.lower() in {
                        "unknown", "tbd", "player 1", "n/a", "unavailable", "[insert]",
                    }
                )

        return {
            "field_count": len(data),
            "placeholder_count": placeholder_count,
            "has_data": len(data) > 0,
        }

    async def health_check(self) -> bool:
        """Quick ping to see if source is reachable."""
        try:
            result = await self.fetch(
                query="health_check",
                params={},
                run_id="health",
                agent_name="system",
                phase="health_check",
            )
            return result.is_good or result.is_marginal
        except Exception:
            return False
