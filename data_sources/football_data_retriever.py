"""
football-data.org Retriever — Structured soccer data via REST API v4.

Provides:
- League standings with HOME/AWAY/TOTAL splits
- Head-to-head records (embedded in match responses)
- Team squads with player details
- Competition scorers (top goal-scorers)
- Match schedules and results

Free tier: 10 requests/minute. Auth via X-Auth-Token header.
Get a key at https://www.football-data.org/client/register
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"

# Competition codes → human-readable names
COMPETITION_CODES: Dict[str, str] = {
    "PL":  "Premier League",
    "PD":  "La Liga",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "FL1": "Ligue 1",
    "CL":  "Champions League",
    "EL":  "Europa League",
    "WC":  "World Cup",
    "EC":  "European Championship",
}

# Common team name → football-data.org team ID lookup
TEAM_IDS: Dict[str, int] = {
    # Premier League
    "manchester united":   66,
    "man united":          66,
    "man utd":             66,
    "liverpool":           64,
    "arsenal":             57,
    "chelsea":             61,
    "manchester city":     65,
    "man city":            65,
    "tottenham":           73,
    "tottenham hotspur":   73,
    "spurs":               73,
    "newcastle":           67,
    "newcastle united":    67,
    "aston villa":         58,
    "west ham":            563,
    "west ham united":     563,
    "brighton":            397,
    "fulham":              63,
    "brentford":           402,
    "crystal palace":      354,
    "everton":             62,
    "wolves":              76,
    "wolverhampton":       76,
    "nottingham forest":   351,
    "bournemouth":         1044,
    "leicester":           338,
    # La Liga
    "barcelona":           81,
    "real madrid":         86,
    "atletico madrid":     78,
    "sevilla":             243,
    "real sociedad":       92,
    "villarreal":          94,
    # Bundesliga
    "bayern munich":       5,
    "borussia dortmund":   4,
    "rb leipzig":          721,
    # Serie A
    "juventus":            109,
    "ac milan":            98,
    "inter milan":         108,
    "napoli":              113,
    "roma":                100,
    # Ligue 1
    "paris saint-germain": 524,
    "psg":                 524,
}

TEAM_COMPETITIONS: Dict[str, str] = {
    "manchester united": "PL",
    "man united": "PL",
    "man utd": "PL",
    "liverpool": "PL",
    "arsenal": "PL",
    "chelsea": "PL",
    "manchester city": "PL",
    "man city": "PL",
    "tottenham": "PL",
    "tottenham hotspur": "PL",
    "spurs": "PL",
    "newcastle": "PL",
    "newcastle united": "PL",
    "aston villa": "PL",
    "west ham": "PL",
    "west ham united": "PL",
    "brighton": "PL",
    "fulham": "PL",
    "brentford": "PL",
    "crystal palace": "PL",
    "everton": "PL",
    "wolves": "PL",
    "wolverhampton": "PL",
    "nottingham forest": "PL",
    "bournemouth": "PL",
    "leicester": "PL",
    "barcelona": "PD",
    "real madrid": "PD",
    "atletico madrid": "PD",
    "sevilla": "PD",
    "real sociedad": "PD",
    "villarreal": "PD",
    "bayern munich": "BL1",
    "borussia dortmund": "BL1",
    "rb leipzig": "BL1",
    "juventus": "SA",
    "ac milan": "SA",
    "inter milan": "SA",
    "napoli": "SA",
    "roma": "SA",
    "paris saint-germain": "FL1",
    "psg": "FL1",
}


class FootballDataRetriever:
    """
    Async REST client for football-data.org v4 API.

    Rate-limited to 10 requests per minute (free tier) via an asyncio
    semaphore. All responses are cached via DataCache.
    """

    def __init__(
        self,
        cache: Optional[DataCache] = None,
        api_key: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY", "")
        self.cache = cache or DataCache(ttl_seconds=1800)   # 30 min default
        self._sem = asyncio.Semaphore(10)   # max 10 concurrent requests
        self._last_req_times: List[float] = []

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    # ── HTTP ─────────────────────────────────────────────────────────────────

    async def _get(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """Rate-limited async GET."""
        if not self.api_key:
            logger.warning("FOOTBALL_DATA_API_KEY not set — skipping request")
            return {}

        async with self._sem:
            # Enforce ≤10 requests per 60 seconds
            now = time.monotonic()
            self._last_req_times = [t for t in self._last_req_times if now - t < 60]
            if len(self._last_req_times) >= 10:
                sleep_for = 60 - (now - self._last_req_times[0]) + 0.5
                if sleep_for > 0:
                    logger.debug("Rate limit: sleeping %.1fs", sleep_for)
                    await asyncio.sleep(sleep_for)
            self._last_req_times.append(time.monotonic())

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(
                        f"{BASE_URL}{path}",
                        params=params or {},
                        headers={"X-Auth-Token": self.api_key},
                    )
                    r.raise_for_status()
                    return r.json()
            except httpx.HTTPStatusError as exc:
                logger.warning("football-data.org HTTP %s for %s", exc.response.status_code, path)
                return {}
            except Exception as exc:
                logger.warning("football-data.org request failed [%s]: %s", path, exc)
                return {}

    # ── standings ─────────────────────────────────────────────────────────────

    async def get_standings(
        self, competition_code: str, season: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get league standings: TOTAL, HOME, and AWAY tables.

        Args:
            competition_code: e.g. "PL" for Premier League
            season: Starting year e.g. 2025 for 2025-26 season

        Returns:
            {
              "competition": str,
              "total": [{position, team_name, played, won, draw, lost, points, gd}],
              "home":  [...same...],
              "away":  [...same...],
            }
        """
        cache_key = f"{competition_code}_{season or 'current'}"
        cached = self.cache.get("standings", cache_key)
        if cached:
            return cached

        params = {}
        if season:
            params["season"] = season

        data = await self._get(f"/competitions/{competition_code}/standings", params)
        if not data:
            return {}

        def _parse_table(standing_type: str) -> List[Dict]:
            for table in data.get("standings", []):
                if table.get("type") == standing_type:
                    return [
                        {
                            "position": row.get("position"),
                            "team_name": row.get("team", {}).get("name", ""),
                            "team_id": row.get("team", {}).get("id"),
                            "played": row.get("playedGames"),
                            "won": row.get("won"),
                            "draw": row.get("draw"),
                            "lost": row.get("lost"),
                            "points": row.get("points"),
                            "goals_for": row.get("goalsFor"),
                            "goals_against": row.get("goalsAgainst"),
                            "goal_difference": row.get("goalDifference"),
                        }
                        for row in table.get("table", [])
                    ]
            return []

        result = {
            "competition": COMPETITION_CODES.get(competition_code, competition_code),
            "competition_code": competition_code,
            "season": data.get("season", {}).get("startDate", "")[:4],
            "total": _parse_table("TOTAL"),
            "home":  _parse_table("HOME"),
            "away":  _parse_table("AWAY"),
        }
        self.cache.set("standings", cache_key, result)
        return result

    def get_team_standing(
        self,
        standings: Dict[str, Any],
        team_name: str,
    ) -> Dict[str, Any]:
        """Extract a single team's row from pre-fetched standings."""
        name_lower = team_name.lower()
        result: Dict[str, Any] = {}
        for table_type in ("total", "home", "away"):
            for row in standings.get(table_type, []):
                if name_lower in row.get("team_name", "").lower():
                    result[table_type] = row
        return result

    # ── H2H ──────────────────────────────────────────────────────────────────

    async def get_head_to_head(
        self, team1: str, team2: str, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch head-to-head record by finding a recent match between the teams
        and reading the embedded H2H data from the football-data.org match endpoint.

        Returns:
            {
              "team1": str, "team2": str,
              "total_matches": int,
              "team1_wins": int, "team2_wins": int, "draws": int,
              "total_goals": int,
              "recent_results": [{date, home, away, score, winner}],
            }
        """
        cache_key = f"{team1}|{team2}"
        cached = self.cache.get("h2h", cache_key)
        if cached:
            return cached

        # Find team IDs
        t1_id = self._resolve_team_id(team1)
        t2_id = self._resolve_team_id(team2)

        if not (t1_id and t2_id):
            logger.warning("Cannot resolve team IDs for H2H: %s vs %s", team1, team2)
            return {"team1": team1, "team2": team2, "total_matches": 0, "recent_results": []}

        # Fetch recent matches between the teams
        data = await self._get(f"/teams/{t1_id}/matches", {
            "status": "FINISHED",
            "limit": 20,
        })
        matches = data.get("matches", [])

        h2h_matches = []
        for m in matches:
            comps = m.get("homeTeam", {}), m.get("awayTeam", {})
            ids = {c.get("id") for c in comps}
            if t2_id in ids:
                score = m.get("score", {}).get("fullTime", {})
                home_team = m.get("homeTeam", {})
                away_team = m.get("awayTeam", {})
                winner_id = None
                if score.get("home") is not None and score.get("away") is not None:
                    if score["home"] > score["away"]:
                        winner_id = home_team.get("id")
                    elif score["away"] > score["home"]:
                        winner_id = away_team.get("id")
                h2h_matches.append({
                    "date": m.get("utcDate", "")[:10],
                    "home": home_team.get("name", ""),
                    "away": away_team.get("name", ""),
                    "score": f"{score.get('home', '?')}-{score.get('away', '?')}",
                    "winner_team_id": winner_id,
                    "winner": (
                        home_team.get("name") if winner_id == home_team.get("id")
                        else away_team.get("name") if winner_id == away_team.get("id")
                        else "Draw"
                    ),
                })

        h2h_matches.sort(key=lambda item: item.get("date", ""), reverse=True)
        h2h_matches = h2h_matches[:limit]
        t1_wins = sum(1 for m in h2h_matches if m.get("winner_team_id") == t1_id)
        t2_wins = sum(1 for m in h2h_matches if m.get("winner_team_id") == t2_id)
        draws = sum(1 for m in h2h_matches if m["winner"] == "Draw")

        result = {
            "team1": team1,
            "team2": team2,
            "total_matches": len(h2h_matches),
            "team1_wins": t1_wins,
            "team2_wins": t2_wins,
            "draws": draws,
            "total_goals": sum(
                sum(int(x) for x in m["score"].split("-") if x.isdigit())
                for m in h2h_matches
            ),
            "recent_results": h2h_matches,
        }
        self.cache.set("h2h", cache_key, result)
        return result

    # ── scorers ───────────────────────────────────────────────────────────────

    async def get_competition_scorers(
        self, competition_code: str, season: Optional[int] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top goal scorers for a competition."""
        cache_key = f"{competition_code}_{season or 'current'}_scorers"
        cached = self.cache.get("scorers", cache_key)
        if cached:
            return cached

        params = {"limit": limit}
        if season:
            params["season"] = season

        data = await self._get(f"/competitions/{competition_code}/scorers", params)
        scorers = [
            {
                "name": s.get("player", {}).get("name", ""),
                "team": s.get("team", {}).get("name", ""),
                "goals": s.get("goals"),
                "assists": s.get("assists"),
                "penalties": s.get("penalties"),
            }
            for s in data.get("scorers", [])
        ]
        self.cache.set("scorers", cache_key, scorers)
        return scorers

    # ── team squad ────────────────────────────────────────────────────────────

    async def get_team_squad(self, team_name: str) -> Dict[str, Any]:
        """Get team squad with player details."""
        cache_key = team_name.lower()
        cached = self.cache.get("fd_squad", cache_key)
        if cached:
            return cached

        team_id = self._resolve_team_id(team_name)
        if not team_id:
            return {"team": team_name, "squad": []}

        data = await self._get(f"/teams/{team_id}")
        squad = [
            {
                "name": p.get("name", ""),
                "position": p.get("position", ""),
                "date_of_birth": p.get("dateOfBirth", "")[:10],
                "nationality": p.get("nationality", ""),
                "shirt_number": p.get("shirtNumber"),
            }
            for p in data.get("squad", [])
        ]

        result = {
            "team": data.get("name", team_name),
            "team_id": team_id,
            "venue": data.get("venue", ""),
            "founded": data.get("founded"),
            "colors": data.get("clubColors", ""),
            "squad": squad,
        }
        self.cache.set("fd_squad", cache_key, result)
        return result

    # ── matches ───────────────────────────────────────────────────────────────

    async def get_matches(
        self,
        competition_code: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch matches for a competition, optionally filtered by date range and status.

        Args:
            competition_code: e.g. "PL"
            date_from / date_to: "YYYY-MM-DD" strings
            status: "SCHEDULED", "FINISHED", "LIVE", etc.
        """
        cache_key = f"{competition_code}_{date_from}_{date_to}_{status}"
        cached = self.cache.get("fd_matches", cache_key)
        if cached:
            return cached

        params: Dict[str, Any] = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if status:
            params["status"] = status

        data = await self._get(f"/competitions/{competition_code}/matches", params)
        matches = [
            {
                "id": m.get("id"),
                "date": m.get("utcDate", "")[:10],
                "status": m.get("status"),
                "matchday": m.get("matchday"),
                "home_team": m.get("homeTeam", {}).get("name", ""),
                "away_team": m.get("awayTeam", {}).get("name", ""),
                "score": {
                    "home": m.get("score", {}).get("fullTime", {}).get("home"),
                    "away": m.get("score", {}).get("fullTime", {}).get("away"),
                },
                "winner": m.get("score", {}).get("winner"),
            }
            for m in data.get("matches", [])
        ]
        self.cache.set("fd_matches", cache_key, matches)
        return matches

    # ── helpers ───────────────────────────────────────────────────────────────

    def _resolve_team_id(self, team_name: str) -> Optional[int]:
        return TEAM_IDS.get(team_name.lower().strip())

    def resolve_competition_code(self, team_name: str) -> Optional[str]:
        """Resolve a likely competition code from a team name."""
        return TEAM_COMPETITIONS.get(team_name.lower().strip())

    async def close(self) -> None:
        """Compatibility no-op."""
        return None
