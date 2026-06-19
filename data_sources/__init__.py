"""
Data retrieval module for multi-agent commentary system.

Phase 1 infrastructure:
- BaseRetriever (ABC) — fetch → log → score → return template
- FetchResult — unified return type with is_good/is_bad/is_marginal
- RateLimiter — per-source async rate limiter
- RoundRobinRouter — source priority routing with failover
- ParallelRaceFetcher — multi-source parallel race

Specialized data retrievers for:
- ESPN API (team/player statistics)
- Weather data (OpenWeatherMap, Tavily search, Open-Meteo)
- Sport-specific data (MultiSource, football-data.org)
- Wikipedia (player biographies via Tavily)
- Tavily web search (bios, news, weather, H2H, storylines)
- Exa semantic search (domain-filtered, topic-aware)
- MultiSource load-balanced retriever (ESPN → FootballData → Transfermarkt → Firecrawl)
- StatsBomb free event data (historical seasons)
- Firecrawl web scraping (current-season stats via anti-bot API)
- football-data.org REST API (standings, H2H, scorers)
- And 16+ domain-specific retrievers (DBpedia, Goal.com, Rotowire, etc.)
"""

from data_sources.cache import DataCache
from data_sources.result import FetchResult
from data_sources.rate_limiter import RateLimiter, DEFAULT_SOURCE_RPM, get_source_rate_limiter
from data_sources.base import BaseRetriever, RetrieverProtocol
from data_sources.round_robin_router import RoundRobinRouter
from data_sources.parallel_race_fetcher import ParallelRaceFetcher

from data_sources.espn_retriever import ESPNDataRetriever
from data_sources.weather_retriever import WeatherDataRetriever
from data_sources.sports_specific_retriever import SportsSpecificRetriever
from data_sources.wikipedia_retriever import WikipediaRetriever
from data_sources.tavily_search_service import TavilySearchService
from data_sources.exa_search_service import ExaSearchService
from data_sources.statsbomb_retriever import StatsBombRetriever
from data_sources.firecrawl_retriever import FirecrawlRetriever
from data_sources.football_data_retriever import FootballDataRetriever
from data_sources.multi_source_retriever import MultiSourceRetriever
from data_sources.transfermarkt_retriever import TransfermarktRetriever
from data_sources.one_versus_one_retriever import OneVersusOneRetriever
from data_sources.brightdata_mcp_retriever import BrightDataMcpRetriever
from data_sources.fixture_resolver import FixtureResolver
from data_sources.open_meteo_retriever import OpenMeteoRetriever
from data_sources.dbpedia_retriever import DbpediaRetriever
from data_sources.jina_reader_retriever import JinaReaderRetriever
from data_sources.goal_com_retriever import GoalComRetriever
from data_sources.rotowire_retriever import RotowireRetriever
from data_sources.forvo_retriever import ForvoRetriever
from data_sources.youglish_retriever import YouglishRetriever
from data_sources.sky_sports_retriever import SkySportsRetriever
from data_sources.bbc_sport_retriever import BbcSportRetriever
from data_sources.the_athletic_retriever import AthleticRetriever
from data_sources.sports_mole_retriever import SportsMoleRetriever
from data_sources.one_football_retriever import OneFootballRetriever
from data_sources.sofascore_retriever import SofascoreRetriever
from data_sources.fbref_retriever import FbrefRetriever
from data_sources.whoscored_retriever import WhoScoredRetriever
from data_sources.eleven_v_eleven_retriever import ElevenVElevenRetriever

__all__ = [
    "DataCache",
    "FetchResult",
    "RateLimiter",
    "DEFAULT_SOURCE_RPM",
    "get_source_rate_limiter",
    "BaseRetriever",
    "RetrieverProtocol",
    "RoundRobinRouter",
    "ParallelRaceFetcher",
    "ESPNDataRetriever",
    "WeatherDataRetriever",
    "SportsSpecificRetriever",
    "WikipediaRetriever",
    "TavilySearchService",
    "ExaSearchService",
    "StatsBombRetriever",
    "FirecrawlRetriever",
    "FootballDataRetriever",
    "MultiSourceRetriever",
    "TransfermarktRetriever",
    "OneVersusOneRetriever",
    "BrightDataMcpRetriever",
    "FixtureResolver",
    "OpenMeteoRetriever",
    "DbpediaRetriever",
    "JinaReaderRetriever",
    "GoalComRetriever",
    "RotowireRetriever",
    "ForvoRetriever",
    "YouglishRetriever",
    "SkySportsRetriever",
    "BbcSportRetriever",
    "AthleticRetriever",
    "SportsMoleRetriever",
    "OneFootballRetriever",
    "SofascoreRetriever",
    "FbrefRetriever",
    "WhoScoredRetriever",
    "ElevenVElevenRetriever",
]
