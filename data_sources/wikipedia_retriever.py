"""
Wikipedia Data Retriever - Fetch player biographical information via Tavily search.

Replaces mock data with real web search for:
- Player career history and achievements
- Career statistics and records
- Personal background and playing style
- Notable moments and trophies
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)


class WikipediaRetriever:
    """Retrieve player biographical data via web search (Tavily)."""

    def __init__(
        self,
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        """
        Initialize Wikipedia retriever.

        Args:
            cache: Optional DataCache instance
            search_service: Optional TavilySearchService for web search
        """
        self.cache = cache or DataCache(ttl_seconds=86400)  # 24 hours for biographical data
        self.search_service = search_service

    async def search_player(self, query: str) -> list[str]:
        """Search player pages via wikipedia when the package is available."""
        cache_key = f"search_{query}"
        cached = self.cache.get("wikipedia_search", cache_key)
        if cached:
            return cached

        try:
            import wikipedia

            wikipedia.set_lang("en")
            results = wikipedia.search(query)
        except Exception as exc:
            logger.warning("Wikipedia search failed for %s: %s", query, exc)
            results = []

        self.cache.set("wikipedia_search", cache_key, results)
        return results

    async def get_player_biography(
        self,
        player_name: str,
        sport: str = "soccer",
    ) -> Dict[str, Any]:
        """
        Get player biographical information from Tavily search.

        Args:
            player_name: Player's full name
            sport: Sport type (for context)

        Returns:
            Biographical data from search or empty dict if unavailable
        """
        cache_key = f"{player_name}_{sport}"
        cached = self.cache.get("wikipedia_biography", cache_key)
        if cached:
            return cached

        biography = {}

        # Try Tavily search first
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search_player_bio(
                    player_name, sport
                )
                if search_result.get("answer"):
                    biography = self._parse_biography_from_search(
                        player_name, sport, search_result
                    )
            except Exception as exc:
                logger.warning(
                    "Tavily search failed for player bio [%s]: %s",
                    player_name,
                    exc,
                )

        # Return empty if search failed (no fabrication)
        if not biography:
            biography = self._make_empty_biography(player_name, sport)

        self.cache.set("wikipedia_biography", cache_key, biography)
        return biography

    async def get_player_career_timeline(
        self,
        player_name: str,
    ) -> Dict[str, Any]:
        """
        Extract career timeline for player via Tavily search.

        Args:
            player_name: Player name

        Returns:
            Career timeline (clubs, years, achievements)
        """
        cache_key = f"{player_name}_timeline"
        cached = self.cache.get("wikipedia_timeline", cache_key)
        if cached:
            return cached

        timeline = {}

        # Try Tavily search first
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search(
                    f"{player_name} career history clubs timeline progression",
                    cache_namespace="tavily_career",
                )
                if search_result.get("answer"):
                    timeline = {
                        "player_name": player_name,
                        "career_summary": search_result["answer"][:500],
                        "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                        "data_source": "tavily_search",
                    }
            except Exception as exc:
                logger.warning("Tavily search failed for career timeline [%s]: %s", player_name, exc)

        # Return empty if unavailable
        if not timeline:
            timeline = {
                "player_name": player_name,
                "career_summary": "",
                "career_events": [],
                "clubs_played_for": [],
                "data_source": "unavailable",
            }

        self.cache.set("wikipedia_timeline", cache_key, timeline)
        return timeline

    async def get_player_achievements(
        self,
        player_name: str,
    ) -> Dict[str, Any]:
        """
        Get player's major achievements and awards via Tavily search.

        Args:
            player_name: Player name

        Returns:
            Achievements (trophies, awards, records)
        """
        cache_key = f"{player_name}_achievements"
        cached = self.cache.get("wikipedia_achievements", cache_key)
        if cached:
            return cached

        achievements = {}

        # Try Tavily search first
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search(
                    f"{player_name} achievements awards trophies records",
                    cache_namespace="tavily_achievements",
                )
                if search_result.get("answer"):
                    achievements = {
                        "player_name": player_name,
                        "summary": search_result["answer"][:500],
                        "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                        "data_source": "tavily_search",
                    }
            except Exception as exc:
                logger.warning("Tavily search failed for achievements [%s]: %s", player_name, exc)

        # Return empty if unavailable
        if not achievements:
            achievements = {
                "player_name": player_name,
                "major_trophies": [],
                "individual_awards": [],
                "records": [],
                "international_caps": {},
                "data_source": "unavailable",
            }

        self.cache.set("wikipedia_achievements", cache_key, achievements)
        return achievements

    async def get_manager_history(
        self,
        manager_name: str,
    ) -> Dict[str, Any]:
        """
        Get manager's career history and tactics via Tavily search.

        Args:
            manager_name: Manager/coach name

        Returns:
            Manager history (clubs managed, achievements, tactical style)
        """
        cache_key = f"{manager_name}_history"
        cached = self.cache.get("wikipedia_manager", cache_key)
        if cached:
            return cached

        manager_data = {}

        # Try Tavily search first
        if self.search_service and self.search_service.is_available:
            try:
                search_result = await self.search_service.search(
                    f"{manager_name} manager coach career history tactical",
                    cache_namespace="tavily_manager",
                )
                if search_result.get("answer"):
                    manager_data = {
                        "manager_name": manager_name,
                        "career_summary": search_result["answer"][:500],
                        "source_urls": [r.get("url", "") for r in search_result.get("results", [])],
                        "data_source": "tavily_search",
                    }
            except Exception as exc:
                logger.warning("Tavily search failed for manager history [%s]: %s", manager_name, exc)

        # Return empty if unavailable
        if not manager_data:
            manager_data = {
                "manager_name": manager_name,
                "position": None,
                "nationality": None,
                "birth_year": None,
                "career_clubs": [],
                "tactical_style": None,
                "known_formations": [],
                "philosophy": None,
                "data_source": "unavailable",
            }

        self.cache.set("wikipedia_manager", cache_key, manager_data)
        return manager_data

    # ===== Helpers =====

    def _parse_biography_from_search(
        self, player_name: str, sport: str, search_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse Tavily search results into biography structure."""
        answer = search_result.get("answer", "")
        urls = [r.get("url", "") for r in search_result.get("results", [])]
        wiki_url = next((u for u in urls if "wikipedia.org" in u), "")

        return {
            "name": player_name,
            "sport": sport,
            "career_summary": answer[:300] if answer else "",
            "playing_style": answer[300:500] if len(answer) > 300 else "",
            "source_urls": urls[:3],
            "wikipedia_url": wiki_url or f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}",
            "last_updated": datetime.utcnow().isoformat(),
            "data_source": "tavily_search",
            "birth_date": None,
            "birth_place": None,
            "nationality": None,
            "position": None,
            "height_cm": None,
            "weight_kg": None,
            "current_team": None,
            "jersey_number": None,
            "career_started": None,
            "notable_achievements": [
                r.get("content", "")[:100] for r in search_result.get("results", [])[:3]
            ],
        }

    def _make_empty_biography(
        self, player_name: str, sport: str
    ) -> Dict[str, Any]:
        """Return empty biography (no fabrication)."""
        logger.warning("Wikipedia bio lookup failed for %s — no data available", player_name)
        return {
            "name": player_name,
            "sport": sport,
            "birth_date": None,
            "birth_place": None,
            "nationality": None,
            "position": None,
            "height_cm": None,
            "weight_kg": None,
            "current_team": None,
            "jersey_number": None,
            "career_summary": "",
            "playing_style": "",
            "career_started": None,
            "notable_achievements": [],
            "wikipedia_url": f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}",
            "last_updated": datetime.utcnow().isoformat(),
            "data_source": "unavailable",
        }

    async def close(self) -> None:
        """Compatibility no-op."""
        return None
