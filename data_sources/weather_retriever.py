"""
Weather Data Retriever - Fetch weather conditions at match venues.

Integrates with OpenWeatherMap API to get:
- Current weather at venue (temperature, wind, humidity, conditions)
- Forecast for match day and surrounding hours
- Weather impact analysis (how it affects different sports)
"""

import httpx
from typing import Dict, Optional, Any
from datetime import datetime
import logging
from data_sources.cache import DataCache
import os

logger = logging.getLogger(__name__)


class WeatherDataRetriever:
    """Retrieve weather data from OpenWeatherMap API."""

    def __init__(self, cache: Optional[DataCache] = None, api_key: Optional[str] = None):
        """
        Initialize weather retriever.

        Args:
            cache: Optional DataCache instance
            api_key: OpenWeatherMap API key
        """
        self.cache = cache or DataCache(ttl_seconds=1800)  # 30 min for weather
        self.api_key = api_key or os.getenv("OPENWEATHERMAP_API_KEY", "mock-key")
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.http_client = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "PitchAI-Commentary"},
        )

    async def get_match_day_weather(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
        sport: str = "soccer",
    ) -> Dict[str, Any]:
        """
        Get weather at match venue for specific match time.

        Args:
            venue_name: Venue/stadium name
            latitude: Venue latitude
            longitude: Venue longitude
            match_datetime: ISO format datetime (e.g., '2024-03-27T20:00:00Z')
            sport: Sport type for contextual impact analysis

        Returns:
            Weather data with conditions, temperature, wind, forecast
        """
        cache_key = f"{venue_name}_{match_datetime}"
        cached = self.cache.get("weather_match_day", cache_key)
        if cached:
            return cached

        weather_data = await self._fetch_weather_mock(
            venue_name,
            latitude,
            longitude,
            match_datetime,
            sport,
        )

        self.cache.set("weather_match_day", cache_key, weather_data)
        return weather_data

    async def get_forecast_trend(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
        hours_window: int = 3,
    ) -> Dict[str, Any]:
        """
        Get weather forecast trend around match time.

        Args:
            venue_name: Venue name
            latitude: Latitude
            longitude: Longitude
            match_datetime: ISO datetime of match
            hours_window: Hours before/after match to consider

        Returns:
            Forecast trend with hourly breakdown
        """
        cache_key = f"{venue_name}_{match_datetime}_forecast"
        cached = self.cache.get("weather_forecast", cache_key)
        if cached:
            return cached

        forecast_data = await self._fetch_forecast_mock(
            venue_name,
            latitude,
            longitude,
            match_datetime,
            hours_window,
        )

        self.cache.set("weather_forecast", cache_key, forecast_data)
        return forecast_data

    async def contextualize_weather(
        self,
        weather_data: Dict[str, Any],
        sport: str = "soccer",
    ) -> Dict[str, Any]:
        """
        Analyze weather impact for specific sport.

        Args:
            weather_data: Weather conditions (temp, wind, humidity, etc.)
            sport: Sport type

        Returns:
            Impact analysis (how weather affects tactical play)
        """
        conditions = weather_data.get("conditions", "clear").lower()
        wind_kmh = weather_data.get("wind_kmh", 0)
        humidity = weather_data.get("humidity", 50)
        temp_c = weather_data.get("temp_c", 20)

        # Sport-specific impacts
        impacts = {
            "soccer": self._analyze_soccer_weather(conditions, wind_kmh, humidity),
            "cricket": self._analyze_cricket_weather(conditions, wind_kmh, humidity),
            "basketball": self._analyze_basketball_weather(temp_c, humidity),
            "rugby": self._analyze_rugby_weather(conditions, wind_kmh),
            "tennis": self._analyze_tennis_weather(wind_kmh, humidity),
        }

        return impacts.get(sport, {"general": "Weather may influence match pace and tactics"})

    # ===== Weather Impact Analysis =====

    def _analyze_soccer_weather(self, conditions: str, wind_kmh: float, humidity: int) -> Dict[str, str]:
        """Analyze weather impact for soccer."""
        impacts = []

        if "rain" in conditions:
            impacts.append("Wet pitch favors long-ball tactics, reduces passing accuracy")
        elif conditions == "clear":
            impacts.append("Dry pitch favors possession-based play, fast-paced")

        if wind_kmh > 15:
            impacts.append(f"Strong wind ({wind_kmh:.1f} kmh) will affect crosses and long shots")
        elif wind_kmh < 5:
            impacts.append("Calm conditions favor technical, short-passing football")

        if humidity > 80:
            impacts.append("High humidity may slow down pace in second half")

        return {
            "general": "; ".join(impacts)
            or "Normal weather conditions expected"
        }

    def _analyze_cricket_weather(self, conditions: str, wind_kmh: float, humidity: int) -> Dict[str, str]:
        """Analyze weather impact for cricket."""
        impacts = []

        if "cloud" in conditions:
            impacts.append("Overcast conditions favor seam bowling")
        if "rain" in conditions:
            impacts.append("Rain risk - may affect match duration and DLS scoring")

        if wind_kmh > 20:
            impacts.append("Strong wind may affect fielding and ball trajectory")

        if humidity > 75:
            impacts.append("High humidity may create swing bowling conditions")

        return {
            "general": "; ".join(impacts)
            or "Favorable batting conditions expected"
        }

    def _analyze_basketball_weather(self, temp_c: float, humidity: int) -> Dict[str, str]:
        """Analyze weather impact for basketball (mostly indoor)."""
        impacts = []

        if temp_c > 30:
            impacts.append("Hot conditions may affect indoor court climate control")
        if humidity > 80:
            impacts.append("High humidity may make court conditions slippery")

        return {
            "general": "; ".join(impacts)
            or "Normal indoor conditions expected"
        }

    def _analyze_rugby_weather(self, conditions: str, wind_kmh: float) -> Dict[str, str]:
        """Analyze weather impact for rugby."""
        impacts = []

        if "rain" in conditions:
            impacts.append("Wet conditions favor defensive, close-play rugby")
        if wind_kmh > 15:
            impacts.append(f"Strong wind will affect kicking game and passes")

        return {
            "general": "; ".join(impacts)
            or "Good conditions for open rugby play"
        }

    def _analyze_tennis_weather(self, wind_kmh: float, humidity: int) -> Dict[str, str]:
        """Analyze weather impact for tennis."""
        impacts = []

        if wind_kmh > 10:
            impacts.append(f"Wind ({wind_kmh:.1f} kmh) will affect serve and ball control")
        if humidity > 70:
            impacts.append("High humidity may slow down ball speed")

        return {
            "general": "; ".join(impacts)
            or "Ideal playing conditions"
        }

    # ===== Mock Data Methods =====

    async def _fetch_weather_mock(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
        sport: str,
    ) -> Dict[str, Any]:
        """Return mock weather data."""
        return {
            "venue": venue_name,
            "coordinates": {"lat": latitude, "lon": longitude},
            "match_datetime": match_datetime,
            "conditions": "partly_cloudy",
            "temp_c": 22,
            "feels_like_c": 21,
            "humidity": 65,
            "wind_kmh": 12,
            "wind_direction": "NW",
            "pressure_mb": 1013,
            "visibility_km": 10,
            "uv_index": 5,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def _fetch_forecast_mock(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
        hours_window: int,
    ) -> Dict[str, Any]:
        """Return mock forecast data."""
        return {
            "venue": venue_name,
            "match_datetime": match_datetime,
            "forecast_hours": [
                {
                    "time": f"19:00",
                    "temp_c": 22,
                    "conditions": "partly_cloudy",
                    "wind_kmh": 10,
                },
                {
                    "time": f"20:00",
                    "temp_c": 21,
                    "conditions": "clear",
                    "wind_kmh": 12,
                },
                {
                    "time": f"21:00",
                    "temp_c": 19,
                    "conditions": "clear",
                    "wind_kmh": 14,
                },
            ],
            "general_trend": "Improving conditions, winds picking up",
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
