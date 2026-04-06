"""
Matchup Analysis Agent - Analyze 1v1 player matchups and positional battles.

Identifies critical matchups, positional strengths, and tactical battles
that will define the match. Uses FBref stats for real player comparison.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_fbref_retriever
from data_sources.player_profile_db import get_player_db

logger = logging.getLogger(__name__)


class MatchupAnalysisAgent(BaseAgent):
    """Analyze key player matchups and positional battles."""

    def __init__(
        self,
        model_id: str = "us.nova-lite-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        fbref_retriever: Optional[Any] = None,
    ):
        """Initialize matchup analysis agent."""
        super().__init__(
            model_id=model_id,
            sport=sport,
            agent_type="matchup_analysis",
        )
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.fbref = fbref_retriever or (get_fbref_retriever(cache=self.cache) if sport == "soccer" else None)

    async def execute(
        self,
        home_lineup: List[Dict[str, str]],
        away_lineup: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Execute matchup analysis."""
        return await self.analyze_key_matchups(home_lineup, away_lineup)

    async def analyze_key_matchups(
        self,
        home_lineup: List[Dict[str, str]],
        away_lineup: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Analyze critical player matchups between lineups.

        Args:
            home_lineup: Home team starting XI
            away_lineup: Away team starting XI

        Returns:
            Key matchups and tactical analysis
        """
        start_time = datetime.utcnow()

        # Identify positions and key battles
        positional_analysis = await self._analyze_positional_strength(
            home_lineup,
            away_lineup,
        )

        # Generate critical matchup pairs
        critical_matchups = await self._identify_critical_matchups(
            home_lineup,
            away_lineup,
        )

        # Assess weak points
        weak_points = await self._identify_weak_points(home_lineup, away_lineup)

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="matchup_analysis_complete",
            details={
                "critical_matchups": len(critical_matchups),
                "duration_ms": duration_ms,
            },
        )

        return {
            "critical_matchups": critical_matchups,
            "positional_strength": positional_analysis,
            "weak_points": weak_points,
            "tactical_implications": await self._generate_tactical_implications(
                critical_matchups,
                weak_points,
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _identify_critical_matchups(
        self,
        home_lineup: List[Dict[str, str]],
        away_lineup: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Identify key 1v1 matchups."""
        # Simple heuristic: match by position and form
        matchups = []

        for home_player in home_lineup[:6]:  # Key outfield players
            for away_player in away_lineup[:6]:
                if home_player.get("position") == away_player.get("position"):
                    matchup = await self._analyze_player_matchup(home_player, away_player)
                    if matchup:
                        matchups.append(matchup)
                    break

        return matchups[:5]  # Top 5 matchups

    async def _analyze_player_matchup(
        self,
        player1: Dict[str, str],
        player2: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        """Analyze individual player matchup with real stats."""
        db = get_player_db()
        p1_name = player1.get('name', '')
        p2_name = player2.get('name', '')

        # Check local DB first
        player1_stats = db.get_season_stats(p1_name, self.sport, "25-26", "fbref") or {}
        player2_stats = db.get_season_stats(p2_name, self.sport, "25-26", "fbref") or {}

        # Only hit FBref for players not in the DB
        if not player1_stats or not player2_stats:
            if self.fbref and self.fbref.is_available:
                try:
                    tasks = []
                    tasks.append(
                        self.fbref.get_player_season_stats(p1_name, stat_type="standard")
                        if not player1_stats else asyncio.sleep(0, result=player1_stats)
                    )
                    tasks.append(
                        self.fbref.get_player_season_stats(p2_name, stat_type="standard")
                        if not player2_stats else asyncio.sleep(0, result=player2_stats)
                    )
                    p1_result, p2_result = await asyncio.gather(*tasks, return_exceptions=True)
                    if isinstance(p1_result, dict) and p1_result:
                        player1_stats = p1_result
                        db.upsert_season_stats(p1_name, self.sport, "25-26", "fbref", p1_result)
                    if isinstance(p2_result, dict) and p2_result:
                        player2_stats = p2_result
                        db.upsert_season_stats(p2_name, self.sport, "25-26", "fbref", p2_result)
                except Exception as exc:
                    logger.warning("FBref stats fetch failed: %s", exc)

        # Build prompt with stats if available
        stats_context = ""
        if player1_stats:
            goals1 = player1_stats.get('goals', 0) or 0
            assists1 = player1_stats.get('assists', 0) or 0
            stats_context += f"\n{player1.get('name')}: {goals1}G {assists1}A this season"
        if player2_stats:
            goals2 = player2_stats.get('goals', 0) or 0
            assists2 = player2_stats.get('assists', 0) or 0
            stats_context += f"\n{player2.get('name')}: {goals2}G {assists2}A this season"
        if not stats_context:
            stats_context = "\nNo verified season stats were available for this matchup."

        prompt = f"""As an elite {self.sport} analyst, analyze matchup: {player1.get('name', 'Player 1')} vs {player2.get('name', 'Player 2')}
Position: {player1.get('position', 'Unknown')}
{stats_context}

Provide:
1. Statistical advantage
2. Tactical edge
3. Key battle prediction

Only analyze from the verified data above and the listed positions. If statistics are unavailable, say that explicitly.

Keep to 2-3 sentences."""

        analysis = await self.call_bedrock(
            prompt=prompt,
            temperature=0.3,
            max_tokens=100,
        )

        return {
            "player1": player1.get("name", "Unknown"),
            "player2": player2.get("name", "Unknown"),
            "position": player1.get("position", "Unknown"),
            "player1_stats": player1_stats,
            "player2_stats": player2_stats,
            "analysis": analysis,
            "importance": "high",
        }

    async def _analyze_positional_strength(
        self,
        home_lineup: List[Dict[str, str]],
        away_lineup: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Analyze positional strengths."""
        home_summary = self._summarize_lineup(home_lineup)
        away_summary = self._summarize_lineup(away_lineup)
        assessment = {}

        for zone in ("Defense", "Midfield", "Attack"):
            key = zone.lower()
            home_zone = home_summary.get(key, {})
            away_zone = away_summary.get(key, {})
            if home_zone.get("contribution", 0) > away_zone.get("contribution", 0):
                verdict = f"{zone}: slight edge to home side"
            elif away_zone.get("contribution", 0) > home_zone.get("contribution", 0):
                verdict = f"{zone}: slight edge to away side"
            else:
                verdict = f"{zone}: balanced on verified data"
            assessment[zone] = {
                "home_players": home_zone.get("players", 0),
                "away_players": away_zone.get("players", 0),
                "home_contribution": home_zone.get("contribution", 0),
                "away_contribution": away_zone.get("contribution", 0),
                "verdict": verdict,
            }

        return assessment

    async def _identify_weak_points(
        self,
        home_lineup: List[Dict[str, str]],
        away_lineup: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Identify defensive weak points."""
        return {
            "home_vulnerabilities": self._infer_vulnerabilities(home_lineup),
            "away_vulnerabilities": self._infer_vulnerabilities(away_lineup),
        }

    def _summarize_lineup(self, lineup: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Summarize players and contributions by zone."""
        summary = {
            "defense": {"players": 0, "contribution": 0},
            "midfield": {"players": 0, "contribution": 0},
            "attack": {"players": 0, "contribution": 0},
        }

        for player in lineup:
            zone = self._position_zone(player.get("position", ""))
            stats = player.get("stats", {}) if isinstance(player.get("stats"), dict) else {}
            contribution = (stats.get("goals", 0) or 0) + (stats.get("assists", 0) or 0)
            summary[zone]["players"] += 1
            summary[zone]["contribution"] += contribution

        return summary

    def _infer_vulnerabilities(self, lineup: List[Dict[str, Any]]) -> List[str]:
        """Infer structural vulnerabilities from the verified lineup composition."""
        summary = self._summarize_lineup(lineup)
        vulnerabilities = []
        if summary["defense"]["players"] < 3:
            vulnerabilities.append("Thin defensive cover in the verified lineup")
        if summary["midfield"]["players"] < 2:
            vulnerabilities.append("Limited midfield control based on listed starters")
        if summary["attack"]["players"] < 2:
            vulnerabilities.append("Low attacking depth in the verified lineup")
        if not vulnerabilities:
            vulnerabilities.append("No obvious structural weakness from verified lineup data")
        return vulnerabilities

    def _position_zone(self, position: str) -> str:
        """Map a position label into a broad zone."""
        pos = (position or "").upper()
        if pos in {"GK", "CB", "LB", "RB", "LWB", "RWB", "DEFENDER"} or pos.endswith("B"):
            return "defense"
        if pos in {"CM", "CDM", "CAM", "LM", "RM", "MIDFIELDER", "MF"} or pos.endswith("M"):
            return "midfield"
        return "attack"

    async def _generate_tactical_implications(
        self,
        matchups: List[Dict[str, Any]],
        weak_points: Dict[str, Any],
    ) -> str:
        """Generate tactical implications from matchup analysis."""
        prompt = f"""As an elite {self.sport} analyst, based on key matchups and weak points, what tactical approaches will likely emerge?

Matchups Summary: {len(matchups)} critical battles identified

Provide expected tactical adjustments and key battles to watch."""

        implications = await self.call_bedrock(
            prompt=prompt,
            temperature=0.4,
            max_tokens=100,  # 100 for local dev (200 in production)
        )

        return implications

    async def close(self):
        """Clean up resources."""
        pass

