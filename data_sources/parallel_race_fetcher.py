"""
Parallel race fetcher — fire multiple sources simultaneously, take the first good result.

Pattern: Race 2-3 sources for the same query, cancel remaining tasks when
a good result arrives. Falls back to best marginal result if nothing is good.
"""
from __future__ import annotations

import asyncio
from typing import Any

from data_sources.result import FetchResult


class ParallelRaceFetcher:
    """Race multiple sources for the same data — take the first good result."""

    async def race(
        self,
        query: str,
        sources: list[tuple[str, Any]],
        run_id: str,
        agent_name: str,
        params: dict[str, Any] | None = None,
        max_parallel: int = 3,
    ) -> FetchResult:
        """
        Fire all sources at once via asyncio.gather.
        Return the first result that is_good, or the best of any.

        Args:
            query: The search query or data request.
            sources: List of (source_name, retriever_instance) tuples.
            run_id: Current run identifier.
            agent_name: Name of the agent making the request.
            params: Optional extra parameters for the fetch.
            max_parallel: Maximum number of sources to race simultaneously.
        """
        params = params or {}
        candidates = sources[:max_parallel]

        if not candidates:
            return FetchResult.empty(source_name="parallel_race_fallback")

        async def _call_source(source_name: str, retriever: Any) -> tuple[str, FetchResult | None, str | None]:
            try:
                result = await retriever.fetch(
                    query=query,
                    params=params,
                    run_id=run_id,
                    agent_name=agent_name,
                )
                return source_name, result, None
            except Exception as exc:
                return source_name, None, str(exc)

        tasks = [
            asyncio.create_task(_call_source(name, retriever))
            for name, retriever in candidates
        ]

        try:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            results: list[FetchResult] = []
            for task in done:
                try:
                    _, result, _ = task.result()
                    if result is not None:
                        results.append(result)
                except Exception:
                    pass

            good = next((r for r in results if r.is_good), None)
            if good:
                for task in pending:
                    task.cancel()
                return good

            remaining = await asyncio.gather(*pending, return_exceptions=True)
            for item in remaining:
                if isinstance(item, tuple) and len(item) == 3:
                    _, result, _ = item
                    if result is not None:
                        results.append(result)
                elif isinstance(item, FetchResult):
                    results.append(item)
                elif isinstance(item, BaseException):
                    pass

            if results:
                return max(results, key=lambda r: r.completeness)

            return FetchResult.empty(source_name="parallel_race_fallback")
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()