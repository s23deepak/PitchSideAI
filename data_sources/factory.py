"""
Data Retriever Factory — PitchSideAI
Dynamically routes data requests to the most specialized sports API available.
Also manages singletons for shared search services.

Architecture (Phase 1, June 2026):
- Multi-source load balancing for soccer data (ESPN → FootballData → Transfermarkt → Firecrawl)
- RoundRobinRouter for source priority routing with automatic failover
- ParallelRaceFetcher for racing multiple sources simultaneously
- StatsBomb retained for historical data only
- 16+ dedicated source retrievers with audit logging via BaseRetriever ABC
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from .cache import DataCache
from .base import BaseRetriever, RetrieverProtocol
from .retrieval_audit import AuditedRetrieverProxy

logger = logging.getLogger(__name__)

# ── Singletons ─────────────────────────────────────────────────────────────

_search_service = None
_multi_source_retriever = None
_statsbomb_retriever = None
_football_data_retriever = None
_brightdata_mcp_retriever = None
_exa_search_service = None


def get_search_service(cache: Optional[DataCache] = None):
    """Get or create the shared TavilySearchService singleton."""
    global _search_service
    if _search_service is None:
        from .tavily_search_service import TavilySearchService
        _search_service = TavilySearchService(cache=cache)
    return _search_service


def get_exa_search_service(cache: Optional[DataCache] = None):
    """Get or create the shared ExaSearchService singleton."""
    global _exa_search_service
    if _exa_search_service is None:
        from .exa_search_service import ExaSearchService
        _exa_search_service = ExaSearchService(cache=cache)
    return _exa_search_service


def get_statsbomb_retriever(cache: Optional[DataCache] = None):
    """Get or create the shared StatsBombRetriever singleton."""
    global _statsbomb_retriever
    if _statsbomb_retriever is None:
        from .statsbomb_retriever import StatsBombRetriever
        _statsbomb_retriever = AuditedRetrieverProxy("statsbomb", StatsBombRetriever(cache=cache))
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
        _football_data_retriever = AuditedRetrieverProxy("football_data", FootballDataRetriever(cache=cache))
    return _football_data_retriever


def get_brightdata_mcp_retriever():
    """Get or create the shared BrightData MCP retriever singleton."""
    global _brightdata_mcp_retriever
    if _brightdata_mcp_retriever is None:
        from .brightdata_mcp_retriever import BrightDataMcpRetriever
        _brightdata_mcp_retriever = BrightDataMcpRetriever()
    return _brightdata_mcp_retriever


# ── Router & Race Fetcher factory ─────────────────────────────────────────

def create_round_robin_router(
    sources: list[tuple[str, Any]],
    run_id: str,
    agent_name: str,
):
    """Create a round-robin router for a prioritized source list."""
    from .round_robin_router import RoundRobinRouter
    return RoundRobinRouter(sources=sources, run_id=run_id, agent_name=agent_name)


def create_parallel_race_fetcher():
    """Create a parallel race fetcher for multi-source racing."""
    from .parallel_race_fetcher import ParallelRaceFetcher
    return ParallelRaceFetcher()


# ── Sport-specific retriever factory ──────────────────────────────────────

def get_retriever(sport: str, cache: Optional[DataCache] = None) -> RetrieverProtocol:
    """
    Factory to return the optimal data retriever for a given sport.

    For soccer: returns MultiSourceRetriever for load-balanced data fetching.
    For other sports: returns ESPN as fallback.
    """
    sport_key = sport.lower().strip()

    if sport_key == "soccer":
        return get_fbref_retriever(cache=cache)

    from .espn_retriever import ESPNDataRetriever
    return AuditedRetrieverProxy("espn", ESPNDataRetriever(cache=cache))


# ── Named source retriever getters ────────────────────────────────────────

def get_source_retriever_by_name(
    source_name: str,
    cache: Optional[DataCache] = None,
) -> BaseRetriever:
    """Get a dedicated retriever for a specific named source.

    Maps source name strings (e.g. 'goal', 'rotowire', 'dbpedia')
    to their concrete BaseRetriever subclass instances.
    """
    search_service = get_search_service(cache=cache)

    source_map: dict[str, Any] = {
        "goal": lambda: GoalComRetriever(cache=cache, search_service=search_service),
        "rotowire": lambda: RotowireRetriever(cache=cache, search_service=search_service),
        "sky_sports": lambda: SkySportsRetriever(cache=cache, search_service=search_service),
        "bbc_sport": lambda: BbcSportRetriever(cache=cache, search_service=search_service),
        "the_athletic": lambda: AthleticRetriever(cache=cache, search_service=search_service),
        "sports_mole": lambda: SportsMoleRetriever(cache=cache, search_service=search_service),
        "onefootball": lambda: OneFootballRetriever(cache=cache, search_service=search_service),
        "sofascore": lambda: SofascoreRetriever(cache=cache, search_service=search_service),
        "fbref": lambda: FbrefRetriever(cache=cache, search_service=search_service),
        "whoscored": lambda: WhoScoredRetriever(cache=cache, search_service=search_service),
        "11v11": lambda: ElevenVElevenRetriever(cache=cache, search_service=search_service),
        "dbpedia": lambda: DbpediaRetriever(cache=cache),
        "jina": lambda: JinaReaderRetriever(cache=cache),
        "open_meteo": lambda: OpenMeteoRetriever(cache=cache),
        "forvo": lambda: ForvoRetriever(cache=cache),
        "youglish": lambda: YouglishRetriever(cache=cache),
    }

    factory_fn = source_map.get(source_name.lower().replace("-", "_"))
    if factory_fn is None:
        logger.warning("No dedicated retriever for source '%s', falling back to Tavily", source_name)
        return search_service

    return factory_fn()


from .goal_com_retriever import GoalComRetriever
from .rotowire_retriever import RotowireRetriever
from .sky_sports_retriever import SkySportsRetriever
from .bbc_sport_retriever import BbcSportRetriever
from .the_athletic_retriever import AthleticRetriever
from .sports_mole_retriever import SportsMoleRetriever
from .one_football_retriever import OneFootballRetriever
from .sofascore_retriever import SofascoreRetriever
from .fbref_retriever import FbrefRetriever
from .whoscored_retriever import WhoScoredRetriever
from .eleven_v_eleven_retriever import ElevenVElevenRetriever
from .dbpedia_retriever import DbpediaRetriever
from .jina_reader_retriever import JinaReaderRetriever
from .open_meteo_retriever import OpenMeteoRetriever
from .forvo_retriever import ForvoRetriever
from .youglish_retriever import YouglishRetriever
