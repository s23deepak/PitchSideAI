"""
Sport-Specific Data Retriever - Fetch data from FBref, Tavily, and other sources.

Integrates with:
- FBref: Soccer lineups, tactics, formations, player stats
- Tavily: Team news, injuries, suspensions, transfers
- football-data.org: Squad details, standings
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from data_sources.cache import DataCache
from data_sources.factory import (
    get_fbref_retriever,
    get_football_data_retriever,
    get_search_service,
)

logger = logging.getLogger(__name__)


class SportsSpecificRetriever:
    """Retrieve sport-specific data from specialized sources."""

    def __init__(
        self,
        cache: Optional[DataCache] = None,
        fbref_retriever: Optional[Any] = None,
        football_data_retriever: Optional[Any] = None,
        search_service: Optional[Any] = None,
    ):
        """
        Initialize sports-specific retriever.

        Args:
            cache: Optional DataCache instance
            fbref_retriever: Optional FBrefRetriever for soccer stats
            football_data_retriever: Optional FootballDataRetriever for standings/squads
            search_service: Optional TavilySearchService for news/tactics
        """
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.fbref = fbref_retriever or get_fbref_retriever(cache=self.cache)
        self.football_data = football_data_retriever or get_football_data_retriever(cache=self.cache)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def get_soccer_lineups(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Get soccer team lineups and formations.

        Args:
            home_team: Home team name
            away_team: Away team name

        Returns:
            Lineups with formations, player positions, substitutes
        """
        cache_key = f"{home_team}_vs_{away_team}"
        cached = self.cache.get("soccer_lineups", cache_key)
        if cached:
            return cached

        lineups = {
            "home_team": home_team,
            "away_team": away_team,
            "home_formation": None,
            "away_formation": None,
            "home_lineup": [],
            "away_lineup": [],
            "home_bench": [],
            "away_bench": [],
            "data_source": "unavailable",
        }

        # Try Tavily search for predicted lineups
        if self.search_service and self.search_service.is_available:
            try:
                home_lineup = await self.search_service.search_lineup(home_team, "soccer")
                away_lineup = await self.search_service.search_lineup(away_team, "soccer")

                if home_lineup.get("answer") or away_lineup.get("answer"):
                    lineups = {
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_summary": home_lineup.get("answer", "")[:300] if home_lineup.get("answer") else "",
                        "away_summary": away_lineup.get("answer", "")[:300] if away_lineup.get("answer") else "",
                        "data_source": "tavily_search",
                        "source_urls": (
                            [r.get("url", "") for r in home_lineup.get("results", [])]
                            + [r.get("url", "") for r in away_lineup.get("results", [])]
                        )[:5],
                    }
            except Exception as exc:
                logger.warning("Tavily lineup search failed: %s", exc)

        self.cache.set("soccer_lineups", cache_key, lineups)
        return lineups

    async def get_soccer_tactics(
        self,
        team_name: str,
    ) -> Dict[str, Any]:
        """
        Get soccer team tactical profile from real sources.

        Args:
            team_name: Team name

        Returns:
            Tactical data (formation, press type, attacking style, etc.)
        """
        cached = self.cache.get("soccer_tactics", team_name)
        if cached:
            return cached

        tactics = {
            "team": team_name,
            "data_source": "unavailable",
        }

        # Try FBref for tactical stats
        if self.fbref and self.fbref.is_available:
            try:
                tactical_profile = await self.fbref.get_tactical_profile(team_name)
                if tactical_profile:
                    tactics = {
                        "team": team_name,
                        "possession_stats": tactical_profile.get("possession_stats", {}),
                        "defense_stats": tactical_profile.get("defense_stats", {}),
                        "passing_stats": tactical_profile.get("passing_stats", {}),
                        "data_source": "fbref",
                    }
            except Exception as exc:
                logger.warning("FBref tactical profile failed for %s: %s", team_name, exc)

        # Fall back to Tavily search
        if not tactics.get("possession_stats"):
            if self.search_service and self.search_service.is_available:
                try:
                    search_result = await self.search_service.search_team_tactics(team_name, "soccer")
                    if search_result.get("answer"):
                        tactics = {
                            "team": team_name,
                            "tactical_summary": search_result["answer"][:400],
                            "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                            "data_source": "tavily_search",
                        }
                except Exception as exc:
                    logger.warning("Tavily tactical search failed for %s: %s", team_name, exc)

        self.cache.set("soccer_tactics", team_name, tactics)
        return tactics

    async def get_cricket_squad(
        self,
        team_name: str,
        match_type: str = "ODI",
    ) -> Dict[str, Any]:
        """
        Get cricket team squad from real sources.

        Args:
            team_name: Team name
            match_type: Match type (ODI, T20, Test)

        Returns:
            Squad data with batting/bowling averages, recent performance
        """
        cache_key = f"{team_name}_{match_type}"
        cached = self.cache.get("cricket_squad", cache_key)
        if cached:
            return cached

        squad = {
            "team": team_name,
            "match_type": match_type,
            "players": [],
            "data_source": "unavailable",
        }

        # Try Tavily search for squad info
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search(
                    f"{team_name} {match_type} squad players recent form",
                    cache_namespace="tavily_cricket_squad",
                )
                if search_result.get("answer"):
                    squad = {
                        "team": team_name,
                        "match_type": match_type,
                        "squad_summary": search_result["answer"][:400],
                        "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                        "data_source": "tavily_search",
                    }
            except Exception as exc:
                logger.warning("Tavily cricket squad search failed for %s: %s", team_name, exc)

        self.cache.set("cricket_squad", cache_key, squad)
        return squad

    async def get_cricket_playing_condition(
        self,
        venue: str,
    ) -> Dict[str, Any]:
        """
        Get cricket playing conditions at venue from real sources.

        Args:
            venue: Cricket venue name

        Returns:
            Pitch/ground conditions, dimensions, typical behavior
        """
        cached = self.cache.get("cricket_conditions", venue)
        if cached:
            return cached

        conditions = {
            "ground": venue,
            "data_source": "unavailable",
        }

        # Try Tavily search for ground conditions
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search(
                    f"{venue} cricket ground pitch conditions dimensions",
                    cache_namespace="tavily_cricket_conditions",
                )
                if search_result.get("answer"):
                    conditions = {
                        "ground": venue,
                        "conditions_summary": search_result["answer"][:400],
                        "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                        "data_source": "tavily_search",
                    }
            except Exception as exc:
                logger.warning("Tavily cricket conditions search failed for %s: %s", venue, exc)

        self.cache.set("cricket_conditions", venue, conditions)
        return conditions

    async def search_player_news(
        self,
        player_name: str,
        team_name: str,
        sport: str = "soccer",
        hours_lookback: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Search for recent news about specific player from real sources.

        Args:
            player_name: Player name
            team_name: Team name
            sport: Sport type
            hours_lookback: Hours to look back for news

        Returns:
            List of news items (title, source, date, summary)
        """
        cache_key = f"{player_name}_{team_name}_{sport}_{hours_lookback}"
        cached = self.cache.get("player_news", cache_key)
        if cached:
            return cached

        news = []

        # Try Tavily search for player news
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search(
                    f"{player_name} {team_name} {sport} latest news injury update availability",
                    topic="news",
                    max_results=5,
                    cache_namespace="tavily_player_news",
                )
                if search_result.get("results"):
                    news = [
                        {
                            "title": r.get("title", ""),
                            "source": r.get("source", ""),
                            "url": r.get("url", ""),
                            "summary": r.get("content", "")[:200],
                            "importance": "medium",
                        }
                        for r in search_result.get("results", [])[:5]
                    ]
            except Exception as exc:
                logger.warning("Tavily team news search failed: %s", exc)

        self.cache.set("player_news", cache_key, news)
        return news

    async def close(self) -> None:
        """Compatibility no-op."""
        return None

    async def get_team_squad(self, team_name: str) -> Dict[str, Any]:
        """
        Get team squad with player details from real sources.

        Args:
            team_name: Team name

        Returns:
            Squad details with player positions, nationalities
        """
        cache_key = team_name.lower()
        cached = self.cache.get("team_squad", cache_key)
        if cached:
            return cached

        squad = {
            "team": team_name,
            "squad": [],
            "data_source": "unavailable",
        }

        # Try football-data.org for squad
        if self.football_data and self.football_data.is_available:
            try:
                fd_squad = await self.football_data.get_team_squad(team_name)
                if fd_squad.get("squad"):
                    squad = fd_squad
                    squad["data_source"] = "football_data_org"
            except Exception as exc:
                logger.warning("Football-data squad retrieval failed for %s: %s", team_name, exc)

        self.cache.set("team_squad", cache_key, squad)
        return squad
