"""
Player Research Agent - Research team squads with detailed player information.

Gathers biographical, statistical, and contextual data for up to 25 players per team
using ESPN API (stats) and Wikipedia (biography) data sources.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import WikipediaRetriever, DataCache
from data_sources.factory import get_retriever

logger = logging.getLogger(__name__)


class PlayerResearchAgent(BaseAgent):
    """Research and profile team squads."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
    ):
        """
        Initialize player research agent.

        Args:
            model_id: Bedrock model ID (default: Nova Pro for quality)
            sport: Sport type
            cache: Optional shared cache instance
        """
        super().__init__(model_id=model_id, sport=sport, agent_type="player_research")
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.retriever = get_retriever(self.sport, cache=self.cache)
        self.wiki_retriever = WikipediaRetriever(cache=self.cache)

    async def execute(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Main execution method for compatibility with BaseAgent.

        Args:
            home_team: Home team name
            away_team: Away team name

        Returns:
            Combined squad research for both teams
        """
        return await self.research_squad_pair(home_team, away_team)

    async def research_squad_pair(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Research both team squads simultaneously.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            Squad data for both teams
        """
        start_time = datetime.utcnow()

        # Research both squads in parallel
        home_squad, away_squad = await asyncio.gather(
            self.research_squad(home_team),
            self.research_squad(away_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="squad_research_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "home_count": len(home_squad.get("players", [])),
                "away_count": len(away_squad.get("players", [])),
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_team": home_squad,
            "away_team": away_squad,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def research_squad(self, team_name: str) -> Dict[str, Any]:
        """
        Research complete team squad with player-by-player analysis.

        Args:
            team_name: Team name

        Returns:
            Squad data with 25 researched players (or fewer if unavailable)
        """
        # Fetch ESPN squad data
        espn_squad = await self.retriever.get_team_squad(team_name, self.sport)

        # Enrich each player with detailed research
        players = espn_squad.get("players", [])[:5]  # 5 for local dev (bump to 25 for production)

        enriched_players = await asyncio.gather(
            *[self._research_player_detailed(p, team_name) for p in players],
            return_exceptions=True,
        )

        # Filter out any errors
        enriched_players = [p for p in enriched_players if not isinstance(p, Exception)]

        return {
            "team_name": team_name,
            "formation": espn_squad.get("formation", "Unknown"),
            "coach": espn_squad.get("coach", "Unknown"),
            "players": enriched_players,
            "total_players_researched": len(enriched_players),
            "research_timestamp": datetime.utcnow().isoformat(),
        }

    async def _research_player_detailed(
        self,
        player_data: Dict[str, Any],
        team_name: str,
    ) -> Dict[str, Any]:
        """
        Deep research on individual player.

        Args:
            player_data: Basic player data from ESPN
            team_name: Team name for context

        Returns:
            Enriched player profile
        """
        player_name = player_data.get("name", "Unknown")

        try:
            # Get Wikipedia biography in parallel with stats
            wiki_bio, player_stats = await asyncio.gather(
                self.wiki_retriever.get_player_biography(player_name, self.sport),
                self.retriever.get_player_stats(player_name, team_name, self.sport),
                return_exceptions=True,
            )

            # Handle potential exceptions
            if isinstance(wiki_bio, Exception):
                wiki_bio = {}
            if isinstance(player_stats, Exception):
                player_stats = {}

            # Synthesize into profile using Bedrock
            profile_prompt = f"""Create a professional {self.sport} player profile for {player_name}:

Basic Info:
- Position: {player_data.get('position', 'Unknown')}
- Age: {player_data.get('age', 'Unknown')}
- Team: {team_name}

Career:
{wiki_bio.get('career_summary', 'Professional player with competitive experience')}

Statistics:
- Appearances: {player_stats.get('career', {}).get('appearances', 'N/A')}
- Goals: {player_stats.get('career', {}).get('goals', 'N/A')}

Recent Form: {player_data.get('recent_form', 'Consistent performance')}

Provide:
1. Playing style (2-3 key characteristics)
2. Strengths (2-3 main strengths)
3. Weaknesses (1-2 areas for improvement)
4. Matchup prediction vs common typical opponents

Keep it concise (3-4 sentences total) for commentary notes."""

            profile_text = await self.call_bedrock(
                prompt=profile_prompt,
                temperature=0.3,
                max_tokens=150,  # 150 for local dev (300 in production)
            )

            return {
                "name": player_name,
                "position": player_data.get("position", "Unknown"),
                "squad_number": player_data.get("squad_number", "N/A"),
                "age": player_data.get("age", "Unknown"),
                "appearances": player_stats.get("career", {}).get("appearances", 0),
                "goals": player_stats.get("career", {}).get("goals", 0),
                "assists": player_stats.get("career", {}).get("assists", 0),
                "recent_form": player_data.get("recent_form", "Steady"),
                "playing_style": wiki_bio.get("playing_style", "Professional")[:100],
                "profile": profile_text,
                "birth_place": wiki_bio.get("birth_place", "N/A"),
                "nationality": wiki_bio.get("nationality", "N/A"),
            }

        except Exception as e:
            logger.error(f"Error researching player {player_name}: {e}")
            # Return basic profile on error
            return {
                "name": player_name,
                "position": player_data.get("position", "Unknown"),
                "squad_number": player_data.get("squad_number", "N/A"),
                "error": str(e),
            }

    async def get_player_comparatives(
        self,
        player_name: str,
        opposing_player: str,
        team_name: str,
    ) -> Dict[str, Any]:
        """
        Analyze 1v1 scenario between two players.

        Args:
            player_name: Player name
            opposing_player: Opponent player name
            team_name: Team name

        Returns:
            Comparative analysis
        """
        prompt = f"""As an elite {self.sport} analyst, analyze the tactical matchup between {player_name} and {opposing_player}:

For {player_name}:
- Consider their strengths (speed, positioning, strength, technical ability)
- Identify weaknesses against different play styles

For {opposing_player}:
- Counter-tactics available
- Historical patterns if applicable

Provide:
1. Key tactical battle to expect
2. Who has advantage and why
3. How this matchup could swing the game

Keep to 3-4 sentences."""

        analysis = await self.call_bedrock(
            prompt=prompt,
            temperature=0.4,
            max_tokens=120,  # 120 for local dev (250 in production)
        )

        return {
            "player1": player_name,
            "player2": opposing_player,
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def close(self):
        """Clean up resources."""
        await self.retriever.close()
        await self.wiki_retriever.close()
