"""
Weather Data Retriever - Fetch weather conditions at match venues via Tavily search.

Integrates with Tavily to get:
- Current weather at venue (temperature, wind, humidity, conditions)
- Weather impact analysis (how it affects different sports)
"""

import logging
import re
from typing import Any, Dict, Optional
from datetime import datetime

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)


class WeatherDataRetriever:
    """Retrieve weather data from Tavily search."""

    def __init__(
        self,
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        """
        Initialize weather retriever.

        Args:
            cache: Optional DataCache instance
            search_service: Optional TavilySearchService for web search
        """
        self.cache = cache or DataCache(ttl_seconds=1800)  # 30 min for weather
        self.search_service = search_service

    async def get_match_day_weather(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
        sport: str = "soccer",
    ) -> Dict[str, Any]:
        """
        Get weather at match venue for specific match time via Tavily.

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

        weather_data = {}

        # Try Tavily search for weather
        if self.search_service and self.search_service.is_available:
            try:
                # Parse date from ISO format
                date_str = match_datetime.split("T")[0] if "T" in match_datetime else match_datetime
                search_result = await self.search_service.search_weather(venue_name, date_str)
                if search_result.get("answer"):
                    weather_data = self._parse_weather_from_search(
                        venue_name, latitude, longitude, match_datetime, search_result
                    )
            except Exception as exc:
                logger.warning(
                    "Tavily weather search failed for %s: %s",
                    venue_name,
                    exc,
                )

        # Return empty if search failed
        if not weather_data:
            weather_data = self._make_empty_weather(venue_name, latitude, longitude, match_datetime)

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
        Get weather forecast trend around match time via Tavily.

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

        forecast_data = {}

        # Try Tavily search for forecast
        if self.search_service and self.search_service.is_available:
            try:
                date_str = match_datetime.split("T")[0] if "T" in match_datetime else match_datetime
                search_result = await self.search_service.search_weather(venue_name, date_str)
                if search_result.get("answer"):
                    forecast_data = {
                        "venue": venue_name,
                        "match_datetime": match_datetime,
                        "forecast_summary": search_result["answer"][:500],
                        "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                        "data_source": "tavily_search",
                    }
            except Exception as exc:
                logger.warning("Tavily forecast search failed for %s: %s", venue_name, exc)

        # Return empty if unavailable
        if not forecast_data:
            forecast_data = {
                "venue": venue_name,
                "match_datetime": match_datetime,
                "forecast_hours": [],
                "general_trend": "",
                "data_source": "unavailable",
            }

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
        raw_conditions = weather_data.get("conditions") or ""
        conditions = str(raw_conditions).lower()
        wind_kmh = self._safe_float(weather_data.get("wind_kmh"), default=0.0)
        humidity = self._safe_int(weather_data.get("humidity"), default=50)
        temp_c = self._safe_float(weather_data.get("temp_c"), default=20.0)

        # Sport-specific impacts
        impacts = {
            "soccer": self._analyze_soccer_weather(conditions, wind_kmh, humidity),
            "cricket": self._analyze_cricket_weather(conditions, wind_kmh, humidity),
            "basketball": self._analyze_basketball_weather(temp_c, humidity),
            "rugby": self._analyze_rugby_weather(conditions, wind_kmh),
            "tennis": self._analyze_tennis_weather(wind_kmh, humidity),
        }

        return impacts.get(sport, {"general": ""})

    # ===== Weather Impact Analysis =====

    def _analyze_soccer_weather(
        self, conditions: str, wind_kmh: float, humidity: int
    ) -> Dict[str, str]:
        """Analyze weather impact for soccer."""
        impacts = []

        if "rain" in conditions:
            impacts.append("Wet pitch favors long-ball tactics, reduces passing accuracy")
        elif conditions == "clear":
            impacts.append("Dry pitch favors possession-based play, fast-paced")

        if wind_kmh > 15:
            impacts.append(f"Strong wind ({wind_kmh:.1f} kmh) affects crosses and long shots")
        elif wind_kmh < 5:
            impacts.append("Calm conditions favor technical, short-passing football")

        if humidity > 80:
            impacts.append("High humidity may slow down pace in second half")

        return {"general": "; ".join(impacts) or "Normal weather conditions"}

    def _analyze_cricket_weather(
        self, conditions: str, wind_kmh: float, humidity: int
    ) -> Dict[str, str]:
        """Analyze weather impact for cricket."""
        impacts = []

        if "cloud" in conditions:
            impacts.append("Overcast conditions favor seam bowling")
        if "rain" in conditions:
            impacts.append("Rain risk - may affect match duration")

        if wind_kmh > 20:
            impacts.append("Strong wind affects fielding and ball trajectory")

        if humidity > 75:
            impacts.append("High humidity creates swing bowling conditions")

        return {"general": "; ".join(impacts) or "Favorable batting conditions"}

    def _analyze_basketball_weather(
        self, temp_c: float, humidity: int
    ) -> Dict[str, str]:
        """Analyze weather impact for basketball (mostly indoor)."""
        impacts = []

        if temp_c > 30:
            impacts.append("Hot conditions may affect indoor court climate")
        if humidity > 80:
            impacts.append("High humidity may make court conditions slippery")

        return {"general": "; ".join(impacts) or "Normal indoor conditions"}

    def _analyze_rugby_weather(
        self, conditions: str, wind_kmh: float
    ) -> Dict[str, str]:
        """Analyze weather impact for rugby."""
        impacts = []

        if "rain" in conditions:
            impacts.append("Wet conditions favor defensive, close-play rugby")
        if wind_kmh > 15:
            impacts.append("Strong wind affects kicking game and passes")

        return {"general": "; ".join(impacts) or "Good conditions for open rugby"}

    def _analyze_tennis_weather(
        self, wind_kmh: float, humidity: int
    ) -> Dict[str, str]:
        """Analyze weather impact for tennis."""
        impacts = []

        if wind_kmh > 10:
            impacts.append(f"Wind ({wind_kmh:.1f} kmh) affects serve and ball control")
        if humidity > 70:
            impacts.append("High humidity slows down ball speed")

        return {"general": "; ".join(impacts) or "Ideal playing conditions"}

    # ===== Helpers =====

    def _parse_weather_from_search(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
        search_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse Tavily search results into weather structure."""
        answer = search_result.get("answer", "")
        urls = [r.get("url", "") for r in search_result.get("results", [])]
        conditions = self._extract_conditions(answer)
        temp_c = self._extract_float(answer, r"(-?\d+(?:\.\d+)?)\s*°?\s*C")
        humidity = self._extract_int(answer, r"(\d{1,3})\s*%\s*humidity")
        wind_kmh = self._extract_float(answer, r"(\d+(?:\.\d+)?)\s*(?:km/?h|kmh|kph)")

        return {
            "venue": venue_name,
            "coordinates": {"lat": latitude, "lon": longitude},
            "match_datetime": match_datetime,
            "conditions": conditions,
            "temp_c": temp_c,
            "humidity": humidity,
            "wind_kmh": wind_kmh,
            "weather_summary": answer[:300] if answer else "",
            "source_urls": urls[:3],
            "last_updated": datetime.utcnow().isoformat(),
            "data_source": "tavily_search",
        }

    def _make_empty_weather(
        self,
        venue_name: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
    ) -> Dict[str, Any]:
        """Return empty weather data (no fabrication)."""
        logger.warning("Weather data unavailable for %s", venue_name)
        return {
            "venue": venue_name,
            "coordinates": {"lat": latitude, "lon": longitude},
            "match_datetime": match_datetime,
            "conditions": "",
            "weather_summary": "",
            "temp_c": None,
            "humidity": None,
            "wind_kmh": None,
            "last_updated": datetime.utcnow().isoformat(),
            "data_source": "unavailable",
        }

    def _extract_conditions(self, text: str) -> str:
        """Extract a simple weather condition from free text."""
        lowered = text.lower()
        for key, value in (
            ("thunderstorm", "thunderstorm"),
            ("storm", "storm"),
            ("heavy rain", "rain"),
            ("rain", "rain"),
            ("partly cloudy", "partly_cloudy"),
            ("mostly cloudy", "cloudy"),
            ("cloudy", "cloudy"),
            ("sunny", "clear"),
            ("clear", "clear"),
            ("snow", "snow"),
        ):
            if key in lowered:
                return value
        return ""

    def _extract_float(self, text: str, pattern: str) -> Optional[float]:
        """Extract a float using a regex pattern."""
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return None

    def _extract_int(self, text: str, pattern: str) -> Optional[int]:
        """Extract an int using a regex pattern."""
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None

    def _safe_float(self, value: Any, default: float) -> float:
        """Return a float fallback when a value is missing or invalid."""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value: Any, default: int) -> int:
        """Return an int fallback when a value is missing or invalid."""
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    async def close(self) -> None:
        """Compatibility no-op."""
        return None
