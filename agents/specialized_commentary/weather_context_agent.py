"""
Weather Context Agent - Analyze and contextualize weather impact on match.

Gathers weather conditions and provides sport-specific impact analysis
for how weather will affect tactical play.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
from agents.base import BaseAgent
from data_sources import WeatherDataRetriever, DataCache
from data_sources.factory import get_search_service

logger = logging.getLogger(__name__)


class WeatherContextAgent(BaseAgent):
    """Analyze weather conditions and impacts."""

    def __init__(
        self,
        model_id: str = "us.nova-sonic-1:0",  # Fast model for weather analysis
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
    ):
        """Initialize weather context agent."""
        super().__init__(
            model_id=model_id,
            sport=sport,
            agent_type="weather_context",
        )
        self.cache = cache or DataCache(ttl_seconds=1800)  # 30 min for weather
        self.weather_retriever = WeatherDataRetriever(
            cache=self.cache,
            search_service=get_search_service(cache=self.cache),
        )

    async def execute(
        self,
        venue: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
    ) -> Dict[str, Any]:
        """Execute weather analysis."""
        return await self.analyze_match_weather(
            venue,
            latitude,
            longitude,
            match_datetime,
        )

    async def analyze_match_weather(
        self,
        venue: str,
        latitude: float,
        longitude: float,
        match_datetime: str,
    ) -> Dict[str, Any]:
        """
        Analyze weather conditions and their impact on the match.

        Args:
            venue: Stadium/venue name
            latitude: Venue latitude
            longitude: Venue longitude
            match_datetime: ISO datetime of match

        Returns:
            Weather analysis with conditions and impact
        """
        start_time = datetime.utcnow()

        # Get weather data
        weather_data = await self.weather_retriever.get_match_day_weather(
            venue,
            latitude,
            longitude,
            match_datetime,
            self.sport,
        )

        # Get forecast trend
        forecast = await self.weather_retriever.get_forecast_trend(
            venue,
            latitude,
            longitude,
            match_datetime,
            hours_window=3,
        )

        # Contextualize for sport
        impact = await self.weather_retriever.contextualize_weather(weather_data, self.sport)

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Generate narrative about weather impact
        weather_narrative = await self._generate_weather_narrative(
            weather_data,
            forecast,
            impact,
        )

        self.log_event(
            event_type="weather_analysis_complete",
            details={
                "venue": venue,
                "temp_c": weather_data.get("temp_c"),
                "conditions": weather_data.get("conditions"),
                "duration_ms": duration_ms,
            },
        )

        return {
            "venue": venue,
            "match_datetime": match_datetime,
            "current_conditions": {
                "temperature_c": weather_data.get("temp_c"),
                "feels_like_c": weather_data.get("feels_like_c"),
                "conditions": weather_data.get("conditions"),
                "humidity": weather_data.get("humidity"),
                "wind_kmh": weather_data.get("wind_kmh"),
                "wind_direction": weather_data.get("wind_direction"),
                "visibility_km": weather_data.get("visibility_km"),
            },
            "forecast": forecast.get("forecast_hours", []),
            "sport_impact": impact,
            "narrative": weather_narrative,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _generate_weather_narrative(
        self,
        weather_data: Dict[str, Any],
        forecast: Dict[str, Any],
        impact: Dict[str, Any],
    ) -> str:
        """
        Generate narrative about weather impact.

        Args:
            weather_data: Current weather
            forecast: Weather forecast
            impact: Sport-specific impact analysis

        Returns:
            Weather commentary narrative
        """
        temp = weather_data.get("temp_c")
        conditions = weather_data.get("conditions") or weather_data.get("weather_summary", "Weather unavailable")
        wind = weather_data.get("wind_kmh")
        forecast_trend = forecast.get("general_trend") or forecast.get("forecast_summary", "Unavailable")
        sport_impact = impact.get("general", "Weather impact unavailable")

        current_summary = []
        if temp is not None:
            current_summary.append(f"{temp}°C")
        if conditions:
            current_summary.append(str(conditions))
        if wind is not None:
            current_summary.append(f"Wind {wind:.1f} km/h")
        if not current_summary:
            current_summary = ["Weather details unavailable"]

        prompt = f"""Create a weather commentary narrative for a {self.sport} match:

Current: {', '.join(current_summary)}
Forecast Trend: {forecast_trend}
Sport Impact: {sport_impact}

Provide:
1. How weather will affect match flow
2. Tactical adjustments teams might make
3. Key weather factor to watch

Keep to 3-4 sentences, suitable for match commentary."""

        narrative = await self.call_bedrock(
            prompt=prompt,
            temperature=0.3,
            max_tokens=125,  # 125 for local dev (250 in production)
        )

        return narrative

    async def close(self):
        """Clean up resources."""
        if hasattr(self.weather_retriever, "close"):
            await self.weather_retriever.close()
