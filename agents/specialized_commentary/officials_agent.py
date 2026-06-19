"""
Officials Agent - Research referee, VAR, and match official appointments.

Fetches referee names, per-official profiles (career, card tendency, notable matches,
nationality, age) via Tavily search, Wikipedia, and DBpedia structured lookups.
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


class OfficialsAgent(BaseAgent):
    """Research match officials and referee appointments."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        super().__init__(model_id=model_id, sport=sport, agent_type="officials")
        self.cache = cache or DataCache(ttl_seconds=86400)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(
        self,
        home_team: str,
        away_team: str,
        competition: str = "",
        fixture_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute officials research for a match fixture."""
        return await self.fetch_officials(
            home_team, away_team, competition, fixture_context,
        )

    async def fetch_officials(
        self,
        home_team: str,
        away_team: str,
        competition: str = "",
        fixture_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch referee, VAR, assistants, and fourth official for a fixture."""
        start_time = datetime.utcnow()
        match_key = f"{home_team} vs {away_team}"
        competition_label = competition or "football"

        officials_data = await self._search_officials_appointments(
            match_key, competition_label,
        )

        if not officials_data.get("referee_name"):
            return {
                "referee_name": "",
                "var_name": "",
                "assistant_names": [],
                "fourth_official_name": "",
                "officials_summary": "",
                "data_status": "unavailable",
                "reason": "No verified officials data in this run",
                "source_urls": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

        referee_profile = await self._fetch_official_profile(
            officials_data.get("referee_name", ""),
        )
        var_profile = await self._fetch_official_profile(
            officials_data.get("var_name", ""),
        ) if officials_data.get("var_name") else {}

        assistant_names = officials_data.get("assistant_names", [])
        assistant_profiles = await asyncio.gather(
            *[self._fetch_official_profile(name) for name in assistant_names[:2]],
            return_exceptions=True,
        )
        assistant_profiles_list: list[Dict[str, Any]] = [
            p for p in assistant_profiles if isinstance(p, dict) and p
        ]

        fourth_name = officials_data.get("fourth_official_name", "")
        fourth_profile = await self._fetch_official_profile(fourth_name) if fourth_name else {}

        narrative = await self._synthesize_officials_brief(
            referee_profile, var_profile, assistant_profiles_list, fourth_profile,
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="officials_research_complete",
            details={
                "match": match_key,
                "referee": officials_data.get("referee_name"),
                "duration_ms": duration_ms,
            },
        )

        return {
            "referee_name": officials_data.get("referee_name", ""),
            "referee_profile": referee_profile,
            "var_name": officials_data.get("var_name", ""),
            "var_profile": var_profile,
            "assistant_names": assistant_names,
            "assistant_profiles": assistant_profiles_list,
            "fourth_official_name": fourth_name,
            "fourth_official_profile": fourth_profile,
            "officials_summary": narrative,
            "data_status": "accepted" if officials_data.get("referee_name") else "unavailable",
            "source_urls": officials_data.get("source_urls", []),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _search_officials_appointments(
        self,
        match_key: str,
        competition_label: str,
    ) -> Dict[str, Any]:
        """Search for referee/VAR/officials appointments via Tavily."""
        if not self.search_service or not self.search_service.is_available:
            return {}

        try:
            search_result = await self.search_service.search(
                f"{match_key} {competition_label} referee VAR officials appointments",
                search_depth="advanced",
                topic="news",
                max_results=8,
                include_answer=True,
                cache_namespace="tavily_officials",
                include_domains=["fifa.com", "espn.com", "bbc.co.uk", "skysports.com", "uefa.com"],
            )
        except Exception as exc:
            logger.warning("Officials search failed for %s: %s", match_key, exc)
            return {}

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""
        all_text = "\n".join(
            str(r.get(key) or "") for r in results
            for key in ("title", "content", "raw_content", "answer")
        ) + "\n" + answer

        referee_name = self._extract_referee_name(all_text)
        var_name = self._extract_var_name(all_text)
        assistants = self._extract_assistant_names(all_text)
        fourth = self._extract_fourth_official_name(all_text)

        source_urls = [r.get("url", "") for r in results if r.get("url")][:4]

        return {
            "referee_name": referee_name,
            "var_name": var_name,
            "assistant_names": assistants,
            "fourth_official_name": fourth,
            "source_urls": source_urls,
        }

    def _extract_referee_name(self, text: str) -> str:
        patterns = [
            r"referee[s]?\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
            r"referee[:]?\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
            r"appointed\s+(?:referee|official)[:]?\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
            r"will\s+(?:be|be\s+the)\s+(?:referee|refereed\s+by)[:]?\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_var_name(self, text: str) -> str:
        patterns = [
            r"VAR\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
            r"video\s+assistant\s+referee\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_assistant_names(self, text: str) -> list[str]:
        names: list[str] = []
        pattern = re.compile(
            r"(?:assistant\s+referee|linesman|assistant)\s*(?:number)?\s*\d*\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
            flags=re.I,
        )
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if name and name not in names:
                names.append(name)
        if len(names) < 2:
            names2 = re.findall(
                r"assistant\s+referees?\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?(?:\s*(?:and|&)\s*[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)?)",
                text,
                flags=re.I,
            )
            return names2 if names2 else names
        return names[:2]

    def _extract_fourth_official_name(self, text: str) -> str:
        patterns = [
            r"fourth\s+official\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
            r"4th\s+official\s*[:–-]\s*([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group(1).strip()
        return ""

    async def _fetch_official_profile(
        self,
        name: str,
    ) -> Dict[str, Any]:
        """Fetch profile for a named official via Tavily search."""
        if not name or len(name.strip()) < 3:
            return {}

        try:
            search_result = await self.search_service.search(
                f"{name} football referee profile card tendency notable matches",
                search_depth="advanced",
                topic="general",
                max_results=4,
                include_answer=True,
                cache_namespace="tavily_referee_profile",
            )
        except Exception as exc:
            logger.warning("Official profile search failed for %s: %s", name, exc)
            return {}

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""

        profile_text = (
            answer + "\n" + "\n".join(
                str(r.get(key) or "") for r in results
                for key in ("title", "content", "raw_content")
            )
        )

        profile_prompt = f"""You are a football broadcast researcher. Summarize this match official's profile:

Name: {name}
Search results: {profile_text[:300]}

Provide:
1. Nationality and age
2. Card tendency (yellows/reds per game if available)
3. Notable matches officiated
4. Style (lenient/strict/communicative)
5. VAR history if applicable

Only use facts from the provided evidence. If data is unavailable, state that explicitly.
Keep to 2-3 sentences."""

        profile = await self.call_llm(
            prompt=profile_prompt,
            temperature=0.2,
            max_tokens=120,
        )

        return {
            "name": name,
            "nationality": "N/A",
            "profile_summary": profile,
            "source_urls": [r.get("url", "") for r in results if r.get("url")][:2],
        }

    async def _synthesize_officials_brief(
        self,
        referee_profile: Dict[str, Any],
        var_profile: Dict[str, Any],
        assistant_profiles: list[Dict[str, Any]],
        fourth_profile: Dict[str, Any],
    ) -> str:
        """Synthesize officials narrative for broadcast brief."""
        parts = []

        if referee_profile.get("profile_summary"):
            parts.append(f"Referee: {referee_profile.get('profile_summary', '')}")
        if var_profile.get("profile_summary"):
            parts.append(f"VAR: {var_profile.get('profile_summary', '')}")
        if assistant_profiles:
            assistant_text = "; ".join(
                p.get("profile_summary", p.get("name", ""))
                for p in assistant_profiles
                if p.get("profile_summary")
            )
            if assistant_text:
                parts.append(f"Assistants: {assistant_text}")
        if fourth_profile.get("profile_summary"):
            parts.append(f"Fourth Official: {fourth_profile.get('profile_summary', '')}")

        if not parts:
            return "Officials data is unavailable from verified sources in this run."

        return " | ".join(parts)

    async def close(self):
        """Clean up resources."""
        pass