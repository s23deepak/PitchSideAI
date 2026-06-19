"""
Tavily Search Service — Real-time web search for sports data.

Replaces mock data in Wikipedia, Weather, SportsSpecific retrievers by
fetching current information from the web via Tavily AI search API.

Also exposes a LangChain-compatible TavilySearchResults tool path for
integration with LangChain pipelines.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from data_sources.cache import DataCache
from data_sources.retrieval_audit import audit_retrieval, monotonic_ms, get_audit_run_id
from core.retrieval_ledger import get_ledger
from core.source_catalog import get_source_tier

logger = logging.getLogger(__name__)


class TavilySearchService:
    """
    Reusable Tavily web search with caching and graceful fallback.

    Usage:
        svc = TavilySearchService()
        result = await svc.search("Mohamed Salah 2025-26 stats")
        print(result["answer"])   # AI-generated summary
        print(result["results"])  # List of {title, url, content, score}
    """

    def __init__(
        self,
        cache: Optional[DataCache] = None,
        api_key: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.cache = cache or DataCache(ttl_seconds=3600)
        self._client = None          # lazy — tavily.TavilyClient
        self._lc_tool = None         # lazy — langchain_community TavilySearchResults
        self._available: Optional[bool] = None  # None = unchecked
        self._unavailable_reason: str = ""
        self._ledger = get_ledger()

    # ── availability ──────────────────────────────────────────────────────────

    def _ensure_client(self) -> bool:
        """Lazy-init Tavily client. Returns True if ready."""
        if self._available is not None:
            return self._available
        if not self.api_key:
            logger.warning("TAVILY_API_KEY not set — search will use mock fallbacks")
            self._available = False
            return False
        try:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=self.api_key)
            self._available = True
            return True
        except ImportError:
            logger.warning("tavily-python not installed — run: pip install tavily-python")
            self._available = False
            return False
        except Exception as exc:
            logger.error("Tavily client init failed: %s", exc)
            self._available = False
            return False

    def _ensure_lc_tool(self):
        """Lazy-init LangChain TavilySearchResults tool."""
        if self._lc_tool is not None:
            return self._lc_tool
        if not self.api_key:
            return None
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults
            os.environ.setdefault("TAVILY_API_KEY", self.api_key)
            self._lc_tool = TavilySearchResults(max_results=5)
            return self._lc_tool
        except Exception as exc:
            logger.warning("LangChain Tavily tool unavailable: %s", exc)
            return None

    @property
    def is_available(self) -> bool:
        return self._ensure_client()

    # ── core search ───────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        search_depth: str = "basic",   # "basic" or "advanced"
        topic: str = "general",         # "general" or "news"
        max_results: int = 5,
        include_answer: bool = True,
        cache_namespace: str = "tavily",
        include_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a Tavily search with caching.

        Returns:
            {
                "answer":  str,             # AI-generated summary
                "results": List[Dict],      # [{title, url, content, score}]
                "query":   str,
                "source":  "tavily"|"cache"|"fallback"
            }
        """
        include_domains = include_domains or []
        cache_key = f"{query}|{search_depth}|{topic}|{','.join(include_domains)}"
        cached = self.cache.get(cache_namespace, cache_key)
        if cached:
            result = {**cached, "source": "cache"}
            await audit_retrieval(
                provider="tavily",
                method="search",
                params={
                    "query": query,
                    "search_depth": search_depth,
                    "topic": topic,
                    "max_results": max_results,
                    "include_answer": include_answer,
                    "cache_namespace": cache_namespace,
                    "include_domains": include_domains,
                    "cache_hit": True,
                },
                result=result,
                duration_ms=0,
                source="search_service",
            )
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="parallel_gather",
                agent_name="tavily_search",
                source_name="tavily",
                source_tier=get_source_tier("tavily"),
                query_text=query,
                query_params={"search_depth": search_depth, "topic": topic, "max_results": max_results},
                duration_ms=0,
                response_bytes=len(str(result)),
                status="success",
                data_completeness=0.9,
                data_quality=0.9,
                cache_hit=True,
            )
            return result

        if not self._ensure_client():
            result = self._empty(query)
            await audit_retrieval(
                provider="tavily",
                method="search",
                params={
                    "query": query,
                    "search_depth": search_depth,
                    "topic": topic,
                    "max_results": max_results,
                    "include_answer": include_answer,
                    "cache_namespace": cache_namespace,
                    "include_domains": include_domains,
                    "available": False,
                    "unavailable_reason": self._unavailable_reason,
                },
                result=result,
                duration_ms=0,
                source="search_service",
            )
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="parallel_gather",
                agent_name="tavily_search",
                source_name="tavily",
                source_tier=get_source_tier("tavily"),
                query_text=query,
                query_params={"search_depth": search_depth, "topic": topic, "max_results": max_results},
                duration_ms=0,
                response_bytes=0,
                status="empty",
                error_message=self._unavailable_reason,
                data_completeness=0.0,
                data_quality=0.0,
            )
            return result

        start_ms = monotonic_ms()
        try:
            search_kwargs = {
                "query": query,
                "search_depth": search_depth,
                "topic": topic,
                "max_results": max_results,
                "include_answer": include_answer,
            }
            if include_domains:
                search_kwargs["include_domains"] = include_domains
            try:
                response = await asyncio.to_thread(self._client.search, **search_kwargs)
            except TypeError:
                if not include_domains:
                    raise
                search_kwargs.pop("include_domains", None)
                response = await asyncio.to_thread(self._client.search, **search_kwargs)
            result = {
                "answer": response.get("answer", ""),
                "results": response.get("results", []),
                "query": query,
                "source": "tavily",
            }
            self.cache.set(cache_namespace, cache_key, result)
            await audit_retrieval(
                provider="tavily",
                method="search",
                params={
                    "query": query,
                    "search_depth": search_depth,
                    "topic": topic,
                    "max_results": max_results,
                    "include_answer": include_answer,
                    "cache_namespace": cache_namespace,
                    "include_domains": include_domains,
                    "cache_hit": False,
                },
                result=result,
                duration_ms=monotonic_ms() - start_ms,
                source="search_service",
            )
            duration_ms = int(monotonic_ms() - start_ms)
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="parallel_gather",
                agent_name="tavily_search",
                source_name="tavily",
                source_tier=get_source_tier("tavily"),
                query_text=query,
                query_params={"search_depth": search_depth, "topic": topic, "max_results": max_results},
                duration_ms=duration_ms,
                response_bytes=len(str(result)),
                status="success",
                data_completeness=0.8,
                data_quality=0.8,
            )
            return result
        except Exception as exc:
            self._mark_unavailable_if_plan_limited(exc)
            logger.error("Tavily search failed for '%s': %s", query, exc)
            result = self._empty(query)
            await audit_retrieval(
                provider="tavily",
                method="search",
                params={
                    "query": query,
                    "search_depth": search_depth,
                    "topic": topic,
                    "max_results": max_results,
                    "include_answer": include_answer,
                    "cache_namespace": cache_namespace,
                    "include_domains": include_domains,
                    "unavailable_reason": self._unavailable_reason,
                },
                result=result,
                error=exc,
                duration_ms=monotonic_ms() - start_ms,
                source="search_service",
            )
            self._ledger.log_fetch(
                run_id=get_audit_run_id(),
                phase="parallel_gather",
                agent_name="tavily_search",
                source_name="tavily",
                source_tier=get_source_tier("tavily"),
                query_text=query,
                query_params={"search_depth": search_depth, "topic": topic, "max_results": max_results},
                duration_ms=int(monotonic_ms() - start_ms),
                response_bytes=0,
                status="error",
                error_message=str(exc),
                data_completeness=0.0,
                data_quality=0.0,
            )
            return result

    async def search_langchain(
        self,
        query: str,
        cache_namespace: str = "tavily_lc",
    ) -> List[Dict[str, str]]:
        """
        Search via LangChain TavilySearchResults tool.
        Returns list of {url, content} dicts for LangChain pipelines.
        """
        cached = self.cache.get(cache_namespace, query)
        if cached:
            await audit_retrieval(
                provider="tavily",
                method="search_langchain",
                params={"query": query, "cache_namespace": cache_namespace, "cache_hit": True},
                result=cached,
                duration_ms=0,
                source="search_service",
            )
            return cached

        tool = self._ensure_lc_tool()
        if not tool:
            await audit_retrieval(
                provider="tavily",
                method="search_langchain",
                params={
                    "query": query,
                    "cache_namespace": cache_namespace,
                    "available": False,
                    "unavailable_reason": self._unavailable_reason,
                },
                result=[],
                duration_ms=0,
                source="search_service",
            )
            return []

        start_ms = monotonic_ms()
        try:
            results = await asyncio.to_thread(tool.invoke, query)
            if isinstance(results, str):
                results = [{"content": results, "url": ""}]
            self.cache.set(cache_namespace, query, results)
            await audit_retrieval(
                provider="tavily",
                method="search_langchain",
                params={"query": query, "cache_namespace": cache_namespace, "cache_hit": False},
                result=results,
                duration_ms=monotonic_ms() - start_ms,
                source="search_service",
            )
            return results
        except Exception as exc:
            self._mark_unavailable_if_plan_limited(exc)
            logger.error("LangChain Tavily search failed: %s", exc)
            await audit_retrieval(
                provider="tavily",
                method="search_langchain",
                params={
                    "query": query,
                    "cache_namespace": cache_namespace,
                    "unavailable_reason": self._unavailable_reason,
                },
                result=[],
                error=exc,
                duration_ms=monotonic_ms() - start_ms,
                source="search_service",
            )
            return []

    # ── domain-specific helpers ───────────────────────────────────────────────

    async def search_player_bio(
        self, player_name: str, sport: str = "soccer"
    ) -> Dict[str, Any]:
        """Search for player biography, career history, achievements."""
        query = (
            f"{player_name} {sport} player biography career clubs "
            f"nationality statistics trophies"
        )
        return await self.search(
            query,
            search_depth="advanced",
            max_results=3,
            cache_namespace="tavily_player_bio",
        )

    async def search_weather(self, venue: str, match_date: str) -> Dict[str, Any]:
        """Search for weather forecast at a venue for a given date."""
        query = f"weather forecast {venue} {match_date} temperature wind rain"
        return await self.search(
            query,
            topic="news",
            max_results=3,
            cache_namespace="tavily_weather",
        )

    async def search_h2h(
        self, team1: str, team2: str, sport: str = "soccer", include_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Search for head-to-head history between two teams."""
        query = (
            f"{team1} vs {team2} {sport} head to head record "
            f"history recent results 2024 2025 2026"
        )
        return await self.search(
            query,
            search_depth="advanced",
            max_results=5,
            cache_namespace="tavily_h2h",
            include_domains=include_domains,
        )

    async def search_team_tactics(
        self, team_name: str, sport: str = "soccer"
    ) -> Dict[str, Any]:
        """Search for team tactical profile and formation."""
        query = (
            f"{team_name} {sport} formation tactics playing style "
            f"possession press 2025-26 season"
        )
        return await self.search(
            query,
            max_results=3,
            cache_namespace="tavily_tactics",
        )

    async def search_team_news(
        self, team_name: str, sport: str = "soccer", include_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Search for latest team news, injuries, suspensions, transfers."""
        query = (
            f"{team_name} {sport} latest news injury update "
            f"suspension lineup today 2026"
        )
        return await self.search(
            query,
            topic="news",
            max_results=5,
            cache_namespace="tavily_team_news",
            include_domains=include_domains,
        )

    async def search_team_manager(
        self, team_name: str, sport: str = "soccer"
    ) -> Dict[str, Any]:
        """Search for a team's current manager or head coach."""
        query = (
            f"current manager of {team_name} {sport} team head coach now 2026"
        )
        return await self.search(
            query,
            search_depth="advanced",
            topic="news",
            max_results=5,
            cache_namespace="tavily_team_manager",
        )

    async def search_team_signings(
        self, team_name: str, sport: str = "soccer"
    ) -> Dict[str, Any]:
        """Search for recent team signings and transfer arrivals."""
        query = (
            f"{team_name} {sport} recent signings transfer arrivals new players 2026"
        )
        return await self.search(
            query,
            search_depth="advanced",
            topic="news",
            max_results=5,
            cache_namespace="tavily_team_signings",
        )

    async def search_match_storylines(
        self, team1: str, team2: str, sport: str = "soccer", include_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Search for key match storylines and narratives."""
        query = (
            f"{team1} vs {team2} {sport} match preview storylines "
            f"key battles talking points 2026"
        )
        return await self.search(
            query,
            topic="news",
            max_results=5,
            cache_namespace="tavily_storylines",
            include_domains=include_domains,
        )

    async def search_player_matchup(
        self, player1: str, player2: str, sport: str = "soccer"
    ) -> Dict[str, Any]:
        """Search for player vs player matchup history and stats."""
        query = (
            f"{player1} vs {player2} {sport} matchup comparison "
            f"statistics head to head duel"
        )
        return await self.search(
            query,
            max_results=3,
            cache_namespace="tavily_matchup",
        )

    async def search_lineup(
        self, team_name: str, sport: str = "soccer", include_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Search for predicted starting lineup."""
        query = (
            f"{team_name} {sport} predicted starting lineup XI "
            f"team selection latest news today"
        )
        return await self.search(
            query,
            topic="news",
            max_results=3,
            cache_namespace="tavily_lineup",
            include_domains=include_domains,
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _empty(self, query: str) -> Dict[str, Any]:
        """Return empty result when search is unavailable (no fabrication)."""
        return {"answer": "", "results": [], "query": query, "source": "fallback"}

    def _mark_unavailable_if_plan_limited(self, exc: Exception) -> None:
        """Disable further Tavily calls for this service after hard quota failures."""
        text = " ".join(str(part) for part in (exc, getattr(exc, "response", ""), getattr(exc, "args", ""))).lower()
        if any(
            marker in text
            for marker in (
                "plan limit",
                "usage limit",
                "quota",
                "monthly limit",
                "credit limit",
                "insufficient credits",
                "status_code=403",
                "403 forbidden",
            )
        ):
            self._available = False
            self._unavailable_reason = "plan_or_quota_limit"
            logger.warning("Tavily disabled for this run after quota/plan-limit response")
