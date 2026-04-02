"""
News Agent - Gather current team news, injuries, and lineup confirmations.

Fetches latest team news, injury status, suspensions, and lineup changes
for pre-match communication.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_retriever

logger = logging.getLogger(__name__)


class NewsAgent(BaseAgent):
    """Gather and synthesize team news and updates."""

    def __init__(
        self,
        model_id: str = "us.nova-sonic-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
    ):
        """Initialize news agent."""
        super().__init__(model_id=model_id, sport=sport, agent_type="news")
        self.cache = cache or DataCache(ttl_seconds=1800)  # 30 min for news
        self.retriever = get_retriever(self.sport, cache=self.cache)

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
            self.get_team_news(home_team),
            self.get_team_news(away_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="news_gathering_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "injuries_found": len(
                    home_news.get("injuries", []) + away_news.get("injuries", [])
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

    async def get_team_news(self, team_name: str) -> Dict[str, Any]:
        """
        Get comprehensive team news.

        Args:
            team_name: Team name

        Returns:
            News including injuries, suspensions, lineup status
        """
        espn_news_list = await self.retriever.get_team_news(team_name, self.sport)
        headlines = [item.get("headline", "") for item in espn_news_list if isinstance(item, dict)]
        recent_headlines = " | ".join(headlines[:3]) if headlines else "None known"

        # Get lineup status
        lineup_status = await self._get_lineup_confirmation_status(team_name)

        # Get actual injuries from roster instead of news
        injuries = await self.retriever.get_injuries(team_name, self.sport)

        # Synthesize into news report
        news_synthesis_prompt = f"""As an elite {self.sport} analyst, create a concise team news report for {team_name}:

Recent Headlines: {recent_headlines}

Injuries: {self._format_injuries(injuries)}

Suspensions: None known

Late Changes: None known

Lineup Status: {lineup_status.get('status', 'TBD')}

Provide:
1. Key personnel absences impacting team strength
2. Tactical adjustments expected due to absences
3. Expected lineups (if known)

Keep to 3-4 sentences."""

        synthesis = await self.call_bedrock(
            prompt=news_synthesis_prompt,
            temperature=0.2,
            max_tokens=120,  # 120 for local dev (250 in production)
        )

        return {
            "team_name": team_name,
            "injuries": injuries,
            "suspensions": [],
            "last_minute_changes": "None known",
            "lineup_status": lineup_status,
            "synthesis": synthesis,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def _get_lineup_confirmation_status(
        self,
        team_name: str,
    ) -> Dict[str, Any]:
        """Check lineup confirmation status."""
        # In production, would check official team news
        return {
            "status": "pencil_confirmed",
            "confirmed_count": 9,
            "uncertain_count": 2,
            "likely_changes": "Possible rest for key players",
        }

    def _format_injuries(self, injuries: List[Dict[str, Any]]) -> str:
        """Format injuries for prompt."""
        if not injuries:
            return "None known"
        formatted = []
        for inj in injuries[:3]:  # Top 3 injuries
            formatted.append(f"{inj.get('player', 'Unknown')} ({inj.get('status', 'out')})")
        return ", ".join(formatted)

    def _format_suspensions(self, suspensions: List[Dict[str, Any]]) -> str:
        """Format suspensions for prompt."""
        if not suspensions:
            return "None"
        formatted = []
        for susp in suspensions:
            formatted.append(
                f"{susp.get('player', 'Unknown')} ({susp.get('remaining_matches', 1)} match)"
            )
        return ", ".join(formatted)

    async def _synthesize_critical_updates(
        self,
        home_news: Dict[str, Any],
        away_news: Dict[str, Any],
    ) -> List[str]:
        """Extract critical updates from both teams' news."""
        critical = []

        # Check for major injuries
        all_injuries = home_news.get("injuries", []) + away_news.get("injuries", [])
        if any(inj.get("status") == "out" for inj in all_injuries):
            critical.append("Major absence to impact match")

        # Check for suspensions
        if home_news.get("suspensions") or away_news.get("suspensions"):
            critical.append("Suspension affecting key player")

        # Check late changes
        if (home_news.get("last_minute_changes") or away_news.get("last_minute_changes")):
            critical.append("Expected late lineup adjustments")

        return critical if critical else ["No critical updates"]

    async def close(self):
        """Clean up resources."""
        await self.retriever.close()
        await self.sports_retriever.close()
