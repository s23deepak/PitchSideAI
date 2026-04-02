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
from data_sources import ESPNDataRetriever, WikipediaRetriever, DataCache

logger = logging.getLogger(__name__)


class HistoricalContextAgent(BaseAgent):
    """Build historical context and narrative arcs."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
    ):
        """Initialize historical context agent."""
        super().__init__(
            model_id=model_id,
            sport=sport,
            agent_type="historical_context",
        )
        self.cache = cache or DataCache(ttl_seconds=86400)  # 24 hours for historical data
        self.espn_retriever = ESPNDataRetriever(cache=self.cache)
        self.wiki_retriever = WikipediaRetriever(cache=self.cache)

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
        narrative_prompt = f"""Create a compelling match narrative for {home_team} vs {away_team}:

Historical Record: {h2h_history.get('total_record', 'Unknown')}

Recent H2H:
{self._format_h2h(h2h_history.get('recent_matches', []))}

Key Storylines:
{self._format_storylines(storylines)}

Provide:
1. Historical context (rivalry, tradition, significance)
2. Current storyline (what makes THIS match special)
3. Redemption/Revenge Arcs (if applicable)
4. Expected Drama (based on history)

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
        Get H2H historical data between teams.

        Args:
            team1: First team
            team2: Second team
            matches: Number of recent H2H to fetch

        Returns:
            H2H record and match details
        """
        h2h_data = await self.espn_retriever.get_head_to_head(
            team1,
            team2,
            self.sport,
        )

        # Analyze patterns
        recent_matches = h2h_data.get("recent_matches", [])
        patterns = self._analyze_h2h_patterns(recent_matches)

        return {
            "home_team": team1,
            "away_team": team2,
            "total_record": h2h_data.get("total_record", "Unknown"),
            "recent_matches": recent_matches,
            "patterns": patterns,
            "historical_trend": h2h_data.get("patterns", "No clear pattern"),
        }

    async def identify_key_storylines(
        self,
        home_team: str,
        away_team: str,
    ) -> List[Dict[str, str]]:
        """
        Identify compelling narrative elements.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            List of storyline objects
        """
        storylines = []

        # Generic storylines (in production, would pull from sports news APIs)
        potential_storylines = [
            {
                "type": "rivalry",
                "title": f"Classic {home_team} vs {away_team} rivalry",
                "description": "Two historic rivals meet again in crucial encounter",
            },
            {
                "type": "redemption",
                "title": "Revenge match",
                "description": f"{away_team} looking to avenge recent loss to {home_team}",
            },
            {
                "type": "milestone",
                "title": "Historic occasion",
                "description": "Important match for both sides' respective campaigns",
            },
        ]

        return potential_storylines[:2]  # Return top 2 storylines

    def _format_h2h(self, matches: List[Dict[str, Any]]) -> str:
        """Format H2H matches for prompt."""
        formatted = []
        for match in matches[:5]:  # Last 5 matches
            formatted.append(
                f"- {match.get('date', 'Unknown')}: {match.get('result', 'Unknown')} "
                f"({match.get('key_moment', 'Decisive moment')})"
            )
        return "\n".join(formatted) or "Limited H2H history"

    def _format_storylines(self, storylines: List[Dict[str, str]]) -> str:
        """Format storylines for prompt."""
        formatted = []
        for story in storylines:
            formatted.append(f"- {story.get('title', 'Unknown')}: {story.get('description', '')}")
        return "\n".join(formatted) or "No major storylines"

    def _analyze_h2h_patterns(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in H2H history."""
        if not matches:
            return {"pattern": "Limited historical data"}

        # Count outcomes
        wins = sum(1 for m in matches if "W" in m.get("result", ""))
        draws = sum(1 for m in matches if "D" in m.get("result", ""))

        trend = "Competitive" if wins == draws else "Dominated" if wins > draws else "Under pressure"

        return {
            "pattern": trend,
            "consistency": "High" if len(set(m.get("result", "") for m in matches)) < 2 else "Variable",
        }

    async def close(self):
        """Clean up resources."""
        await self.espn_retriever.close()
        await self.wiki_retriever.close()
