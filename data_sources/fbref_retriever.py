"""
FBref Retriever — Structured soccer statistics via soccerdata.

Provides detailed player and team statistics scraped from FBref
(https://fbref.com) using the soccerdata library:

- Player season stats  (goals, assists, xG, xAG, pass%, dribbles, tackles …)
- Team season stats    (possession %, press intensity, defensive actions …)
- Team match logs      (recent results with detailed match stats)
- Schedule / H2H       (fixtures filtered to matchups between two teams)

soccerdata caches scraped data locally in ~/.local/share/soccerdata/,
so repeated calls within a session are instant.

Supported leagues:
  "ENG-Premier League", "ESP-La Liga", "GER-Bundesliga",
  "ITA-Serie A",        "FRA-Ligue 1"
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

# Map short sport/league aliases to soccerdata league IDs
LEAGUE_ALIASES: Dict[str, str] = {
    "premier league":       "ENG-Premier League",
    "epl":                  "ENG-Premier League",
    "eng-premier league":   "ENG-Premier League",
    "la liga":              "ESP-La Liga",
    "esp-la liga":          "ESP-La Liga",
    "bundesliga":           "GER-Bundesliga",
    "ger-bundesliga":       "GER-Bundesliga",
    "serie a":              "ITA-Serie A",
    "ita-serie a":          "ITA-Serie A",
    "ligue 1":              "FRA-Ligue 1",
    "fra-ligue 1":          "FRA-Ligue 1",
}

DEFAULT_LEAGUE   = "ENG-Premier League"
DEFAULT_SEASON   = "25-26"          # soccerdata format for 2025-26


def _normalize_league(league: Optional[str]) -> str:
    if not league:
        return DEFAULT_LEAGUE
    return LEAGUE_ALIASES.get(league.lower(), league)


def _flatten_column_name(column: Any) -> str:
    """Flatten pandas MultiIndex columns into stable snake_case strings."""
    if isinstance(column, tuple):
        parts = [str(part).strip().lower().replace(" ", "_") for part in column if str(part).strip()]
        return "_".join(parts)
    return str(column).strip().lower().replace(" ", "_")


def _first_matching_value(row: Dict[str, Any], *candidates: str) -> Any:
    """Return the first value whose key matches any of the candidate substrings."""
    for candidate in candidates:
        if candidate in row:
            return row[candidate]

    lowered = {key.lower(): value for key, value in row.items()}
    for candidate in candidates:
        candidate_lower = candidate.lower()
        for key, value in lowered.items():
            if candidate_lower in key:
                return value
    return None


class FBrefRetriever:
    """
    Async wrapper around soccerdata.FBref for structured player/team stats.

    Usage:
        fb = FBrefRetriever()
        stats = await fb.get_player_season_stats("Salah", "Liverpool")
        print(stats["goals"], stats["assists"], stats["xg"])
    """

    def __init__(
        self,
        cache: Optional[DataCache] = None,
        league: str = DEFAULT_LEAGUE,
        season: str = DEFAULT_SEASON,
    ):
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.default_league = _normalize_league(league)
        self.default_season = season
        self._available: Optional[bool] = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import soccerdata   # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("soccerdata not installed — run: pip install soccerdata")
            self._available = False
        return self._available

    @property
    def is_available(self) -> bool:
        return self._check_available()

    # ── player stats ──────────────────────────────────────────────────────────

    async def get_player_season_stats(
        self,
        player_name: str,
        team_name: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        """
        Fetch a player's season statistics from FBref.

        stat_type options: "standard", "shooting", "passing",
                           "goal_shot_creation", "defense", "possession"

        Returns a dict with numeric stat fields or empty dict on failure.
        """
        lg = _normalize_league(league) or self.default_league
        sv = season or self.default_season
        cache_key = f"{player_name}|{team_name}|{lg}|{sv}|{stat_type}"
        cached = self.cache.get("fbref_player", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return {}

        try:
            result = await asyncio.to_thread(
                self._fetch_player_stats_sync,
                player_name, team_name, lg, sv, stat_type,
            )
            self.cache.set("fbref_player", cache_key, result)
            return result
        except Exception as exc:
            logger.warning("FBref player stats failed [%s]: %s", player_name, exc)
            return {}

    def _fetch_player_stats_sync(
        self,
        player_name: str,
        team_name: Optional[str],
        league: str,
        season: str,
        stat_type: str,
    ) -> Dict[str, Any]:
        import soccerdata as sd
        fbref = sd.FBref(leagues=league, seasons=season)
        df = fbref.read_player_season_stats(stat_type=stat_type)

        if df is None or df.empty:
            return {}

        # FBref DataFrames use MultiIndex — flatten
        df = df.reset_index()

        # Normalize column names
        df.columns = [_flatten_column_name(c) for c in df.columns]

        # Filter by player name (partial, case-insensitive)
        name_col = next(
            (c for c in df.columns if "player" in c or "name" in c), None
        )
        if not name_col:
            return {}

        mask = df[name_col].str.lower().str.contains(
            player_name.lower(), na=False
        )
        if team_name:
            team_col = next(
                (c for c in df.columns if "squad" in c or "team" in c), None
            )
            if team_col:
                mask = mask & df[team_col].str.lower().str.contains(
                    team_name.lower(), na=False
                )

        rows = df[mask]
        if rows.empty:
            return {}

        row = {k: v for k, v in rows.iloc[0].to_dict().items() if v == v and v is not None}
        normalized = {
            "player_name": _first_matching_value(row, "player", "name"),
            "team_name": _first_matching_value(row, "squad", "team"),
            "position": _first_matching_value(row, "pos", "position"),
            "appearances": _first_matching_value(row, "playing_time_mp", "standard_playing_time_mp", "mp"),
            "starts": _first_matching_value(row, "playing_time_starts", "starts"),
            "minutes": _first_matching_value(row, "playing_time_min", "minutes", "min"),
            "goals": _first_matching_value(row, "performance_gls", "standard_performance_gls", "gls", "goals"),
            "assists": _first_matching_value(row, "performance_ast", "standard_performance_ast", "ast", "assists"),
            "xg": _first_matching_value(row, "expected_xg", "xg"),
            "xag": _first_matching_value(row, "expected_xag", "xag"),
            "shots": _first_matching_value(row, "standard_performance_sh", "performance_sh", "shots"),
            "shots_on_target": _first_matching_value(row, "standard_performance_sot", "performance_sot", "shots_on_target"),
            "pass_completion_pct": _first_matching_value(row, "total_cmp%", "passing_total_cmp%", "cmp%", "pass_completion_pct"),
            "progressive_passes": _first_matching_value(row, "passing_total_prgp", "prgp", "progressive_passes"),
            "tackles": _first_matching_value(row, "tackles_tkl", "defense_tackles_tkl", "tkl", "tackles"),
            "interceptions": _first_matching_value(row, "int", "defense_int", "interceptions"),
        }
        return {**row, **{k: v for k, v in normalized.items() if v is not None}}

    # ── team stats ────────────────────────────────────────────────────────────

    async def get_team_season_stats(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        """
        Fetch team-level aggregated season stats from FBref.

        stat_type options: "standard", "keeper", "shooting", "passing",
                           "passing_types", "goal_shot_creation", "defense",
                           "possession", "playing_time", "misc"
        """
        lg = _normalize_league(league) or self.default_league
        sv = season or self.default_season
        cache_key = f"{team_name}|{lg}|{sv}|{stat_type}"
        cached = self.cache.get("fbref_team", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return {}

        try:
            result = await asyncio.to_thread(
                self._fetch_team_stats_sync,
                team_name, lg, sv, stat_type,
            )
            self.cache.set("fbref_team", cache_key, result)
            return result
        except Exception as exc:
            logger.warning("FBref team stats failed [%s]: %s", team_name, exc)
            return {}

    def _fetch_team_stats_sync(
        self,
        team_name: str,
        league: str,
        season: str,
        stat_type: str,
    ) -> Dict[str, Any]:
        import soccerdata as sd
        fbref = sd.FBref(leagues=league, seasons=season)
        df = fbref.read_team_season_stats(stat_type=stat_type)

        if df is None or df.empty:
            return {}

        df = df.reset_index()
        df.columns = [_flatten_column_name(c) for c in df.columns]

        team_col = next(
            (c for c in df.columns if "squad" in c or "team" in c), None
        )
        if not team_col:
            return {}

        mask = df[team_col].str.lower().str.contains(
            team_name.lower(), na=False
        )
        rows = df[mask]
        if rows.empty:
            return {}

        row = {k: v for k, v in rows.iloc[0].to_dict().items() if v == v and v is not None}
        normalized = {
            "team_name": _first_matching_value(row, "squad", "team"),
            "matches_played": _first_matching_value(row, "playing_time_mp", "standard_playing_time_mp", "mp"),
            "goals": _first_matching_value(row, "performance_gls", "standard_performance_gls", "gls", "goals"),
            "goals_against": _first_matching_value(row, "performance_ga", "ga", "goals_against"),
            "xg": _first_matching_value(row, "expected_xg", "xg"),
            "xga": _first_matching_value(row, "expected_xga", "xga"),
            "possession_pct": _first_matching_value(row, "performance_poss", "poss", "possession"),
            "pass_completion_pct": _first_matching_value(row, "total_cmp%", "passing_total_cmp%", "cmp%", "pass_completion_pct"),
            "tackles": _first_matching_value(row, "tackles_tkl", "defense_tackles_tkl", "tkl", "tackles"),
            "interceptions": _first_matching_value(row, "int", "defense_int", "interceptions"),
        }
        return {**row, **{k: v for k, v in normalized.items() if v is not None}}

    async def get_tactical_profile(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a tactical profile from possession + defense + passing stats.
        Called by SportsSpecificRetriever to replace mock tactics.
        """
        lg = _normalize_league(league) or self.default_league
        sv = season or self.default_season

        possession, defense, passing = await asyncio.gather(
            self.get_team_season_stats(team_name, lg, sv, "possession"),
            self.get_team_season_stats(team_name, lg, sv, "defense"),
            self.get_team_season_stats(team_name, lg, sv, "passing"),
        )

        if not any([possession, defense, passing]):
            return {}

        return {
            "team": team_name,
            "possession_stats": possession,
            "defense_stats": defense,
            "passing_stats": passing,
            "data_source": "fbref",
        }

    # ── team match log ────────────────────────────────────────────────────────

    async def get_team_match_log(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        last_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the last N match results for a team.
        Returns list of {date, opponent, venue, result, goals_for, goals_against}.
        """
        lg = _normalize_league(league) or self.default_league
        sv = season or self.default_season
        cache_key = f"{team_name}|{lg}|{sv}|matchlog"
        cached = self.cache.get("fbref_matchlog", cache_key)
        if cached:
            return cached[:last_n]

        if not self._check_available():
            return []

        try:
            results = await asyncio.to_thread(
                self._fetch_match_log_sync, team_name, lg, sv
            )
            self.cache.set("fbref_matchlog", cache_key, results)
            return results[:last_n]
        except Exception as exc:
            logger.warning("FBref match log failed [%s]: %s", team_name, exc)
            return []

    def _fetch_match_log_sync(
        self, team_name: str, league: str, season: str
    ) -> List[Dict[str, Any]]:
        import soccerdata as sd
        fbref = sd.FBref(leagues=league, seasons=season)
        df = fbref.read_team_match_stats(stat_type="schedule", team=team_name)

        if df is None or df.empty:
            return []

        df = df.reset_index()
        df.columns = [_flatten_column_name(c) for c in df.columns]

        matches = []
        for _, row in df.iterrows():
            result_val = str(row.get("result", "")).upper()
            if result_val not in ("W", "D", "L"):
                continue  # skip unplayed fixtures
            matches.append({
                "date": str(row.get("date", ""))[:10],
                "opponent": str(row.get("opponent", "")),
                "venue": str(row.get("venue", "")),
                "result": result_val,
                "goals_for": row.get("gf") or row.get("goals_for"),
                "goals_against": row.get("ga") or row.get("goals_against"),
                "xg": row.get("xg"),
                "xga": row.get("xga"),
            })

        # Return in reverse chronological order (most recent first)
        matches.sort(key=lambda x: x["date"], reverse=True)
        return matches

    # ── H2H from schedule ────────────────────────────────────────────────────

    async def get_head_to_head_matches(
        self,
        team1: str,
        team2: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find H2H fixtures from the season schedule.
        Returns list of played matches between the two teams.
        """
        lg = _normalize_league(league) or self.default_league
        sv = season or self.default_season
        cache_key = f"{team1}|{team2}|{lg}|{sv}"
        cached = self.cache.get("fbref_h2h", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return []

        try:
            matches = await asyncio.to_thread(
                self._fetch_h2h_sync, team1, team2, lg, sv
            )
            self.cache.set("fbref_h2h", cache_key, matches)
            return matches
        except Exception as exc:
            logger.warning("FBref H2H failed [%s vs %s]: %s", team1, team2, exc)
            return []

    def _fetch_h2h_sync(
        self, team1: str, team2: str, league: str, season: str
    ) -> List[Dict[str, Any]]:
        import soccerdata as sd
        fbref = sd.FBref(leagues=league, seasons=season)
        df = fbref.read_schedule()

        if df is None or df.empty:
            return []

        df = df.reset_index()
        df.columns = [_flatten_column_name(c) for c in df.columns]

        home_col = next((c for c in df.columns if "home" in c.lower()), None)
        away_col = next((c for c in df.columns if "away" in c.lower()), None)
        if not (home_col and away_col):
            return []

        t1, t2 = team1.lower(), team2.lower()
        mask = (
            (df[home_col].str.lower().str.contains(t1, na=False) &
             df[away_col].str.lower().str.contains(t2, na=False))
            |
            (df[home_col].str.lower().str.contains(t2, na=False) &
             df[away_col].str.lower().str.contains(t1, na=False))
        )
        sub = df[mask]

        matches = []
        for _, row in sub.iterrows():
            score_h = row.get("score_home") or row.get("xg_home")
            score_a = row.get("score_away") or row.get("xg_away")
            matches.append({
                "date": str(row.get("date", ""))[:10],
                "home": str(row.get(home_col, "")),
                "away": str(row.get(away_col, "")),
                "score": f"{score_h}-{score_a}" if score_h is not None else "TBD",
            })
        return matches

    async def close(self) -> None:
        """Compatibility no-op."""
        return None
