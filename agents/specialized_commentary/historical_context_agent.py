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
from data_sources.factory import get_football_data_retriever, get_retriever, get_search_service

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

        # Synthesize into narrative
        narrative_prompt = f"""As an elite {self.sport} analyst, create a compelling match narrative for {home_team} vs {away_team}:

Head-to-Head Record: {h2h_history.get('team1_wins', 0)}-{h2h_history.get('draws', 0)}-{h2h_history.get('team2_wins', 0)} (W-D-L)
Total Matches: {h2h_history.get('total_matches', 0)}

Recent H2H Results:
{self._format_h2h(h2h_history.get('recent_matches', []))}

Key Storylines:
{self._format_storylines(storylines)}

Provide:
1. Historical context (rivalry significance, pattern)
2. Current storyline narrative
3. Expected dynamic based on history
4. Notable H2H trends

Keep to 4-5 sentences focused on storytelling."""

        narrative = await self.call_bedrock(
            prompt=narrative_prompt,
            temperature=0.5,
            max_tokens=175,  # 175 for local dev (350 in production)
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
                h2h_data = await self.football_data.get_head_to_head(
                    team1,
                    team2,
                    limit=matches,
                )
            except Exception as exc:
                logger.warning("Football-data H2H failed for %s vs %s: %s", team1, team2, exc)

        if not h2h_data:
            try:
                espn_h2h = await self.retriever.get_head_to_head(team1, team2, self.sport)
            except Exception as exc:
                logger.warning("ESPN H2H fallback failed for %s vs %s: %s", team1, team2, exc)
                espn_h2h = {}

            h2h_data = {
                "total_matches": 0,
                "team1_wins": espn_h2h.get("home_record", {}).get("wins", 0),
                "team2_wins": espn_h2h.get("away_record", {}).get("wins", 0),
                "draws": espn_h2h.get("home_record", {}).get("draws", 0),
                "recent_results": [],
                "note": espn_h2h.get("note", "Historical record unavailable"),
            }

        # Analyze patterns from H2H data
        recent_matches = h2h_data.get("recent_results", [])
        patterns = self._analyze_h2h_patterns(recent_matches)

        return {
            "home_team": team1,
            "away_team": team2,
            "total_matches": h2h_data.get("total_matches", 0),
            "team1_wins": h2h_data.get("team1_wins", 0),
            "team2_wins": h2h_data.get("team2_wins", 0),
            "draws": h2h_data.get("draws", 0),
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
                    # Convert search results into storyline format
                    for result in search_result.get("results", [])[:3]:
                        storylines.append({
                            "type": "news",
                            "title": result.get("title", ""),
                            "description": result.get("content", "")[:200],
                            "source": result.get("source", ""),
                        })
            except Exception as exc:
                logger.warning("Tavily storylines search failed: %s", exc)

        # Fall back to minimal storylines if search failed
        if not storylines:
            storylines = [
                {
                    "type": "matchup",
                    "title": f"{home_team} vs {away_team}",
                    "description": "Two teams meet in upcoming fixture",
                }
            ]

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

