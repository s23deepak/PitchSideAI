"""
Historical Context Agent - Build narrative context and historical patterns.

Gathers head-to-head history, key storylines, and historical moments to provide
rich narrative context for match commentary.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_brightdata_mcp_retriever, get_football_data_retriever, get_retriever, get_search_service
from quality.evidence import filter_allowed_search_results

logger = logging.getLogger(__name__)


class HistoricalContextAgent(BaseAgent):
    """Build historical context and narrative arcs."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        football_data_retriever: Optional[Any] = None,
        search_service: Optional[Any] = None,
    ):
        """Initialize historical context agent."""
        super().__init__(
            model_id=model_id,
            sport=sport,
            agent_type="historical_context",
        )
        self.cache = cache or DataCache(ttl_seconds=86400)  # 24 hours for historical data
        self.football_data = football_data_retriever or get_football_data_retriever(cache=self.cache)
        self.search_service = search_service or get_search_service(cache=self.cache)
        self.retriever = get_retriever(self.sport, cache=self.cache)

    async def execute(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Execute full historical context analysis."""
        return await self.build_match_narrative(home_team, away_team)

    async def build_match_narrative(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Build comprehensive historical narrative for the matchup.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            Historical context with H2H, storylines, narratives
        """
        start_time = datetime.utcnow()

        # Gather historical data in parallel
        h2h_history, storylines = await asyncio.gather(
            self.get_head_to_head_history(home_team, away_team),
            self.identify_key_storylines(home_team, away_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="historical_context_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "h2h_matches": len(h2h_history.get("recent_matches", [])),
                "storylines": len(storylines),
                "duration_ms": duration_ms,
            },
        )

        if h2h_history.get("status") == "unavailable" and not storylines:
            narrative = ""
        else:
            # Synthesize into narrative with missing facts called out explicitly.
            h2h_record = (
                "Unavailable from trusted sources"
                if h2h_history.get("status") == "unavailable"
                else f"{h2h_history.get('team1_wins', 0)}-{h2h_history.get('draws', 0)}-{h2h_history.get('team2_wins', 0)} (W-D-L)"
            )
            narrative_prompt = f"""As an elite {self.sport} analyst, create a concise match narrative for {home_team} vs {away_team}.

Head-to-Head Record: {h2h_record}
Total Matches: {h2h_history.get('total_matches') if h2h_history.get('status') != 'unavailable' else 'Unavailable'}

Recent H2H Results:
{self._format_h2h(h2h_history.get('recent_matches', []))}

Key Storylines:
{self._format_storylines(storylines)}

Provide:
1. Historical context (rivalry significance, pattern)
2. Current storyline narrative
3. Expected dynamic based on history
4. Notable H2H trends

Keep to 3-4 sentences. Do not invent head-to-head numbers when the record is unavailable."""

            narrative = await self.call_llm(
                prompt=narrative_prompt,
                temperature=0.4,
                max_tokens=150,
            )

        return {
            "h2h_history": h2h_history,
            "storylines": storylines,
            "narrative": narrative,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_head_to_head_history(
        self,
        team1: str,
        team2: str,
        matches: int = 10,
    ) -> Dict[str, Any]:
        """
        Get H2H historical data between teams from football-data.org.

        Args:
            team1: First team
            team2: Second team
            matches: Number of recent H2H to fetch

        Returns:
            H2H record and match details
        """
        h2h_data = {}

        # Try football-data.org for H2H
        if self.football_data and self.football_data.is_available:
            try:
                try:
                    h2h_data = await self.football_data.get_head_to_head(
                        team1,
                        team2,
                        limit=matches,
                    )
                except TypeError:
                    h2h_data = await self.football_data.get_head_to_head(team1, team2)
            except Exception as exc:
                logger.warning("Football-data H2H failed for %s vs %s: %s", team1, team2, exc)

        if not h2h_data:
            h2h_data = {
                "status": "unavailable",
                "total_matches": None,
                "team1_wins": None,
                "team2_wins": None,
                "draws": None,
                "recent_results": [],
                "note": "Trusted H2H data unavailable in this run",
            }

        # Analyze patterns from H2H data
        recent_matches = h2h_data.get("recent_results", [])
        patterns = self._analyze_h2h_patterns(recent_matches)

        return {
            "home_team": team1,
            "away_team": team2,
            "status": h2h_data.get("status", "accepted"),
            "total_matches": h2h_data.get("total_matches"),
            "team1_wins": h2h_data.get("team1_wins"),
            "team2_wins": h2h_data.get("team2_wins"),
            "draws": h2h_data.get("draws"),
            "recent_matches": recent_matches,
            "patterns": patterns,
            "note": h2h_data.get("note", ""),
        }

    async def identify_key_storylines(
        self,
        home_team: str,
        away_team: str,
    ) -> List[Dict[str, str]]:
        """
        Identify compelling narrative elements via web search.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            List of storyline objects from real sources
        """
        storylines = []

        # Search for match storylines via Tavily
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search_match_storylines(
                    home_team, away_team, self.sport
                )
                if search_result.get("results"):
                    accepted_results, rejected = filter_allowed_search_results(
                        search_result.get("results", []),
                        home_team=home_team,
                        away_team=away_team,
                        topic="storylines",
                        max_results=3,
                    )
                    brightdata = get_brightdata_mcp_retriever()
                    scrape_result = await brightdata.scrape_search_results(
                        accepted_results,
                        home_team=home_team,
                        away_team=away_team,
                        topic="storylines",
                        limit=2,
                    )
                    scraped_by_url = {
                        item.get("url"): item
                        for item in scrape_result.get("scraped", [])
                        if item.get("url")
                    }
                    # Convert accepted search results into storyline format.
                    for result in accepted_results:
                        scraped = scraped_by_url.get(result.get("url"), {})
                        storylines.append({
                            "type": "news",
                            "title": result.get("title", ""),
                            "description": (scraped.get("content") or result.get("content", ""))[:300],
                            "source": result.get("source", ""),
                            "url": result.get("url", ""),
                            "data_source": "brightdata_mcp" if scraped else "tavily_search",
                        })
                    if rejected or scrape_result.get("degraded"):
                        logger.info(
                            "Rejected %s polluted storyline candidates for %s vs %s",
                            len(rejected) + len(scrape_result.get("degraded", [])),
                            home_team,
                            away_team,
                        )
            except Exception as exc:
                logger.warning("Tavily storylines search failed: %s", exc)

        return storylines

    def _format_h2h(self, matches: List[Dict[str, Any]]) -> str:
        """Format H2H matches for prompt."""
        if not matches:
            return "Limited H2H history"

        formatted = []
        for match in matches[:5]:  # Last 5 matches
            date = match.get('date', 'Unknown date')
            score = match.get('score', '?-?')
            home = match.get('home', '')
            away = match.get('away', '')
            formatted.append(f"- {date}: {home} {score} {away}")
        return "\n".join(formatted)

    def _format_storylines(self, storylines: List[Dict[str, str]]) -> str:
        """Format storylines for prompt."""
        formatted = []
        for story in storylines:
            formatted.append(f"- {story.get('title', 'Unknown')}: {story.get('description', '')}")
        return "\n".join(formatted) or "No major storylines"

    def _analyze_h2h_patterns(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in H2H history."""
        if not matches:
            return {"pattern": "Limited historical data", "consistency": "Unknown"}

        winners = [m.get("winner") for m in matches if m.get("winner") and m.get("winner") != "Draw"]
        draws = sum(1 for m in matches if m.get("winner") == "Draw")

        total = len(matches)
        if total > 0:
            if draws >= total / 3:
                trend = "Highly competitive"
            elif winners and len(set(winners)) == 1:
                trend = "One-sided"
            else:
                trend = "Balanced"
        else:
            trend = "Unknown"

        return {
            "pattern": trend,
            "competitiveness": "High" if draws >= total / 3 else "Low",
        }

    async def close(self):
        """Clean up resources."""
        pass
