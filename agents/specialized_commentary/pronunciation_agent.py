"""
Pronunciation Agent - Fetch verified phonetic spellings and audio for player names.

Retrieves pronunciation from Forvo (audio recordings), YouGlish (YouTube context),
and Wikipedia IPA transcriptions. Never guesses pronunciations.
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


class PronunciationAgent(BaseAgent):
    """Fetch verified phonetic spellings from audio sources."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        super().__init__(model_id=model_id, sport=sport, agent_type="pronunciation")
        self.cache = cache or DataCache(ttl_seconds=86400)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(
        self,
        key_players: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute pronunciation lookup for key players."""
        return await self.fetch_pronunciations(key_players)

    async def fetch_pronunciations(
        self,
        key_players: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fetch verified phonetic spellings for key player names."""
        start_time = datetime.utcnow()

        if not key_players:
            return {
                "phonetics": [],
                "data_status": "unavailable",
                "reason": "No players provided",
                "timestamp": datetime.utcnow().isoformat(),
            }

        names = [
            player.get("name", "")
            for player in key_players[:10]
            if isinstance(player, dict) and player.get("name")
        ]

        if not names:
            return {
                "phonetics": [],
                "data_status": "unavailable",
                "reason": "No valid player names",
                "timestamp": datetime.utcnow().isoformat(),
            }

        phonetic_tasks = [self._fetch_phonetic_for_name(name) for name in names]
        phonetics_raw = await asyncio.gather(*phonetic_tasks, return_exceptions=True)
        phonetics: list[Dict[str, Any]] = [
            p for p in phonetics_raw if isinstance(p, dict) and p
        ]

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        verified_count = sum(1 for p in phonetics if p.get("source") != "unavailable")
        self.log_event(
            event_type="pronunciation_complete",
            details={
                "players_checked": len(names),
                "verified_count": verified_count,
                "duration_ms": duration_ms,
            },
        )

        return {
            "phonetics": phonetics,
            "data_status": "accepted" if len(phonetics) > 0 else "unavailable",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _fetch_phonetic_for_name(self, name: str) -> Dict[str, Any]:
        """Fetch phonetic spelling for one player name from Forvo/YouGlish/Wikipedia."""
        if not name or len(name.strip()) < 3:
            return {
                "name": name,
                "phonetic": "",
                "source": "unavailable",
                "reason": "Name too short",
            }

        phonetic = ""
        source_label = "unavailable"

        forvo_result = await self._call_forvo(name)
        if forvo_result is not None:
            phonetic = forvo_result
            source_label = "forvo"
        else:
            youglish_result = await self._call_youglish(name)
            if youglish_result is not None:
                phonetic = youglish_result
                source_label = "youglish"
            else:
                wiki_ipa = await self._fetch_wikipedia_ipa(name)
                if wiki_ipa is not None:
                    phonetic = wiki_ipa
                    source_label = "wikipedia"

        if not phonetic:
            return {
                "name": name,
                "phonetic": "",
                "source": "unavailable",
                "reason": "No pronunciation data from verified sources",
            }

        return {
            "name": name,
            "phonetic": phonetic,
            "source": source_label,
        }

    async def _call_forvo(self, name: str) -> Optional[str]:
        """Fetch pronunciation from Forvo API."""
        try:
            from data_sources.forvo_retriever import ForvoRetriever
            forvo = ForvoRetriever(cache=self.cache)
            result = await forvo._do_fetch(
                query=name,
                params={"language": "en", "api_key": ""},
            )
            data, _, _ = result
            if isinstance(data, dict) and not data.get("error"):
                items = data.get("items", [])
                if items:
                    return items[0].get("word", "")
            return None
        except Exception as exc:
            logger.debug("Forvo lookup failed for %s: %s", name, exc)
            return None

    async def _call_youglish(self, name: str) -> Optional[str]:
        """Fetch pronunciation from YouGlish API."""
        try:
            from data_sources.youglish_retriever import YouglishRetriever
            youglish = YouglishRetriever(cache=self.cache)
            result = await youglish._do_fetch(
                query=name,
                params={"language": "en", "accent": ""},
            )
            data, _, _ = result
            if isinstance(data, dict) and not data.get("error"):
                return data.get("phonetic") or data.get("query", "")
            return None
        except Exception as exc:
            logger.debug("YouGlish lookup failed for %s: %s", name, exc)
            return None

    async def _fetch_wikipedia_ipa(self, name: str) -> Optional[str]:
        """Fetch IPA transcription from Wikipedia search results."""
        if not self.search_service or not self.search_service.is_available:
            return None

        try:
            search_result = await self.search_service.search(
                f"{name} pronunciation IPA",
                search_depth="basic",
                topic="general",
                max_results=2,
                include_answer=False,
                cache_namespace="tavily_pronunciation",
            )
        except Exception as exc:
            logger.debug("Wikipedia IPA search failed for %s: %s", name, exc)
            return None

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        text = "\n".join(
            str(r.get(key) or "") for r in results
            for key in ("title", "content", "raw_content")
        )

        ipa_match = re.search(r"IPA\s*[:]\s*[/]\s*([^/]+)\s*[/]", text)
        if ipa_match:
            return ipa_match.group(1).strip()

        return None

    async def close(self):
        """Clean up resources."""
        pass