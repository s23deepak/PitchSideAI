"""
Venue Details Agent - Research stadium capacity, surface, altitude, and history.

Fetches venue infrastructure facts (capacity, surface type, roof, altitude, pitch dimensions,
opened date, atmosphere) via Tavily search, Open-Meteo elevation API, and Jina AI Reader.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import httpx
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_search_service

logger = logging.getLogger(__name__)


class VenueDetailsAgent(BaseAgent):
    """Research stadium/venue infrastructure and history."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        super().__init__(model_id=model_id, sport=sport, agent_type="venue_details")
        self.cache = cache or DataCache(ttl_seconds=86400)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(
        self,
        venue: str,
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> Dict[str, Any]:
        """Execute venue details research."""
        return await self.fetch_venue_details(venue, latitude, longitude)

    async def fetch_venue_details(
        self,
        venue: str,
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> Dict[str, Any]:
        """Fetch comprehensive venue infrastructure details."""
        start_time = datetime.utcnow()

        if not venue:
            return {
                "venue_name": "",
                "capacity": None,
                "opened_date": "",
                "surface_type": "",
                "roof_status": "",
                "altitude_m": None,
                "pitch_dimensions": {},
                "atmosphere_notes": "",
                "notable_events": [],
                "data_status": "unavailable",
                "reason": "Venue name not provided",
                "source_urls": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

        venue_data = await self._search_venue(venue)
        altitude = await self._get_altitude(latitude, longitude)

        has_data = venue_data.get("data_status") != "unavailable"

        if not has_data:
            return {
                "venue_name": venue,
                "capacity": None,
                "opened_date": "",
                "surface_type": "",
                "roof_status": "",
                "altitude_m": altitude,
                "pitch_dimensions": {},
                "atmosphere_notes": "",
                "notable_events": [],
                "data_status": "unavailable",
                "reason": venue_data.get("reason", "No verified venue data in this run"),
                "source_urls": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

        narrative = await self._synthesize_venue_narrative(
            venue, venue_data, altitude,
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="venue_research_complete",
            details={
                "venue": venue,
                "capacity": venue_data.get("capacity"),
                "duration_ms": duration_ms,
            },
        )

        return {
            "venue_name": venue,
            "capacity": venue_data.get("capacity"),
            "opened_date": venue_data.get("opened_date", ""),
            "surface_type": venue_data.get("surface_type", ""),
            "roof_status": venue_data.get("roof_status", ""),
            "altitude_m": altitude,
            "pitch_dimensions": {
                "length_m": venue_data.get("pitch_length_m"),
                "width_m": venue_data.get("pitch_width_m"),
            },
            "atmosphere_notes": venue_data.get("atmosphere_notes", ""),
            "notable_events": venue_data.get("notable_events", []) or [],
            "narrative": narrative,
            "data_status": "accepted",
            "source_urls": venue_data.get("source_urls", []),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _search_venue(self, venue: str) -> Dict[str, Any]:
        """Search for venue details via Tavily."""
        if not self.search_service or not self.search_service.is_available:
            return {
                "data_status": "unavailable",
                "reason": "Search service unavailable",
            }

        try:
            search_result = await self.search_service.search(
                f"{venue} stadium capacity surface pitch dimensions roof altitude history",
                search_depth="advanced",
                topic="general",
                max_results=5,
                include_answer=True,
                cache_namespace="tavily_venue",
                include_domains=["wikipedia.org", "stadiumguide.com", "espn.com", "bbc.co.uk"],
            )
        except Exception as exc:
            logger.warning("Venue search failed for %s: %s", venue, exc)
            return {
                "data_status": "unavailable",
                "reason": str(exc),
            }

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""

        if not results and not answer:
            return {
                "data_status": "unavailable",
                "reason": "No venue search results",
            }

        all_text = answer + "\n" + "\n".join(
            str(r.get(key) or "") for r in results
            for key in ("title", "content", "raw_content")
        )

        import re
        capacity_match = re.search(r"capacity\s*[:–]\s*([\d,]+)", all_text, flags=re.I)
        capacity = int(capacity_match.group(1).replace(",", "")) if capacity_match else None

        surface_match = re.search(
            r"(?:surface|pitch|playing\s+surface)[:]?\s*(grass|natural\s+grass|artificial\s+turf|hybrid|clay|hard)",
            all_text,
            flags=re.I,
        )
        surface_type = surface_match.group(1).strip() if surface_match else ""

        roof_match = re.search(
            r"(?:roof|retractable)[:]?\s*(open|closed|retractable|none|no|partial)",
            all_text,
            flags=re.I,
        )
        roof_status = roof_match.group(1).strip() if roof_match else ""

        opened_match = re.search(
            r"(?:opened|built|established|inaugurated)\s+(?:in|on)?\s*(?:\d{1,2}\s+\w+\s+)?(\d{4})",
            all_text,
            flags=re.I,
        )
        opened_date = opened_match.group(1) if opened_match else ""

        source_urls = [r.get("url", "") for r in results if r.get("url")][:3]

        return {
            "capacity": capacity,
            "surface_type": surface_type,
            "roof_status": roof_status,
            "opened_date": opened_date,
            "source_urls": source_urls,
            "data_status": "accepted",
        }

    async def _get_altitude(self, latitude: float, longitude: float) -> Optional[float]:
        """Fetch venue altitude from Open-Meteo elevation API if coordinates available."""
        if not latitude or not longitude:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.open-meteo.com/v1/elevation",
                    params={"latitude": latitude, "longitude": longitude},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elevation = data.get("elevation")
                    if isinstance(elevation, (int, float)):
                        return float(elevation[0]) if isinstance(elevation, list) else float(elevation)
                return None
        except Exception as exc:
            logger.warning("Altitude fetch failed for %.4f, %.4f: %s", latitude, longitude, exc)
            return None

    async def _synthesize_venue_narrative(
        self,
        venue: str,
        venue_data: Dict[str, Any],
        altitude: Optional[float],
    ) -> str:
        """Generate venue narrative with verified facts."""
        if venue_data.get("data_status") == "unavailable":
            return "Venue details are unavailable from trusted sources for this fixture."

        capacity = venue_data.get("capacity")
        surface = venue_data.get("surface_type") or "unavailable"
        roof = venue_data.get("roof_status") or "unavailable"
        opened = venue_data.get("opened_date") or "unavailable"

        facts = []
        if capacity:
            facts.append(f"Capacity: {capacity}")
        if surface != "unavailable":
            facts.append(f"Surface: {surface}")
        if roof != "unavailable":
            facts.append(f"Roof: {roof}")
        if opened != "unavailable":
            facts.append(f"Opened: {str(opened)}")
        if altitude is not None:
            facts.append(f"Altitude: {altitude:.0f}m")

        if not facts:
            return "Confirmed venue infrastructure details are thin in this run."

        prompt = f"""Build a venue description for a {self.sport} match broadcast:

Venue: {venue}
{', '.join(facts)}

Provide 1-2 sentences about how this venue's characteristics may affect the match atmosphere and play.
Only use the facts provided. Keep concise."""

        narrative = await self.call_llm(
            prompt=prompt,
            temperature=0.3,
            max_tokens=100,
        )
        return narrative

    async def close(self):
        """Clean up resources."""
        pass