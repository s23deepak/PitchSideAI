"""
Data retrieval module for multi-agent commentary system.

Provides specialized data retrievers for:
- ESPN API (team/player statistics)
- Weather data (OpenWeatherMap)
- Sport-specific data (goal.com, cricbuzz.com)
- Wikipedia (player biographies)
- RAG system (historical context)
"""

from data_sources.cache import DataCache
from data_sources.espn_retriever import ESPNDataRetriever
from data_sources.weather_retriever import WeatherDataRetriever
from data_sources.sports_specific_retriever import SportsSpecificRetriever
from data_sources.wikipedia_retriever import WikipediaRetriever

__all__ = [
    "DataCache",
    "ESPNDataRetriever",
    "WeatherDataRetriever",
    "SportsSpecificRetriever",
    "WikipediaRetriever",
]
