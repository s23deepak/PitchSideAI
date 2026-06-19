"""
Round-robin source router with automatic failover.

Routes queries through data sources in priority order:
- Skips degraded sources (consecutive failures)
- Falls through sources that return is_bad
- Returns the first good result or the best marginal one
"""
from __future__ import annotations

from typing import Any

from core.source_health import get_source_health_registry
from core.retrieval_ledger import get_ledger
from data_sources.result import FetchResult


class RoundRobinRouter:
    """Routes queries through sources in priority order with automatic failover."""

    def __init__(
        self,
        sources: list[tuple[str, Any]],
        run_id: str,
        agent_name: str,
    ):
        """
        Args:
            sources: List of (source_name, retriever_instance) in priority order.
                     Each retriever must have an async fetch() method returning FetchResult.
            run_id: Current run identifier for ledger logging.
            agent_name: Name of the agent making the request.
        """
        self._sources = sources
        self._run_id = run_id
        self._agent_name = agent_name
        self._index = 0
        self._failed_sources: list[str] = []
        self._health = get_source_health_registry()
        self._ledger = get_ledger()

    async def fetch_with_fallback(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        max_sources: int = 3,
    ) -> FetchResult:
        """
        Try sources in order. Skip degraded ones. Stop at first good result.

        Returns the best result found or the last failure wrapped as FetchResult.empty().
        """
        params = params or {}
        results: list[FetchResult] = []
        attempted = 0

        for source_name, retriever in self._sources:
            if attempted >= max_sources:
                break

            health = self._health.get(source_name)
            if health and health.is_degraded:
                self._failed_sources.append(source_name)
                continue

            try:
                result = await retriever.fetch(
                    query=query,
                    params=params,
                    run_id=self._run_id,
                    agent_name=self._agent_name,
                )
            except Exception as exc:
                result = FetchResult.empty(
                    source_name=source_name,
                    status="error",
                )
                result.error_message = str(exc)

            results.append(result)
            attempted += 1

            if result.is_good:
                return result

            if result.is_bad:
                self._failed_sources.append(source_name)

        best = max(results, key=lambda r: r.completeness) if results else None
        return best or FetchResult.empty(source_name="round_robin_fallback")

    @property
    def failed_sources(self) -> list[str]:
        return list(self._failed_sources)