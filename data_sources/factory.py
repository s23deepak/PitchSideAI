"""
Data Retriever Factory — PitchSide AI
Dynamically routes data requests to the most specialized sports API available.
Also manages singletons for shared search services.
"""
from typing import Any, Dict, List, Optional
import logging
from .cache import DataCache
from .base import BaseRetriever

logger = logging.getLogger(__name__)

# ── Singletons ─────────────────────────────────────────────────────────────

_search_service = None
_fbref_retriever = None
_statsbomb_retriever = None
_football_data_retriever = None


def get_search_service(cache: Optional[DataCache] = None):
    """Get or create the shared TavilySearchService singleton."""
    global _search_service
    if _search_service is None:
        from .tavily_search_service import TavilySearchService
        _search_service = TavilySearchService(cache=cache)
    return _search_service


def get_statsbomb_retriever(cache: Optional[DataCache] = None):
    """Get or create the shared StatsBombRetriever singleton."""
    global _statsbomb_retriever
    if _statsbomb_retriever is None:
        from .statsbomb_retriever import StatsBombRetriever
        _statsbomb_retriever = StatsBombRetriever(cache=cache)
    return _statsbomb_retriever


class FallbackStatsRetriever:
    """
    Three-layer fallback chain for stats retrieval:
      1. StatsBomb  — free historical data (exact-match only; returns empty for current seasons)
      2. Firecrawl  — live web scraping with anti-bot handling (current season primary)
      3. FBref direct — soccerdata as last resort (may 403 in some envs)

    Transparent drop-in replacement: exposes the same 5 async methods +
    is_available property that agents and sports_specific_retriever expect.
    """

    def __init__(self, cache: Optional[DataCache] = None, league: str = "ENG-Premier League", season: str = "25-26"):
        from .statsbomb_retriever import StatsBombRetriever
        from .firecrawl_retriever import FirecrawlRetriever
        from .fbref_retriever import FBrefRetriever
        self._sb = StatsBombRetriever(cache=cache)
        self._fc = FirecrawlRetriever(cache=cache)
        self._fb = FBrefRetriever(cache=cache, league=league, season=season)

    @property
    def is_available(self) -> bool:
        return any([self._sb.is_available, self._fc.is_available, self._fb.is_available])

    async def _chain(self, method: str, *args, **kwargs):
        """Try each retriever in order, return first non-empty result."""
        for retriever in (self._sb, self._fc, self._fb):
            if not retriever.is_available:
                continue
            try:
                result = await getattr(retriever, method)(*args, **kwargs)
                if result:
                    return result
            except Exception as exc:
                logger.warning("%s.%s failed: %s", retriever.__class__.__name__, method, exc)
        return [] if method in ("get_team_match_log", "get_head_to_head_matches") else {}

    async def get_player_season_stats(self, player_name: str, team_name: Optional[str] = None,
                                       league: Optional[str] = None, season: Optional[str] = None,
                                       stat_type: str = "standard") -> Dict[str, Any]:
        return await self._chain("get_player_season_stats", player_name, team_name, league, season, stat_type)

    async def get_team_season_stats(self, team_name: str, league: Optional[str] = None,
                                     season: Optional[str] = None, stat_type: str = "standard") -> Dict[str, Any]:
        return await self._chain("get_team_season_stats", team_name, league, season, stat_type)

    async def get_tactical_profile(self, team_name: str, league: Optional[str] = None,
                                    season: Optional[str] = None) -> Dict[str, Any]:
        return await self._chain("get_tactical_profile", team_name, league, season)

    async def get_team_match_log(self, team_name: str, league: Optional[str] = None,
                                  season: Optional[str] = None, last_n: int = 5) -> List[Dict[str, Any]]:
        return await self._chain("get_team_match_log", team_name, league, season, last_n)

    async def get_head_to_head_matches(self, team1: str, team2: str,
                                        league: Optional[str] = None,
                                        season: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._chain("get_head_to_head_matches", team1, team2, league, season)

    async def close(self) -> None:
        for retriever in (self._sb, self._fc, self._fb):
            await retriever.close()


def get_fbref_retriever(
    cache: Optional[DataCache] = None,
    league: str = "ENG-Premier League",
    season: str = "25-26",
):
    """Get or create the shared FallbackStatsRetriever singleton (StatsBomb → Firecrawl → FBref)."""
    global _fbref_retriever
    if _fbref_retriever is None:
        _fbref_retriever = FallbackStatsRetriever(cache=cache, league=league, season=season)
    return _fbref_retriever


def get_football_data_retriever(cache: Optional[DataCache] = None):
    """Get or create the shared FootballDataRetriever singleton."""
    global _football_data_retriever
    if _football_data_retriever is None:
        from .football_data_retriever import FootballDataRetriever
        _football_data_retriever = FootballDataRetriever(cache=cache)
    return _football_data_retriever


# ── Sport-specific retriever factory ──────────────────────────────────────

def get_retriever(sport: str, cache: Optional[DataCache] = None) -> BaseRetriever:
    """
    Factory to return the optimal data retriever for a given sport.
    """
    sport_key = sport.lower().strip()

    if sport_key == "cricket":
        from .cricbuzz_retriever import CricbuzzRetriever
        return CricbuzzRetriever(cache=cache)

    elif sport_key == "soccer":
        from .goal_retriever import GoalComRetriever
        # We can implement Goal.com later, but let's fall back to ESPN for now
        # until the GoalComRetriever is fully ready!
        # return GoalComRetriever(cache=cache)
        pass

    # Default robust fallback for all sports (incl Soccer until Goal.com is done)
    from .espn_retriever import ESPNDataRetriever
    return ESPNDataRetriever(cache=cache)
