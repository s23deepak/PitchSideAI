"""
Player Research Agent - Research team squads with detailed player information.

Gathers biographical, statistical, and contextual data for players using
Tavily search (biography), FBref (statistics), and ESPN (roster) data sources.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache, WikipediaRetriever
from data_sources.factory import (
    get_retriever,
    get_fbref_retriever,
    get_search_service,
)
from data_sources.player_profile_db import get_player_db

logger = logging.getLogger(__name__)


class PlayerResearchAgent(BaseAgent):
    """Research and profile team squads with real data."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        fbref_retriever: Optional[Any] = None,
        search_service: Optional[Any] = None,
    ):
        """
        Initialize player research agent.

        Args:
            model_id: Bedrock model ID (default: Nova Pro for quality)
            sport: Sport type
            cache: Optional shared cache instance
            fbref_retriever: Optional FBref retriever for player stats
            search_service: Optional Tavily search service
        """
        super().__init__(model_id=model_id, sport=sport, agent_type="player_research")
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.retriever = get_retriever(self.sport, cache=self.cache)
        self.fbref = fbref_retriever or (get_fbref_retriever(cache=self.cache) if sport == "soccer" else None)
        self.search_service = search_service or get_search_service(cache=self.cache)
        self.wiki_retriever = WikipediaRetriever(
            cache=self.cache,
            search_service=self.search_service
        )

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
            Squad data with researched players
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
            "players": enriched_players,
            "total_players_researched": len(enriched_players),
            "data_sources": ["ESPN", "FBref", "Tavily"],
            "research_timestamp": datetime.utcnow().isoformat(),
        }

    async def _research_player_detailed(
        self,
        player_data: Dict[str, Any],
        team_name: str,
    ) -> Dict[str, Any]:
        """
        Deep research on individual player using multiple data sources.
        Checks the local SQLite DB first to avoid redundant external calls.

        Args:
            player_data: Basic player data from ESPN
            team_name: Team name for context

        Returns:
            Enriched player profile
        """
        player_name = player_data.get("name", "Unknown")
        db = get_player_db()

        try:
            # ── Check local DB for cached static profile ──
            cached_profile = db.get_profile(player_name, self.sport)
            if cached_profile:
                logger.info("DB hit for %s — skipping ESPN bio fields", player_name)
                # Merge DB fields into player_data (ESPN may have fresher injury_status)
                for field in ("nationality", "nationality_abbr", "position", "headshot", "wikipedia_url"):
                    if cached_profile.get(field) and not player_data.get(field):
                        player_data[field] = cached_profile[field]

            # ── Save ESPN bio fields to DB (static data we already have) ──
            db.upsert_profile(player_name, self.sport, player_data)

            # ── Fetch external data (Tavily bio + FBref stats) in parallel ──
            wiki_bio, player_stats = await asyncio.gather(
                self.wiki_retriever.get_player_biography(player_name, self.sport),
                self._fetch_player_stats(player_name, team_name),
                return_exceptions=True,
            )

            # Handle potential exceptions
            if isinstance(wiki_bio, Exception):
                wiki_bio = {}
            if isinstance(player_stats, Exception):
                player_stats = {}
            player_stats = player_stats or player_data.get("stats", {})

            # ── Save FBref stats to DB for this season ──
            if player_stats and any(player_stats.get(k) for k in ("goals", "assists", "appearances")):
                db.upsert_season_stats(
                    player_name, self.sport, "25-26", "fbref", player_stats
                )

            # ── Save notable achievements from Wikipedia if present ──
            if wiki_bio.get("notable_achievements") or wiki_bio.get("wikipedia_url"):
                db.upsert_profile(player_name, self.sport, {
                    "wikipedia_url": wiki_bio.get("wikipedia_url"),
                    "notable_achievements": wiki_bio.get("notable_achievements"),
                })

            # Build stats context
            stats_summary = ""
            if player_stats:
                goals = player_stats.get("goals", 0) or 0
                assists = player_stats.get("assists", 0) or 0
                stats_summary = f"Season: {goals}G {assists}A"

            # Synthesize into profile using Bedrock
            profile_prompt = f"""Create a professional {self.sport} player profile for {player_name}:

Basic Info:
- Position: {player_data.get('position', 'Unknown')}
- Age: {player_data.get('age', 'Unknown')}
- Team: {team_name}

Career: {wiki_bio.get('career_summary', '')[:150]}

Statistics: {stats_summary}

Provide:
1. Playing style (2 key characteristics)
2. Strengths (2 main attributes)
3. Match impact prediction

Keep it concise (2-3 sentences) for commentary notes."""

            profile_text = await self.call_bedrock(
                prompt=profile_prompt,
                temperature=0.3,
                max_tokens=120,
            )

            return {
                "name": player_name,
                "position": player_data.get("position", "Unknown"),
                "squad_number": player_data.get("squad_number") or player_data.get("jersey", "N/A"),
                "age": player_data.get("age", "Unknown"),
                "stats": player_stats,
                "biography": wiki_bio.get("career_summary", "")[:100],
                "nationality": wiki_bio.get("nationality") or player_data.get("nationality", "N/A"),
                "injury_status": player_data.get("injury_status", "Healthy"),
                "profile": profile_text,
            }

        except Exception as e:
            logger.error("Error researching player %s: %s", player_name, e)
            # Return basic profile on error
            return {
                "name": player_name,
                "position": player_data.get("position", "Unknown"),
                "squad_number": player_data.get("squad_number") or player_data.get("jersey", "N/A"),
                "error": str(e),
            }

    async def _fetch_player_stats(
        self, player_name: str, team_name: str
    ) -> Dict[str, Any]:
        """Fetch player stats from local DB first, then FBref as fallback."""
        db = get_player_db()

        # Check DB for current season stats (saved from a previous successful FBref fetch)
        cached_stats = db.get_season_stats(player_name, self.sport, "25-26", "fbref")
        if cached_stats:
            logger.info("DB stats hit for %s — skipping FBref", player_name)
            return cached_stats

        if not self.fbref or not self.fbref.is_available:
            return {}

        try:
            stats = await self.fbref.get_player_season_stats(player_name, team_name)
            if stats:
                db.upsert_season_stats(player_name, self.sport, "25-26", stats.get("data_source", "fbref"), stats)
            return stats
        except Exception as exc:
            logger.warning("FBref player stats failed for %s: %s", player_name, exc)
            return {}

    async def close(self):
        """Clean up resources."""
        pass
