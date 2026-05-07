"""
Data Retriever Factory — PitchAI
Dynamically routes data requests to the most specialized sports API available.
Also manages singletons for shared search services.

Architecture (May 2026):
- Multi-source load balancing for soccer data (ESPN → FootballData → Transfermarkt → Firecrawl)
- StatsBomb retained for historical data only
- FBref and Cricbuzz removed (FBref 403s frequently, Cricbuzz not needed)
"""
from typing import Any, Dict, List, Optional
import logging
from .cache import DataCache
from .base import BaseRetriever

logger = logging.getLogger(__name__)

# ── Singletons ─────────────────────────────────────────────────────────────

_search_service = None
_multi_source_retriever = None
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


def get_fbref_retriever(
    cache: Optional[DataCache] = None,
    league: str = "ENG-Premier League",
    season: str = "25-26",
):
    """
    Get or create the shared MultiSourceRetriever singleton.

    Replaces FallbackStatsRetriever (Apr 2026) with load-balanced multi-source architecture.
    Sources: ESPN (primary) → FootballData.org → Transfermarkt → Firecrawl (fallback)

    Note: league/season params kept for backward compatibility but not used by MultiSourceRetriever.
    """
    global _multi_source_retriever
    if _multi_source_retriever is None:
        from .multi_source_retriever import MultiSourceRetriever
        _multi_source_retriever = MultiSourceRetriever(cache=cache, league=league, season=season)
    return _multi_source_retriever


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

    For soccer: returns MultiSourceRetriever for load-balanced data fetching.
    For other sports: returns ESPN as fallback.
    """
    sport_key = sport.lower().strip()

    if sport_key == "soccer":
        # Use multi-source retriever for soccer (load-balanced across 4 sources)
        return get_fbref_retriever(cache=cache)

    # Default robust fallback for all other sports
    from .espn_retriever import ESPNDataRetriever
    return ESPNDataRetriever(cache=cache)
