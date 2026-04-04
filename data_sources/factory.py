"""
Data Retriever Factory — PitchSide AI
Dynamically routes data requests to the most specialized sports API available.
Also manages singletons for shared search services.
"""
from typing import Optional
import logging
from .cache import DataCache
from .base import BaseRetriever

logger = logging.getLogger(__name__)

# ── Singletons ─────────────────────────────────────────────────────────────

_search_service = None
_fbref_retriever = None
_football_data_retriever = None


def get_search_service(cache: Optional[DataCache] = None):
    """Get or create the shared TavilySearchService singleton."""
    global _search_service
    if _search_service is None:
        from .tavily_search_service import TavilySearchService
        _search_service = TavilySearchService(cache=cache)
    return _search_service


def get_fbref_retriever(
    cache: Optional[DataCache] = None,
    league: str = "ENG-Premier League",
    season: str = "25-26",
):
    """Get or create the shared FBrefRetriever singleton."""
    global _fbref_retriever
    if _fbref_retriever is None:
        from .fbref_retriever import FBrefRetriever
        _fbref_retriever = FBrefRetriever(cache=cache, league=league, season=season)
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
