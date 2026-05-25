"""BrightData remote MCP retrieval for trusted commentary evidence."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

from config import BRIGHTDATA_MCP_BASE_URL, BRIGHTDATA_MCP_GROUPS, BRIGHTDATA_MCP_TOKEN
from data_sources.retrieval_audit import audit_retrieval
from quality.evidence import filter_allowed_search_results, is_allowed_url, validate_scraped_content

logger = logging.getLogger(__name__)


def build_brightdata_mcp_url(
    token: str,
    *,
    base_url: str = BRIGHTDATA_MCP_BASE_URL,
    groups: str = BRIGHTDATA_MCP_GROUPS,
) -> str:
    """Build the remote MCP endpoint. Callers must not log the returned URL."""
    params = {"token": token, "groups": groups}
    return f"{base_url.rstrip('/')}?{urlencode(params)}"


def redact_brightdata_mcp_url(url: str) -> str:
    """Return a log-safe BrightData MCP endpoint."""
    if "token=" not in url:
        return url
    prefix, rest = url.split("token=", 1)
    suffix = ""
    if "&" in rest:
        _, suffix = rest.split("&", 1)
        suffix = f"&{suffix}"
    return f"{prefix}token=[REDACTED]{suffix}"


class BrightDataMcpRetriever:
    """Controlled scraper for already-approved source URLs.

    BrightData is deliberately downstream of source selection. This retriever
    refuses unapproved domains and returns degraded metadata instead of trying
    to answer broad web questions itself.
    """

    TOOL_PREFERENCE = ("scrape_as_markdown", "extract", "scrape_batch", "scrape_as_html")

    def __init__(
        self,
        *,
        token: str = BRIGHTDATA_MCP_TOKEN,
        base_url: str = BRIGHTDATA_MCP_BASE_URL,
        groups: str = BRIGHTDATA_MCP_GROUPS,
        timeout: float = 45.0,
    ) -> None:
        self.token = token or ""
        self.base_url = base_url
        self.groups = groups
        self.timeout = timeout

    @property
    def is_available(self) -> bool:
        return bool(self.token)

    @property
    def endpoint(self) -> str:
        return build_brightdata_mcp_url(self.token, base_url=self.base_url, groups=self.groups)

    @property
    def redacted_endpoint(self) -> str:
        return redact_brightdata_mcp_url(self.endpoint) if self.token else self.base_url

    async def scrape_url(
        self,
        url: str,
        *,
        topic: str = "general",
        home_team: str = "",
        away_team: str = "",
    ) -> dict[str, Any]:
        start = time.perf_counter()
        params = {"url": url, "endpoint": self.redacted_endpoint, "topic": topic}
        if not self.is_available:
            result = self._degraded(url, "missing_brightdata_mcp_token")
            await audit_retrieval(
                provider="brightdata_mcp",
                method="scrape_url",
                params=params,
                result=result,
                duration_ms=self._elapsed_ms(start),
            )
            return result
        if not is_allowed_url(url):
            result = self._degraded(url, "domain_not_allowed")
            await audit_retrieval(
                provider="brightdata_mcp",
                method="scrape_url",
                params=params,
                result=result,
                duration_ms=self._elapsed_ms(start),
            )
            return result

        try:
            content, tool_name = await self._call_scrape_tool(url)
            validation_status, reason = validate_scraped_content(
                content,
                url=url,
                home_team=home_team,
                away_team=away_team,
            )
            result = {
                "url": url,
                "source_url": url,
                "source": "BrightData MCP",
                "data_source": "brightdata_mcp",
                "tool_name": tool_name,
                "content": content[:6000],
                "validation_status": validation_status,
                "reason": reason,
            }
            await audit_retrieval(
                provider="brightdata_mcp",
                method="scrape_url",
                params=params,
                result=result,
                duration_ms=self._elapsed_ms(start),
            )
            return result
        except Exception as exc:
            logger.warning("BrightData MCP scrape failed for allowed URL %s: %s", url, exc)
            result = self._degraded(url, "brightdata_scrape_failed", str(exc))
            await audit_retrieval(
                provider="brightdata_mcp",
                method="scrape_url",
                params=params,
                result=result,
                error=exc,
                duration_ms=self._elapsed_ms(start),
            )
            return result

    async def scrape_search_results(
        self,
        results: list[dict[str, Any]],
        *,
        home_team: str,
        away_team: str,
        topic: str,
        limit: int = 2,
    ) -> dict[str, Any]:
        accepted, rejected = filter_allowed_search_results(
            results,
            home_team=home_team,
            away_team=away_team,
            topic=topic,
            max_results=limit,
        )
        scraped = []
        degraded = []
        for candidate in accepted:
            scraped_item = await self.scrape_url(
                str(candidate.get("url") or ""),
                topic=topic,
                home_team=home_team,
                away_team=away_team,
            )
            if scraped_item.get("validation_status") == "accepted":
                scraped.append({**candidate, **scraped_item})
            else:
                degraded.append(scraped_item)
        return {
            "accepted_candidates": accepted,
            "scraped": scraped,
            "rejected_evidence": [item.to_dict() for item in rejected],
            "degraded": degraded,
            "available": self.is_available,
        }

    async def _call_scrape_tool(self, url: str) -> tuple[str, str]:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError("mcp package is not installed") from exc

        async with streamablehttp_client(self.endpoint, timeout=self.timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tool_name = self._select_tool([getattr(tool, "name", "") for tool in tools_result.tools])
                result = await self._call_tool_with_fallbacks(session, tool_name, url)
        return self._extract_text(result), tool_name

    async def _call_tool_with_fallbacks(self, session: Any, tool_name: str, url: str) -> Any:
        argument_variants = (
            {"url": url},
            {"urls": [url]},
            {"target_url": url},
            {"url": url, "format": "markdown"},
        )
        last_exc: Exception | None = None
        for arguments in argument_variants:
            try:
                return await session.call_tool(tool_name, arguments)
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"BrightData MCP tool {tool_name} rejected supported URL arguments") from last_exc

    def _select_tool(self, tool_names: list[str]) -> str:
        names = [name for name in tool_names if name]
        for preferred in self.TOOL_PREFERENCE:
            if preferred in names:
                return preferred
        for name in names:
            if "scrape" in name or "extract" in name:
                return name
        raise RuntimeError("BrightData MCP did not expose a scraping tool")

    def _extract_text(self, result: Any) -> str:
        chunks: list[str] = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                chunks.append(str(text))
            elif isinstance(item, dict):
                chunks.append(str(item.get("text") or item))
        if chunks:
            return "\n".join(chunks)
        return str(result)

    def _degraded(self, url: str, reason: str, error: str = "") -> dict[str, Any]:
        return {
            "url": url,
            "source_url": url,
            "source": "BrightData MCP",
            "data_source": "brightdata_mcp",
            "content": "",
            "validation_status": "degraded",
            "reason": reason,
            "error": error,
        }

    def _elapsed_ms(self, start: float) -> float:
        return (time.perf_counter() - start) * 1000
