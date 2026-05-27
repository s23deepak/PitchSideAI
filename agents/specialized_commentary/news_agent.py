"""
News Agent - Gather current team news, injuries, and lineup confirmations.

Fetches latest team news, injury status, and lineup changes for pre-match communication
via Tavily search and structured sports data APIs.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_brightdata_mcp_retriever, get_retriever, get_search_service
from quality.evidence import classify_source_tier, filter_allowed_search_results, preferred_domains_for_topic

logger = logging.getLogger(__name__)


class NewsAgent(BaseAgent):
    """Gather and synthesize team news and updates."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        """Initialize news agent."""
        super().__init__(model_id=model_id, sport=sport, agent_type="news")
        self.cache = cache or DataCache(ttl_seconds=1800)  # 30 min for news
        self.retriever = get_retriever(self.sport, cache=self.cache)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Execute news gathering for both teams."""
        return await self.gather_match_news(home_team, away_team)

    async def gather_match_news(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Gather all news and team updates for match.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            News data (injuries, suspensions, lineup confirmations, late changes)
        """
        start_time = datetime.utcnow()

        # Gather news for both teams in parallel
        home_news, away_news = await asyncio.gather(
            self.get_team_news(home_team, opponent=away_team),
            self.get_team_news(away_team, opponent=home_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="news_gathering_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "news_items": len(
                    home_news.get("news_items", []) + away_news.get("news_items", [])
                ),
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_team": home_news,
            "away_team": away_news,
            "critical_updates": await self._synthesize_critical_updates(
                home_news,
                away_news,
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_team_news(self, team_name: str, opponent: str = "") -> Dict[str, Any]:
        """
        Get comprehensive team news from real sources.

        Args:
            team_name: Team name

        Returns:
            News including injuries, suspensions, latest updates
        """
        espn_news, injuries = await asyncio.gather(
            self.retriever.get_team_news(team_name, self.sport),
            self.retriever.get_injuries(team_name, self.sport),
        )

        news_items = [
            {
                "title": item.get("headline", ""),
                "content": item.get("description", "")[:200],
                "source": "ESPN",
                "url": item.get("url", ""),
            }
            for item in espn_news[:5]
            if item.get("headline")
        ]

        rejected_evidence: list[dict[str, Any]] = []
        if news_items:
            news_items, rejected = filter_allowed_search_results(
                news_items,
                home_team=team_name,
                away_team=opponent,
                topic="team_news",
                max_results=5,
            )
            rejected_evidence.extend(item.to_dict() for item in rejected)
        brightdata_status = {"available": False, "degraded_count": 0, "reason": ""}

        # Fetch team news via Tavily search, then scrape only allowlisted URLs.
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search_team_news(
                    team_name,
                    self.sport,
                    include_domains=preferred_domains_for_topic("team_news"),
                )
                if search_result.get("results"):
                    accepted_results, rejected = filter_allowed_search_results(
                        search_result.get("results", []),
                        home_team=team_name,
                        away_team=opponent,
                        topic="team_news",
                        max_results=4,
                    )
                    rejected_evidence.extend(item.to_dict() for item in rejected)
                    brightdata = get_brightdata_mcp_retriever()
                    scrape_result = await brightdata.scrape_search_results(
                        accepted_results,
                        home_team=team_name,
                        away_team=opponent,
                        topic="team_news",
                        limit=2,
                    )
                    brightdata_status = {
                        "available": scrape_result.get("available", False),
                        "degraded_count": len(scrape_result.get("degraded", [])),
                        "reason": (scrape_result.get("degraded") or [{}])[0].get("reason", ""),
                    }
                    rejected_evidence.extend(scrape_result.get("rejected_evidence", []))

                    scraped_by_url = {
                        item.get("url"): item
                        for item in scrape_result.get("scraped", [])
                        if item.get("url")
                    }
                    tavily_items = [
                        {
                            "title": r.get("title", ""),
                            "content": (scraped_by_url.get(r.get("url"), {}).get("content") or r.get("content", ""))[:500],
                            "source": r.get("source", ""),
                            "url": r.get("url", ""),
                            "source_tier": classify_source_tier(r.get("url", ""), r.get("source", "")),
                            "source_policy_label": r.get("source_policy_label", ""),
                            "published_at": r.get("published_at", r.get("published_date", "")),
                            "data_source": "brightdata_mcp" if r.get("url") in scraped_by_url else "tavily_search",
                            "validation_status": "accepted",
                        }
                        for r in accepted_results
                    ]
                    news_items = self._dedupe_news(news_items + tavily_items)
            except Exception as exc:
                logger.warning("Tavily news search failed for %s: %s", team_name, exc)

        lineup_status = await self._get_lineup_confirmation_status(team_name, opponent)

        # Synthesize into news report
        news_synthesis_prompt = f"""As an elite {self.sport} analyst, create a concise team news summary for {team_name}:

Recent News:
{self._format_news_items(news_items)}

Injuries: {self._format_injuries(injuries)}

Lineup Status: {lineup_status.get('status', 'Unavailable')}

Provide:
1. Key updates affecting team readiness
2. Player availability status
3. Any tactical adjustments expected

Only state injury, readiness, or availability claims when the supplied evidence explicitly says so. If the injury list says it is not verified, do not convert that into "none reported" or "no injuries."

Keep to 3-4 sentences."""

        synthesis = ""
        if news_items or injuries:
            synthesis = await self.call_llm(
                prompt=news_synthesis_prompt,
                temperature=0.2,
                max_tokens=120,
            )

        return {
            "team_name": team_name,
            "news_items": news_items,
            "injuries": injuries,
            "injury_status": {
                "status": "verified" if injuries else "unverified",
                "summary": "" if injuries else "No verified injury report was accepted in this run",
            },
            "lineup_status": lineup_status,
            "last_minute_changes": news_items[0].get("title", "") if news_items else "",
            "synthesis": synthesis,
            "last_updated": datetime.utcnow().isoformat(),
            "data_source": "combined" if news_items or injuries else "unavailable",
            "brightdata_status": brightdata_status,
            "rejected_evidence": rejected_evidence,
        }

    def _format_news_items(self, news_items: List[Dict[str, str]]) -> str:
        """Format news items for prompt."""
        if not news_items:
            return "No recent news available"

        formatted = []
        for item in news_items[:3]:
            title = item.get("title", "")
            if title:
                formatted.append(f"- {title}")
        return "\n".join(formatted) or "No recent news"

    def _format_injuries(self, injuries: List[Dict[str, Any]]) -> str:
        """Format injury list for prompting."""
        if not injuries:
            return "Not verified in this run"
        return ", ".join(
            f"{inj.get('player', 'Unknown')} ({inj.get('status', 'Unavailable')})"
            for inj in injuries[:4]
        )

    async def _get_lineup_confirmation_status(self, team_name: str, opponent: str = "") -> Dict[str, Any]:
        """Infer lineup certainty from web search results."""
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search_lineup(
                    team_name,
                    self.sport,
                    include_domains=preferred_domains_for_topic("lineup"),
                )
                accepted_results, _ = filter_allowed_search_results(
                    search_result.get("results", []) or [],
                    home_team=team_name,
                    away_team=opponent,
                    topic="lineup",
                    max_results=1,
                )
                if not accepted_results:
                    return {"status": "unavailable", "summary": ""}
                answer = (search_result.get("answer") or "").lower()
                if answer:
                    if "confirmed" in answer or "official lineup" in answer:
                        return {"status": "confirmed", "summary": search_result.get("answer", "")[:160]}
                    if "predicted" in answer or "expected" in answer:
                        return {"status": "predicted", "summary": search_result.get("answer", "")[:160]}
                    return {"status": "reported", "summary": search_result.get("answer", "")[:160]}
            except Exception as exc:
                logger.warning("Lineup status search failed for %s: %s", team_name, exc)
        return {"status": "unavailable", "summary": ""}

    def _dedupe_news(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Deduplicate news items by title while preserving order."""
        seen = set()
        deduped = []
        for item in items:
            title = item.get("title", "").strip().lower()
            if not title or title in seen:
                continue
            seen.add(title)
            deduped.append(item)
        return deduped

    async def _synthesize_critical_updates(
        self,
        home_news: Dict[str, Any],
        away_news: Dict[str, Any],
    ) -> List[str]:
        """Extract critical updates from both teams' news."""
        critical = []

        if home_news.get("injuries") or away_news.get("injuries"):
            critical.append("Verified injury absences may affect selection")

        # Check for injury-related keywords
        all_items = home_news.get("news_items", []) + away_news.get("news_items", [])
        for item in all_items:
            content = (item.get("title", "") + " " + item.get("content", "")).lower()
            if any(word in content for word in ["injury", "injured", "out", "doubtful"]):
                critical.append(f"Injury concern: {item.get('title', '')}")
                break

        # Check for suspension keywords
        for item in all_items:
            content = (item.get("title", "") + " " + item.get("content", "")).lower()
            if any(word in content for word in ["suspension", "banned", "suspended"]):
                critical.append(f"Suspension: {item.get('title', '')}")
                break

        return critical[:2]

    async def close(self):
        """Clean up resources."""
        pass
