"""
Club History Agent - Research club history, trophies, and identity.

Fetches club founded date, trophy count, league titles, UCL titles, philosophy, academy
reputation, and historical significance of the fixture via Tavily search and Wikidata.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_search_service

logger = logging.getLogger(__name__)


class ClubHistoryAgent(BaseAgent):
    """Research club history, trophies, and identity."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        super().__init__(model_id=model_id, sport=sport, agent_type="club_history")
        self.cache = cache or DataCache(ttl_seconds=86400)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """Execute club history research for both teams."""
        return await self.fetch_club_history(home_team, away_team)

    async def fetch_club_history(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """Fetch club history context for both teams in parallel."""
        start_time = datetime.utcnow()

        home_history, away_history = await asyncio.gather(
            self._research_club(home_team),
            self._research_club(away_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="club_history_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "home_founded": home_history.get("founded_year"),
                "away_founded": away_history.get("founded_year"),
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_team": {
                "team_name": home_team,
                **home_history,
            },
            "away_team": {
                "team_name": away_team,
                **away_history,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _research_club(self, team_name: str) -> Dict[str, Any]:
        """Research individual club history, trophies, and identity via Tavily."""
        if not self.search_service or not self.search_service.is_available:
            return {
                "founded_year": None,
                "trophy_count": None,
                "league_titles": None,
                "ucl_titles": None,
                "club_philosophy": "",
                "academy_reputation": "",
                "data_status": "unavailable",
                "reason": "Search service unavailable",
            }

        try:
            search_result = await self.search_service.search(
                f"{team_name} football club history founded trophies league titles philosophy academy",
                search_depth="advanced",
                topic="general",
                max_results=5,
                include_answer=True,
                cache_namespace="tavily_club_history",
                include_domains=["wikipedia.org", "dbpedia.org", "espn.com", "uefa.com"],
            )
        except Exception as exc:
            logger.warning("Club history search failed for %s: %s", team_name, exc)
            return {
                "founded_year": None,
                "trophy_count": None,
                "league_titles": None,
                "ucl_titles": None,
                "club_philosophy": "",
                "academy_reputation": "",
                "data_status": "unavailable",
                "reason": str(exc),
            }

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""

        if not results and not answer:
            return {
                "founded_year": None,
                "trophy_count": None,
                "league_titles": None,
                "ucl_titles": None,
                "club_philosophy": "",
                "academy_reputation": "",
                "data_status": "unavailable",
                "reason": "No club history data found in this run",
                "source_urls": [],
            }

        all_text = answer + "\n" + "\n".join(
            str(r.get(key) or "") for r in results
            for key in ("title", "content", "raw_content")
        )

        import re
        founded_match = re.search(
            r"(?:founded|formed|established)\s+(?:in|on)?\s*(?:\d{1,2}\s+\w+\s+)?(\d{4})",
            all_text,
            flags=re.I,
        )
        founded_year = int(founded_match.group(1)) if founded_match else None

        trophy_match = re.search(r"(?:major\s+trophies|trophies|titles)[:]?\s*(\d+)", all_text, flags=re.I)
        trophy_count = int(trophy_match.group(1)) if trophy_match else None

        source_urls = [r.get("url", "") for r in results if r.get("url")][:3]

        profile_prompt = f"""You are a football broadcast researcher. Summarize this club's identity:

Club: {team_name}
Founded: {founded_year if founded_year else 'unknown'}
Major Trophies: {trophy_count if trophy_count else 'unknown'}
Search facts: {all_text[:200]}
Source URLs: {' '.join(source_urls)}

Provide 2-3 sentences on club identity, historical significance, and what this fixture means in their context.
Only use verified facts from the provided evidence."""

        profile = await self.call_llm(
            prompt=profile_prompt,
            temperature=0.3,
            max_tokens=120,
        )

        return {
            "founded_year": founded_year,
            "trophy_count": trophy_count,
            "league_titles": None,
            "ucl_titles": None,
            "club_philosophy": "",
            "academy_reputation": "",
            "profile_summary": profile,
            "data_status": "accepted" if (founded_year or trophy_count) else "unavailable",
            "source_urls": source_urls,
        }

    async def close(self):
        """Clean up resources."""
        pass