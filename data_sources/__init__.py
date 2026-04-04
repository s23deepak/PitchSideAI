"""
Data retrieval module for multi-agent commentary system.

Provides specialized data retrievers for:
- ESPN API (team/player statistics)
- Weather data (OpenWeatherMap, Tavily search)
- Sport-specific data (FBref, football-data.org)
- Wikipedia (player biographies via Tavily)
- Tavily web search (bios, news, weather, H2H, storylines)
- FBref structured stats (player/team season/match stats)
- football-data.org REST API (standings, H2H, scorers)
"""

from data_sources.cache import DataCache
from data_sources.espn_retriever import ESPNDataRetriever
from data_sources.weather_retriever import WeatherDataRetriever
from data_sources.sports_specific_retriever import SportsSpecificRetriever
from data_sources.wikipedia_retriever import WikipediaRetriever
from data_sources.tavily_search_service import TavilySearchService
from data_sources.fbref_retriever import FBrefRetriever
from data_sources.football_data_retriever import FootballDataRetriever

__all__ = [
    "DataCache",
    "ESPNDataRetriever",
    "WeatherDataRetriever",
    "SportsSpecificRetriever",
    "WikipediaRetriever",
    "TavilySearchService",
    "FBrefRetriever",
    "FootballDataRetriever",
]
