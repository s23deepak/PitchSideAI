"""
Manager Profiles Agent - Research both teams' manager/coach profiles.

Fetches manager name, nationality, career history, tactical philosophy, preferred formations,
achievements, and head-to-head with opponent manager via Tavily, Wikipedia, and DBpedia.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import logging
import re
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_search_service

logger = logging.getLogger(__name__)


class ManagerProfilesAgent(BaseAgent):
    """Profile both teams' managers/coaches."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        super().__init__(model_id=model_id, sport=sport, agent_type="manager_profiles")
        self.cache = cache or DataCache(ttl_seconds=86400)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(
        self,
        home_team: str,
        away_team: str,
        players_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute manager profile research for both teams."""
        return await self.profile_both_managers(
            home_team, away_team, players_context,
        )

    async def profile_both_managers(
        self,
        home_team: str,
        away_team: str,
        players_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch and synthesize manager profiles for both teams."""
        start_time = datetime.utcnow()

        home_manager_name, away_manager_name = await asyncio.gather(
            self._resolve_manager_name(home_team),
            self._resolve_manager_name(away_team),
        )

        home_profile, away_profile = await asyncio.gather(
            self._profile_manager(home_manager_name, home_team),
            self._profile_manager(away_manager_name, away_team),
        )

        manager_h2h = ""
        if home_profile.get("data_status") != "unavailable" and away_profile.get("data_status") != "unavailable":
            manager_h2h = await self._synthesize_manager_h2h(
                home_profile, away_profile, home_team, away_team,
            )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="manager_profiles_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "home_manager": home_manager_name,
                "away_manager": away_manager_name,
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_manager": {
                "name": home_manager_name,
                "team": home_team,
                **home_profile,
            },
            "away_manager": {
                "name": away_manager_name,
                "team": away_team,
                **away_profile,
            },
            "manager_h2h": manager_h2h,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _resolve_manager_name(self, team_name: str) -> str:
        """Search for the current manager/coach name for a team."""
        if not self.search_service or not self.search_service.is_available:
            return ""

        try:
            search_result = await self.search_service.search(
                f"{team_name} current manager head coach {datetime.utcnow().year}",
                search_depth="advanced",
                topic="news",
                max_results=3,
                include_answer=True,
                cache_namespace="tavily_manager",
                include_domains=["espn.com", "bbc.co.uk", "skysports.com", "transfermarkt.com"],
            )
        except Exception as exc:
            logger.warning("Manager search failed for %s: %s", team_name, exc)
            return ""

        results: list[Dict[str, Any]] = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer: str = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""

        name = self._extract_manager_name(answer, team_name)
        if not name:
            name = self._extract_manager_name_from_results(results, team_name)

        return name

    def _extract_manager_name(self, text: str, team_name: str) -> str:
        teams_pattern = re.escape(team_name)
        patterns = [
            rf"{teams_pattern}\s+(?:manager|coach|head\s+coach|boss)[:]?\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)",
            rf"(?:manager|coach|head\s+coach)\s+of\s+{teams_pattern}[,]?\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)\s*(?:is|was)",
            rf"led\s+by\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)[,]?\s*(?:the\s+)?(?:manager|coach|head\s+coach)\s+of\s+{teams_pattern}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_manager_name_from_results(
        self, results: list[Dict[str, Any]], team_name: str
    ) -> str:
        for result in results:
            title = result.get("title", "")
            name_match = re.search(
                r"([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+){1,2})",
                title,
            )
            if name_match:
                candidate = name_match.group(1).strip()
                blocked = {"Champions League", "Premier League", "La Liga", "Serie A", "Bundesliga"}
                if candidate not in blocked and len(candidate) > 4:
                    return candidate
        return ""

    async def _profile_manager(
        self,
        name: str,
        team_name: str,
    ) -> Dict[str, Any]:
        """Build a manager profile with biography, philosophy, and achievements."""
        if not name or len(name.strip()) < 3:
            return {"data_status": "unavailable", "reason": "Manager name not resolved"}

        try:
            search_result = await self.search_service.search(
                f"{name} manager coach career history tactical philosophy formations achievements",
                search_depth="advanced",
                topic="general",
                max_results=5,
                include_answer=True,
                cache_namespace="tavily_manager_profile",
            )
        except Exception as exc:
            logger.warning("Manager profile search failed for %s: %s", name, exc)
            return {"data_status": "unavailable", "reason": str(exc)}

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""

        profile_text = (
            answer + "\n" + "\n".join(
                str(r.get(key) or "") for r in results
                for key in ("title", "content", "raw_content")
            )
        )

        has_data = bool(answer or results)

        profile_prompt = f"""You are a football broadcast researcher. Profile this manager for a match broadcast:

Manager: {name} ({team_name})
Search data: {profile_text[:300]}

Provide:
1. Nationality
2. Career history (key clubs managed)
3. Tactical philosophy and preferred formation
4. Major achievements (trophies won)
5. Current season context and approach

Only use facts from the provided evidence. If data is unavailable, state that explicitly.
Keep to 3-4 sentences."""

        profile = await self.call_llm(
            prompt=profile_prompt,
            temperature=0.3,
            max_tokens=150,
        )

        return {
            "name": name,
            "team": team_name,
            "nationality": "N/A",
            "career_summary": "",
            "tactical_philosophy": "",
            "preferred_formation": "",
            "achievements": [],
            "profile_summary": profile,
            "source_urls": [r.get("url", "") for r in results if r.get("url")][:2],
            "data_status": "accepted" if has_data else "unavailable",
        }

    async def _synthesize_manager_h2h(
        self,
        home_profile: Dict[str, Any],
        away_profile: Dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> str:
        """Generate manager head-to-head narrative."""
        home_name = home_profile.get("name", home_team)
        away_name = away_profile.get("name", away_team)

        prompt = f"""Compare these two managers' tactical approaches for a {self.sport} match:

Home: {home_name} ({home_team})
Profile: {home_profile.get('profile_summary', 'Profile unavailable')[:150]}

Away: {away_name} ({away_team})
Profile: {away_profile.get('profile_summary', 'Profile unavailable')[:150]}

Provide 1-2 sentences on how their tactical philosophies might clash or complement.
Only compare what is in the provided evidence."""

        return await self.call_llm(
            prompt=prompt,
            temperature=0.3,
            max_tokens=80,
        )

    async def close(self):
        """Clean up resources."""
        pass