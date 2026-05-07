"""
Data retrieval module for multi-agent commentary system.

Provides specialized data retrievers for:
- ESPN API (team/player statistics)
- Weather data (OpenWeatherMap, Tavily search)
- Sport-specific data (MultiSource, football-data.org)
- Wikipedia (player biographies via Tavily)
- Tavily web search (bios, news, weather, H2H, storylines)
- MultiSource load-balanced retriever (ESPN → FootballData → Transfermarkt → Firecrawl)
- StatsBomb free event data (historical seasons)
- Firecrawl web scraping (current-season stats via anti-bot API)
- football-data.org REST API (standings, H2H, scorers)
"""

from data_sources.cache import DataCache
from data_sources.espn_retriever import ESPNDataRetriever
from data_sources.weather_retriever import WeatherDataRetriever
from data_sources.sports_specific_retriever import SportsSpecificRetriever
from data_sources.wikipedia_retriever import WikipediaRetriever
from data_sources.tavily_search_service import TavilySearchService
from data_sources.statsbomb_retriever import StatsBombRetriever
from data_sources.firecrawl_retriever import FirecrawlRetriever
from data_sources.football_data_retriever import FootballDataRetriever
from data_sources.multi_source_retriever import MultiSourceRetriever
from data_sources.transfermarkt_retriever import TransfermarktRetriever
from data_sources.one_versus_one_retriever import OneVersusOneRetriever

__all__ = [
    "DataCache",
    "ESPNDataRetriever",
    "WeatherDataRetriever",
    "SportsSpecificRetriever",
    "WikipediaRetriever",
    "TavilySearchService",
    "StatsBombRetriever",
    "FirecrawlRetriever",
    "FootballDataRetriever",
    "MultiSourceRetriever",
    "TransfermarktRetriever",
    "OneVersusOneRetriever",
]
