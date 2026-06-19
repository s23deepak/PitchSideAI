"""
Transfers Agent - Research transfer window activity, contracts, and rumours.

Fetches recent signings, departures, loan moves, contract situations, market value
changes, and transfer rumours via Tavily search and domain-specific news sources.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_search_service

logger = logging.getLogger(__name__)


class TransfersAgent(BaseAgent):
    """Research transfer window activity and contract situations."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        search_service: Optional[Any] = None,
    ):
        super().__init__(model_id=model_id, sport=sport, agent_type="transfers")
        self.cache = cache or DataCache(ttl_seconds=1800)
        self.search_service = search_service or get_search_service(cache=self.cache)

    async def execute(
        self,
        home_team: str,
        away_team: str,
        players_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute transfer research for both teams."""
        return await self.fetch_transfers(
            home_team, away_team, players_context,
        )

    async def fetch_transfers(
        self,
        home_team: str,
        away_team: str,
        players_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch transfer news and contract situations for both teams."""
        start_time = datetime.utcnow()

        home_transfers, away_transfers = await asyncio.gather(
            self._research_team_transfers(home_team),
            self._research_team_transfers(away_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="transfers_research_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_team": {
                "team_name": home_team,
                **home_transfers,
            },
            "away_team": {
                "team_name": away_team,
                **away_transfers,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _research_team_transfers(self, team_name: str) -> Dict[str, Any]:
        """Research transfer window activity for one team."""
        if not self.search_service or not self.search_service.is_available:
            return {
                "recent_signings": [],
                "departures": [],
                "loan_moves": [],
                "contract_situations": [],
                "transfer_rumours": [],
                "market_value_changes": [],
                "data_status": "unavailable",
                "reason": "Search service unavailable",
            }

        current_year = datetime.utcnow().year

        try:
            search_result = await self.search_service.search(
                f"{team_name} transfers {current_year} signings departures contract news latest",
                search_depth="advanced",
                topic="news",
                max_results=8,
                include_answer=True,
                cache_namespace="tavily_transfers",
                include_domains=[
                    "goal.com", "transfermarkt.com", "skysports.com",
                    "bbc.co.uk", "theathletic.com", "espn.com",
                ],
            )
        except Exception as exc:
            logger.warning("Transfer search failed for %s: %s", team_name, exc)
            return {
                "recent_signings": [],
                "departures": [],
                "loan_moves": [],
                "contract_situations": [],
                "transfer_rumours": [],
                "market_value_changes": [],
                "data_status": "unavailable",
                "reason": str(exc),
            }

        results = search_result.get("results", []) if isinstance(search_result, dict) else []
        answer = (search_result.get("answer") or "").strip() if isinstance(search_result, dict) else ""

        if not results and not answer:
            return {
                "recent_signings": [],
                "departures": [],
                "loan_moves": [],
                "contract_situations": [],
                "transfer_rumours": [],
                "market_value_changes": [],
                "data_status": "unavailable",
                "reason": "No transfer news found in this run",
                "source_urls": [],
            }

        signings = self._extract_transfer_items(results, answer, category="signings")
        departures = self._extract_transfer_items(results, answer, category="departures")
        loans = self._extract_transfer_items(results, answer, category="loans")
        contracts = self._extract_transfer_items(results, answer, category="contracts")
        rumours = self._extract_rumour_items(results)

        source_urls = [r.get("url", "") for r in results if r.get("url")][:4]

        synthesis = await self._synthesize_transfer_brief(
            team_name, signings, departures, loans, contracts, rumours,
        )

        return {
            "recent_signings": signings,
            "departures": departures,
            "loan_moves": loans,
            "contract_situations": contracts,
            "transfer_rumours": rumours,
            "market_value_changes": [],
            "synthesis": synthesis,
            "data_status": "accepted" if (signings or departures or contracts) else "unavailable",
            "source_urls": source_urls,
        }

    def _extract_transfer_items(
        self,
        results: List[Dict[str, Any]],
        answer: str,
        category: str,
    ) -> List[Dict[str, str]]:
        """Extract transfer items by category from search results."""
        import re

        items: List[Dict[str, str]] = []
        all_text = answer + "\n" + "\n".join(
            str(r.get(key) or "") for r in results
            for key in ("title", "content", "raw_content")
        )

        category_patterns = {
            "signings": r"(?:signed|signing|signs|acquired|brought\s+in|joined|arrived?)\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)",
            "departures": r"(?:departed|left|leaves|leaving|sold|released|departure)\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)",
            "loans": r"(?:loan|loaned|on\s+loan|loan\s+move|loan\s+deal)\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)",
            "contracts": r"(?:contract|renewed|renewal|extension|expiring|out\s+of\s+contract)\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)",
        }

        pattern = category_patterns.get(category)
        if not pattern:
            return items

        blocked_names = {
            "Transfermarkt", "Sky Sports", "BBC Sport", "ESPN",
            "Goal.com", "The Athletic", "Champions League",
        }

        for match in re.finditer(pattern, all_text, flags=re.I):
            name = match.group(1).strip()
            if name in blocked_names or len(name) < 3:
                continue
            if any(item["player_name"].lower() == name.lower() for item in items):
                continue
            items.append({"player_name": name, "type": category})

        return items[:4]

    def _extract_rumour_items(self, results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract unconfirmed transfer rumours."""
        import re

        rumours: List[Dict[str, str]] = []
        all_text = "\n".join(
            str(r.get(key) or "") for r in results
            for key in ("title", "content", "raw_content")
        )

        pattern = re.compile(
            r"(?:rumour|rumor|rumoured|reported|linked|target|targeting|interested|interest|pursuing|tracking)\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'’.-]+)?)",
            flags=re.I,
        )
        blocked = {"Transfermarkt", "Sky Sports", "BBC", "ESPN", "Goal", "Champions"}

        for match in pattern.finditer(all_text):
            name = match.group(1).strip()
            if name in blocked or len(name) < 3:
                continue
            if any(r["player_name"].lower() == name.lower() for r in rumours):
                continue
            rumours.append({
                "player_name": name,
                "type": "rumour",
                "status": "unconfirmed",
            })
            if len(rumours) >= 3:
                break

        return rumours

    async def _synthesize_transfer_brief(
        self,
        team_name: str,
        signings: List[Dict[str, str]],
        departures: List[Dict[str, str]],
        loans: List[Dict[str, str]],
        contracts: List[Dict[str, str]],
        rumours: List[Dict[str, str]],
    ) -> str:
        """Synthesize transfer window narrative."""
        if not signings and not departures and not contracts and not rumours:
            return ""

        signing_text = ", ".join(item.get("player_name", "") for item in signings[:3]) or "none reported"
        departure_text = ", ".join(item.get("player_name", "") for item in departures[:3]) or "none reported"
        contract_text = ", ".join(item.get("player_name", "") for item in contracts[:3]) or "none reported"
        rumour_text = ", ".join(item.get("player_name", "") for item in rumours[:2]) or "none reported"

        prompt = f"""Summarize transfer window activity for {team_name} as a broadcast note:

Recent Signings: {signing_text}
Departures: {departure_text}
Contract Situations: {contract_text}
Rumours (unconfirmed): {rumour_text}

Provide 2-3 sentences on how these moves affect the current squad.
Only use verified facts from the provided search results. Note rumours as unconfirmed."""

        return await self.call_llm(
            prompt=prompt,
            temperature=0.2,
            max_tokens=100,
        )

    async def close(self):
        """Clean up resources."""
        pass