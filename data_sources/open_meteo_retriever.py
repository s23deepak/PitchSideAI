"""
Open-Meteo Retriever — hourly weather forecast, pitch conditions.

Uses Open-Meteo's free weather API (no auth required) for:
- Temperature, wind speed/direction, humidity, precipitation probability
- Cloud cover, visibility, UV index
- Pitch condition inference from weather data
"""
from __future__ import annotations

from typing import Any

import httpx

from data_sources.base import BaseRetriever
from data_sources.rate_limiter import RateLimiter
from core.source_catalog import get_source_tier

OPEN_METEO_API_BASE = "https://api.open-meteo.com/v1"
OPEN_METEO_TIMEOUT = 10


class OpenMeteoRetriever(BaseRetriever):
    def __init__(self, cache=None):
        super().__init__(
            source_name="open_meteo",
            source_tier=get_source_tier("open_meteo"),
            rate_limiter=RateLimiter(requests_per_minute=60),
            cache=cache,
        )

    async def _do_fetch(
        self, query: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], int, list[str]]:
        lat = params.get("latitude")
        lon = params.get("longitude")
        if not lat or not lon:
            lat, lon = self._parse_coords(query)
        if not lat or not lon:
            return {"error": "No coordinates provided"}, 0, []

        async with httpx.AsyncClient(timeout=OPEN_METEO_TIMEOUT) as client:
            resp = await client.get(
                f"{OPEN_METEO_API_BASE}/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": (
                        "temperature_2m,relative_humidity_2m,precipitation_probability,"
                        "wind_speed_10m,wind_direction_10m,cloud_cover,visibility,uv_index"
                    ),
                    "timezone": "auto",
                },
            )
            raw_text = resp.text
            raw_bytes = len(raw_text.encode("utf-8"))

            if resp.status_code != 200:
                return {"error": f"Open-Meteo returned {resp.status_code}"}, raw_bytes, []

            try:
                data = resp.json()
            except Exception:
                data = {"raw": raw_text[:500]}

            return data, raw_bytes, [str(resp.url)]

    @staticmethod
    def _parse_coords(query: str) -> tuple[float | None, float | None]:
        parts = query.split(",")
        if len(parts) >= 2:
            try:
                return float(parts[0].strip()), float(parts[1].strip())
            except ValueError:
                pass
        return None, None