"""
Matchup Analysis Agent - Analyze 1v1 player matchups and positional battles.

Identifies critical matchups, positional strengths, and tactical battles
that will define the match. Uses MultiSource retriever (ESPN → FootballData → Transfermarkt)
for real player comparison.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
import re
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_fbref_retriever  # Returns MultiSourceRetriever
from data_sources.player_profile_db import get_player_db

logger = logging.getLogger(__name__)

TACTICAL_REFUSAL_PATTERNS = (
    "i'm unable",
    "i am unable",
    "i can't provide",
    "i cannot provide",
    "unable to provide",
    "cannot analyze",
    "can't analyze",
    "not enough information to provide",
)


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
            "validation_status": "accepted" if critical_matchups else "degraded",
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
        """Identify key 1v1 matchups - pairing opposite positions (attacker vs defender)."""
        matchup_tasks = []
        away_by_position = self._players_by_position(away_lineup)
        home_by_position = self._players_by_position(home_lineup)
        seen_pairs: set[tuple[str, str]] = set()
        used_names: set[str] = set()

        def add_pair(player1: Dict[str, str], player2: Optional[Dict[str, str]]) -> None:
            if not player2:
                return
            if self._is_placeholder_player(player1) or self._is_placeholder_player(player2):
                return
            p1_name = player1.get("name", "")
            p2_name = player2.get("name", "")
            if p1_name in used_names or p2_name in used_names:
                return
            pair_key = tuple(sorted((p1_name, p2_name)))
            if not pair_key[0] or not pair_key[1] or pair_key in seen_pairs:
                return
            seen_pairs.add(pair_key)
            used_names.update(pair_key)
            matchup_tasks.append(self._analyze_player_matchup(player1, player2))

        # Match home attackers against away defenders
        for home_player in home_lineup:
            home_pos = home_player.get("position", "").upper()
            if home_pos not in {"GK", "GOALKEEPER"}:
                add_pair(home_player, self._find_opponent(home_pos, away_by_position, used_names))

        # Also catch away attackers against home defenders; the first pass can miss these.
        for away_player in away_lineup:
            away_pos = away_player.get("position", "").upper()
            if away_pos not in {"GK", "GOALKEEPER"}:
                add_pair(away_player, self._find_opponent(away_pos, home_by_position, used_names))

        # Execute all matchup analyses IN PARALLEL
        if matchup_tasks:
            results = await asyncio.gather(*matchup_tasks, return_exceptions=True)
            matchups = [r for r in results if isinstance(r, dict) and r]
            return matchups[:5]  # Top 5 matchups

        return self._candidate_matchups_without_positions(home_lineup, away_lineup)

    def _players_by_position(self, lineup: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        by_position: Dict[str, List[Dict[str, str]]] = {}
        for player in lineup:
            pos = player.get("position", "").upper()
            if pos:
                by_position.setdefault(pos, []).append(player)
        return by_position

    def _first_for_positions(
        self,
        players_by_position: Dict[str, List[Dict[str, str]]],
        positions: List[str],
        excluded_names: Optional[set[str]] = None,
    ) -> Optional[Dict[str, str]]:
        excluded_names = excluded_names or set()
        for position in positions:
            players = players_by_position.get(position)
            for player in players or []:
                if player.get("name", "") not in excluded_names:
                    return player
        return None

    def _is_placeholder_player(self, player: Dict[str, Any]) -> bool:
        name = str(player.get("name") or "").strip()
        if not name or name.lower() == "unknown":
            return True
        if name.endswith("-"):
            return True
        if any(token in {"Getty", "Reuters", "Image", "Images", "Photo", "For"} for token in name.split()):
            return True
        return bool(re.search(r"\bPlayer\s+\d+\b", name, flags=re.I))

    def _candidate_matchups_without_positions(
        self,
        home_lineup: List[Dict[str, Any]],
        away_lineup: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        home_candidates = [player for player in home_lineup if not self._is_placeholder_player(player)]
        away_candidates = [player for player in away_lineup if not self._is_placeholder_player(player)]
        matchups = []
        for home_player, away_player in zip(home_candidates[:3], away_candidates[:3]):
            source_urls = []
            for player in (home_player, away_player):
                for url in player.get("source_urls") or []:
                    if url and url not in source_urls:
                        source_urls.append(url)
            p1_name = home_player.get("name", "Home player")
            p2_name = away_player.get("name", "Away player")
            matchups.append({
                "player1": p1_name,
                "player2": p2_name,
                "position": "candidate",
                "player1_stats": {},
                "player2_stats": {},
                "analysis": (
                    f"Candidate duel only: fixture evidence names {p1_name} and {p2_name}, "
                    "but roles and lineups are not confirmed. Watch whether they share the "
                    "same channel before leaning on this matchup live."
                ),
                "importance": "medium",
                "source_urls": source_urls,
                "candidate_status": "fixture-evidence; not confirmed starter",
            })
        return matchups

    def _has_useful_stats(self, stats: Dict[str, Any]) -> bool:
        if not isinstance(stats, dict) or stats.get("error"):
            return False
        for key in ("appearances", "starts", "minutes", "goals", "assists", "shots", "tackles", "interceptions"):
            value = stats.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return True
        return False

    def _find_opponent(
        self,
        position: str,
        opponents_by_position: Dict[str, List[Dict[str, str]]],
        excluded_names: Optional[set[str]] = None,
    ) -> Optional[Dict[str, str]]:
        pos = (position or "").upper()
        if pos in {"ST", "CF", "FW", "FWD", "STRIKER", "FORWARD"}:
            return self._first_for_positions(opponents_by_position, ["CB", "DEFENDER", "LCB", "RCB"], excluded_names)
        if pos in {"LW", "LM"}:
            return self._first_for_positions(opponents_by_position, ["RB", "RWB", "DEFENDER"], excluded_names)
        if pos in {"RW", "RM", "WINGER"}:
            return self._first_for_positions(opponents_by_position, ["LB", "LWB", "DEFENDER"], excluded_names)
        if pos in {"CAM", "AM"}:
            return self._first_for_positions(opponents_by_position, ["CDM", "DM", "CM", "MIDFIELDER"], excluded_names)
        if pos in {"CM", "CDM", "DM", "MIDFIELDER", "MF"}:
            return self._first_for_positions(opponents_by_position, ["CM", "CDM", "DM", "CAM", "MIDFIELDER", "MF"], excluded_names)
        return None

    async def _analyze_player_matchup(
        self,
        player1: Dict[str, str],
        player2: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        """Analyze individual player matchup with real stats."""
        db = get_player_db()
        p1_name = player1.get('name', '')
        p2_name = player2.get('name', '')
        p1_team = player1.get('team', '')
        p2_team = player2.get('team', '')

        if self._is_placeholder_player(player1) or self._is_placeholder_player(player2):
            return None

        # Check local DB first
        player1_stats = db.get_season_stats(p1_name, self.sport, "25-26", "fbref") or {}
        player2_stats = db.get_season_stats(p2_name, self.sport, "25-26", "fbref") or {}

        # Only hit MultiSource retriever for players not in the DB
        if not player1_stats or not player2_stats:
            if self.fbref and self.fbref.is_available:
                try:
                    tasks = []
                    # MultiSourceRetriever.get_player_stats(player_name, team_name, sport)
                    # MultiSourceRetriever.get_player_stats(player_name, team_name, sport)
                    tasks.append(
                        self.fbref.get_player_stats(p1_name, p1_team or "Unknown", self.sport)
                        if not player1_stats else asyncio.sleep(0, result=player1_stats)
                    )
                    tasks.append(
                        self.fbref.get_player_stats(p2_name, p2_team or "Unknown", self.sport)
                        if not player2_stats else asyncio.sleep(0, result=player2_stats)
                    )
                    p1_result, p2_result = await asyncio.gather(*tasks, return_exceptions=True)
                    if isinstance(p1_result, dict) and p1_result:
                        player1_stats = p1_result
                        db.upsert_season_stats(p1_name, self.sport, "25-26", p1_result.get("data_source", "multi"), p1_result)
                    if isinstance(p2_result, dict) and p2_result:
                        player2_stats = p2_result
                        db.upsert_season_stats(p2_name, self.sport, "25-26", p2_result.get("data_source", "multi"), p2_result)
                except Exception as exc:
                    logger.warning("MultiSource stats fetch failed: %s", exc)

        # Build prompt with stats if available
        stats_context = ""
        player1_stats_useful = self._has_useful_stats(player1_stats)
        player2_stats_useful = self._has_useful_stats(player2_stats)

        if player1_stats_useful:
            goals1 = player1_stats.get('goals', 0) or 0
            assists1 = player1_stats.get('assists', 0) or 0
            stats_context += f"\n{player1.get('name')}: {goals1}G {assists1}A this season"
        if player2_stats_useful:
            goals2 = player2_stats.get('goals', 0) or 0
            assists2 = player2_stats.get('assists', 0) or 0
            stats_context += f"\n{player2.get('name')}: {goals2}G {assists2}A this season"
        if not stats_context:
            return self._deterministic_matchup_note(player1, player2)

        prompt = f"""As an elite {self.sport} analyst, analyze matchup: {player1.get('name', 'Player 1')} vs {player2.get('name', 'Player 2')}
Position: {player1.get('position', 'Unknown')}
{stats_context}

Provide:
1. Statistical advantage
2. Tactical edge
3. Key battle prediction

Only analyze from the verified data above and the listed positions. If statistics are unavailable, say that explicitly.

Keep to 2-3 sentences."""

        analysis = await self.call_llm(
            prompt=prompt,
            temperature=0.3,
            max_tokens=100,
        )

        return {
            "player1": player1.get("name", "Unknown"),
            "player2": player2.get("name", "Unknown"),
            "position": player1.get("position", "Unknown"),
            "player1_stats": player1_stats if player1_stats_useful else {},
            "player2_stats": player2_stats if player2_stats_useful else {},
            "analysis": analysis,
            "importance": "high",
        }

    def _deterministic_matchup_note(
        self,
        player1: Dict[str, str],
        player2: Dict[str, str],
    ) -> Dict[str, Any]:
        p1_name = player1.get("name", "Player 1")
        p2_name = player2.get("name", "Player 2")
        p1_pos = player1.get("position", "Unknown")
        p2_pos = player2.get("position", "Unknown")
        watch = self._position_watchpoint(p1_pos, p2_pos)
        analysis = (
            f"No verified season-stat edge was available for {p1_name} vs {p2_name}. "
            f"Use it as a live watchpoint: {watch}"
        )
        return {
            "player1": p1_name,
            "player2": p2_name,
            "position": p1_pos,
            "player1_stats": {},
            "player2_stats": {},
            "analysis": analysis,
            "importance": "medium",
        }

    def _position_watchpoint(self, player1_position: str, player2_position: str) -> str:
        p1_zone = self._position_zone(player1_position)
        p2_zone = self._position_zone(player2_position)
        if {p1_zone, p2_zone} == {"attack", "defense"}:
            return (
                "first body contact, who controls the channel, whether cover arrives before the turn, "
                "and whether the duel ends in a shot, foul, or forced recycle."
            )
        if p1_zone == "midfield" and p2_zone == "midfield":
            return (
                "who receives on the half-turn, who wins the second ball after pressure, "
                "and which player can turn a safe pass into territory."
            )
        if "midfield" in {p1_zone, p2_zone} and "defense" in {p1_zone, p2_zone}:
            return (
                "whether the midfielder can draw out the defensive line, whether the defender passes runners on cleanly, "
                "and who controls the space in front of the back four."
            )
        return (
            "who gets cover first, who controls the next pass, and whether the duel changes territory."
        )

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
        if not lineup:
            return []

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
        if not matchups:
            return ""

        prompt = f"""As an elite {self.sport} analyst, based on key matchups and weak points, what tactical approaches will likely emerge?

Matchups Summary: {len(matchups)} critical battles identified

Provide expected tactical adjustments and key battles to watch."""

        implications = await self.call_llm(
            prompt=prompt,
            temperature=0.4,
            max_tokens=100,  # 100 for local dev (200 in production)
        )

        if self._is_refusal_text(implications):
            return self._degraded_tactical_implications()

        return implications

    def _is_refusal_text(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        return any(pattern in normalized for pattern in TACTICAL_REFUSAL_PATTERNS)

    def _degraded_tactical_implications(self) -> str:
        return (
            "Tactical implications are limited because verified matchup detail is incomplete. "
            "Use the listed duels as live watchpoints and update once confirmed team shapes are available."
        )

    async def close(self):
        """Clean up resources."""
        pass
