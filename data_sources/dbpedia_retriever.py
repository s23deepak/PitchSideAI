"""
DBpedia Retriever — SPARQL query execution with structured knowledge extraction.

Uses DBpedia's public SPARQL endpoint for structured facts about players,
teams, stadiums, and competitions. Falls back to Wikipedia when SPARQL
returns no results.
"""
from __future__ import annotations

from typing import Any

import httpx

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

DBPEDIA_SPARQL_ENDPOINT = "https://dbpedia.org/sparql"
DBPEDIA_TIMEOUT = 15


class DbpediaRetriever(BaseRetriever):
    def __init__(self, cache=None):
        super().__init__(
            source_name="dbpedia",
            source_tier=get_source_tier("dbpedia"),
            rate_limiter=RateLimiter(requests_per_minute=60),
            cache=cache,
        )

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        sparql_query = params.get("sparql", query)
        format_type = params.get("format", "json")

        async with httpx.AsyncClient(timeout=DBPEDIA_TIMEOUT) as client:
            resp = await client.get(
                DBPEDIA_SPARQL_ENDPOINT,
                params={"query": sparql_query, "format": format_type},
                headers={"Accept": "application/sparql-results+json"},
            )
            raw_text = resp.text
            raw_bytes = len(raw_text.encode("utf-8"))

            if resp.status_code != 200:
                return {"error": f"SPARQL query failed: {resp.status_code}"}, raw_bytes, []

            try:
                data = resp.json()
            except Exception:
                data = {"raw": raw_text[:1000]}

            return data, raw_bytes, [DBPEDIA_SPARQL_ENDPOINT]