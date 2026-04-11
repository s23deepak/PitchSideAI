"""
StatsBomb Retriever — Free open event data via statsbombpy.

Provides the same 5-method interface as FBrefRetriever but backed by
StatsBomb's free open data (historical competitions only). Event-level data
is aggregated into the same per-player and per-team stat dicts that agents
already consume.

Free data covers: La Liga (2004–2021), Champions League, FIFA World Cup,
Euro, Bundesliga 2023/24, Premier League 2003/04 & 2015/16, and more.
See https://github.com/statsbomb/open-data for the full list.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

# ── League / Competition mapping ──────────────────────────────────────────────

# Map codebase league names → StatsBomb (competition_id, competition_name)
_LEAGUE_TO_SB: Dict[str, Tuple[int, str]] = {
    "ENG-Premier League":  (2,  "Premier League"),
    "ESP-La Liga":         (11, "La Liga"),
    "GER-Bundesliga":      (9,  "1. Bundesliga"),
    "ITA-Serie A":         (12, "Serie A"),
    "FRA-Ligue 1":         (7,  "Ligue 1"),
}

_LEAGUE_ALIASES: Dict[str, str] = {
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


def _normalize_league(league: Optional[str]) -> str:
    if not league:
        return "ENG-Premier League"
    return _LEAGUE_ALIASES.get(league.lower(), league)


class StatsBombRetriever:
    """
    Async retriever backed by StatsBomb's free open data.

    Mirrors the FBrefRetriever interface so it can be used as a drop-in
    replacement. Event-level data is aggregated into the same stat dict
    schema that agents expect.
    """

    def __init__(self, cache: Optional[DataCache] = None):
        self.cache = cache or DataCache(ttl_seconds=14400)  # 4-hour TTL
        self._available: Optional[bool] = None
        self._competitions = None  # lazy-loaded DataFrame

    # ── Availability ──────────────────────────────────────────────────────────

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from statsbombpy import sb  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("statsbombpy not installed — run: pip install statsbombpy")
            self._available = False
        return self._available

    @property
    def is_available(self) -> bool:
        return self._check_available()

    # ── Competition / season resolution ───────────────────────────────────────

    def _load_competitions_sync(self):
        from statsbombpy import sb
        return sb.competitions()

    async def _get_competitions(self):
        if self._competitions is None:
            self._competitions = await asyncio.to_thread(self._load_competitions_sync)
        return self._competitions

    async def _resolve_season(
        self, league: str, season: Optional[str]
    ) -> Optional[Tuple[int, int]]:
        """
        Resolve a league + season string to StatsBomb (competition_id, season_id).

        Returns None (no data) when:
        - The league isn't in the free catalog
        - A specific season is requested but NOT in the free data (avoids returning
          stale data from a different season, e.g. 2020/21 stats for a 2025/26 query)

        Only falls back to the most recent available season when season=None
        (i.e. the caller explicitly wants whatever is available).
        """
        sb_entry = _LEAGUE_TO_SB.get(league)
        if not sb_entry:
            return None

        comp_id, _ = sb_entry
        comps = await self._get_competitions()

        if comps is None or comps.empty:
            return None

        league_seasons = comps[comps["competition_id"] == comp_id].copy()
        if league_seasons.empty:
            return None

        if season:
            # Exact-match only — do NOT fall back to a different season.
            # Returning 2020/21 stats when asked for 2025/26 is worse than no data.
            target = _season_code_to_full(season)
            match = league_seasons[league_seasons["season_name"] == target]
            if match.empty:
                return None
            return (comp_id, int(match.iloc[0]["season_id"]))

        # No season specified → caller wants whatever is available; use most recent
        league_seasons = league_seasons.sort_values("season_name", ascending=False)
        row = league_seasons.iloc[0]
        return (comp_id, int(row["season_id"]))

    # ── Player season stats ───────────────────────────────────────────────────

    async def get_player_season_stats(
        self,
        player_name: str,
        team_name: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        lg = _normalize_league(league)
        cache_key = f"sb_player|{player_name}|{team_name}|{lg}|{season}"
        cached = self.cache.get("statsbomb_player", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return {}

        try:
            resolved = await self._resolve_season(lg, season)
            if not resolved:
                return {}
            result = await asyncio.to_thread(
                self._aggregate_player_stats_sync, player_name, team_name, resolved
            )
            if result:
                self.cache.set("statsbomb_player", cache_key, result)
            return result
        except Exception as exc:
            logger.warning("StatsBomb player stats failed [%s]: %s", player_name, exc)
            return {}

    def _aggregate_player_stats_sync(
        self,
        player_name: str,
        team_name: Optional[str],
        resolved: Tuple[int, int],
    ) -> Dict[str, Any]:
        """Aggregate event-level data into per-player season stats."""
        from statsbombpy import sb

        comp_id, season_id = resolved

        # Get all matches for this competition/season
        matches = sb.matches(competition_id=comp_id, season_id=season_id)
        if matches is None or matches.empty:
            return {}

        # Filter matches involving the team (if specified)
        if team_name:
            t_lower = team_name.lower()
            matches = matches[
                matches["home_team"].str.lower().str.contains(t_lower, na=False)
                | matches["away_team"].str.lower().str.contains(t_lower, na=False)
            ]
            if matches.empty:
                return {}

        # Aggregate across matches (process up to 20 matches for speed)
        match_ids = matches["match_id"].tolist()[:20]
        p_lower = player_name.lower()

        stats = {
            "goals": 0, "assists": 0, "xg": 0.0, "xag": 0.0,
            "shots": 0, "shots_on_target": 0, "tackles": 0, "interceptions": 0,
            "passes_completed": 0, "passes_attempted": 0,
            "progressive_passes": 0, "appearances": 0, "minutes": 0,
        }
        found_player = False
        actual_team = None
        actual_season = None

        for mid in match_ids:
            try:
                events = sb.events(match_id=mid)
            except Exception:
                continue

            if events is None or events.empty:
                continue

            # Get actual season name for metadata
            if actual_season is None:
                m_row = matches[matches["match_id"] == mid]
                if not m_row.empty:
                    actual_season = str(m_row.iloc[0].get("season", ""))

            # Find player name in events (fuzzy match)
            player_col = "player" if "player" in events.columns else None
            if not player_col:
                continue

            player_events = events[
                events[player_col].str.lower().str.contains(p_lower, na=False)
            ]
            if player_events.empty:
                continue

            found_player = True
            stats["appearances"] += 1

            if actual_team is None and "team" in events.columns:
                team_rows = player_events["team"].dropna()
                if not team_rows.empty:
                    actual_team = str(team_rows.iloc[0])

            # Minutes: estimate from events (duration if available)
            if "minute" in player_events.columns:
                max_min = player_events["minute"].max()
                if max_min and max_min == max_min:  # not NaN
                    stats["minutes"] += int(max_min)

            # Goals
            shots = player_events[player_events["type"] == "Shot"] if "type" in player_events.columns else player_events.iloc[0:0]
            if not shots.empty:
                stats["shots"] += len(shots)
                if "shot_outcome" in shots.columns:
                    stats["goals"] += len(shots[shots["shot_outcome"] == "Goal"])
                    stats["shots_on_target"] += len(shots[
                        shots["shot_outcome"].isin(["Goal", "Saved", "Saved to Post"])
                    ])
                if "shot_statsbomb_xg" in shots.columns:
                    xg_vals = shots["shot_statsbomb_xg"].dropna()
                    stats["xg"] += float(xg_vals.sum())

            # Assists (via pass_goal_assist)
            passes = player_events[player_events["type"] == "Pass"] if "type" in player_events.columns else player_events.iloc[0:0]
            if not passes.empty:
                stats["passes_attempted"] += len(passes)
                if "pass_outcome" in passes.columns:
                    stats["passes_completed"] += len(passes[passes["pass_outcome"].isna()])
                else:
                    stats["passes_completed"] += len(passes)
                if "pass_goal_assist" in passes.columns:
                    stats["assists"] += int(passes["pass_goal_assist"].fillna(False).sum())

            # Tackles & interceptions
            if "type" in player_events.columns:
                stats["tackles"] += len(player_events[player_events["type"] == "Duel"])
                stats["interceptions"] += len(player_events[player_events["type"] == "Interception"])

        if not found_player:
            return {}

        # Compute derived stats
        pass_pct = (
            round(100 * stats["passes_completed"] / stats["passes_attempted"], 1)
            if stats["passes_attempted"] > 0 else None
        )

        result = {
            "player_name": player_name,
            "team_name": actual_team or team_name,
            "appearances": stats["appearances"],
            "minutes": stats["minutes"],
            "goals": stats["goals"],
            "assists": stats["assists"],
            "xg": round(stats["xg"], 2),
            "shots": stats["shots"],
            "shots_on_target": stats["shots_on_target"],
            "pass_completion_pct": pass_pct,
            "tackles": stats["tackles"],
            "interceptions": stats["interceptions"],
            "data_source": "statsbomb",
        }
        if actual_season:
            result["season_note"] = f"Data from {actual_season} (StatsBomb open data)"

        return result

    # ── Team season stats ─────────────────────────────────────────────────────

    async def get_team_season_stats(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        lg = _normalize_league(league)
        cache_key = f"sb_team|{team_name}|{lg}|{season}|{stat_type}"
        cached = self.cache.get("statsbomb_team", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return {}

        try:
            resolved = await self._resolve_season(lg, season)
            if not resolved:
                return {}
            result = await asyncio.to_thread(
                self._aggregate_team_stats_sync, team_name, resolved
            )
            if result:
                self.cache.set("statsbomb_team", cache_key, result)
            return result
        except Exception as exc:
            logger.warning("StatsBomb team stats failed [%s]: %s", team_name, exc)
            return {}

    def _aggregate_team_stats_sync(
        self,
        team_name: str,
        resolved: Tuple[int, int],
    ) -> Dict[str, Any]:
        from statsbombpy import sb

        comp_id, season_id = resolved
        matches = sb.matches(competition_id=comp_id, season_id=season_id)
        if matches is None or matches.empty:
            return {}

        t_lower = team_name.lower()
        team_matches = matches[
            matches["home_team"].str.lower().str.contains(t_lower, na=False)
            | matches["away_team"].str.lower().str.contains(t_lower, na=False)
        ]
        if team_matches.empty:
            return {}

        # Aggregate from match results
        goals_for = 0
        goals_against = 0
        matches_played = len(team_matches)

        for _, row in team_matches.iterrows():
            is_home = t_lower in str(row.get("home_team", "")).lower()
            h_score = row.get("home_score", 0) or 0
            a_score = row.get("away_score", 0) or 0
            if is_home:
                goals_for += h_score
                goals_against += a_score
            else:
                goals_for += a_score
                goals_against += h_score

        result = {
            "team_name": team_name,
            "matches_played": matches_played,
            "goals": goals_for,
            "goals_against": goals_against,
            "data_source": "statsbomb",
        }
        return result

    # ── Tactical profile ──────────────────────────────────────────────────────

    async def get_tactical_profile(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> Dict[str, Any]:
        stats = await self.get_team_season_stats(team_name, league, season)
        if not stats:
            return {}
        return {
            "team": team_name,
            "possession_stats": stats,
            "defense_stats": stats,
            "passing_stats": stats,
            "data_source": "statsbomb",
        }

    # ── Team match log ────────────────────────────────────────────────────────

    async def get_team_match_log(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        last_n: int = 5,
    ) -> List[Dict[str, Any]]:
        lg = _normalize_league(league)
        cache_key = f"sb_matchlog|{team_name}|{lg}|{season}"
        cached = self.cache.get("statsbomb_matchlog", cache_key)
        if cached:
            return cached[:last_n]

        if not self._check_available():
            return []

        try:
            resolved = await self._resolve_season(lg, season)
            if not resolved:
                return []
            result = await asyncio.to_thread(
                self._fetch_match_log_sync, team_name, resolved
            )
            if result:
                self.cache.set("statsbomb_matchlog", cache_key, result)
            return result[:last_n]
        except Exception as exc:
            logger.warning("StatsBomb match log failed [%s]: %s", team_name, exc)
            return []

    def _fetch_match_log_sync(
        self, team_name: str, resolved: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        from statsbombpy import sb

        comp_id, season_id = resolved
        matches = sb.matches(competition_id=comp_id, season_id=season_id)
        if matches is None or matches.empty:
            return []

        t_lower = team_name.lower()
        team_matches = matches[
            matches["home_team"].str.lower().str.contains(t_lower, na=False)
            | matches["away_team"].str.lower().str.contains(t_lower, na=False)
        ]

        results = []
        for _, row in team_matches.iterrows():
            is_home = t_lower in str(row.get("home_team", "")).lower()
            h_score = row.get("home_score", 0) or 0
            a_score = row.get("away_score", 0) or 0
            gf = h_score if is_home else a_score
            ga = a_score if is_home else h_score

            if gf > ga:
                result_str = "W"
            elif gf < ga:
                result_str = "L"
            else:
                result_str = "D"

            results.append({
                "date": str(row.get("match_date", ""))[:10],
                "opponent": str(row.get("away_team" if is_home else "home_team", "")),
                "venue": "Home" if is_home else "Away",
                "result": result_str,
                "goals_for": gf,
                "goals_against": ga,
                "data_source": "statsbomb",
            })

        results.sort(key=lambda x: x["date"], reverse=True)
        return results

    # ── H2H ───────────────────────────────────────────────────────────────────

    async def get_head_to_head_matches(
        self,
        team1: str,
        team2: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        lg = _normalize_league(league)
        cache_key = f"sb_h2h|{team1}|{team2}|{lg}|{season}"
        cached = self.cache.get("statsbomb_h2h", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return []

        try:
            resolved = await self._resolve_season(lg, season)
            if not resolved:
                return []
            result = await asyncio.to_thread(
                self._fetch_h2h_sync, team1, team2, resolved
            )
            if result:
                self.cache.set("statsbomb_h2h", cache_key, result)
            return result
        except Exception as exc:
            logger.warning("StatsBomb H2H failed [%s vs %s]: %s", team1, team2, exc)
            return []

    def _fetch_h2h_sync(
        self, team1: str, team2: str, resolved: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        from statsbombpy import sb

        comp_id, season_id = resolved
        matches = sb.matches(competition_id=comp_id, season_id=season_id)
        if matches is None or matches.empty:
            return []

        t1, t2 = team1.lower(), team2.lower()
        h2h = matches[
            (matches["home_team"].str.lower().str.contains(t1, na=False)
             & matches["away_team"].str.lower().str.contains(t2, na=False))
            | (matches["home_team"].str.lower().str.contains(t2, na=False)
               & matches["away_team"].str.lower().str.contains(t1, na=False))
        ]

        results = []
        for _, row in h2h.iterrows():
            h_score = row.get("home_score", "")
            a_score = row.get("away_score", "")
            results.append({
                "date": str(row.get("match_date", ""))[:10],
                "home": str(row.get("home_team", "")),
                "away": str(row.get("away_team", "")),
                "score": f"{h_score}-{a_score}",
                "data_source": "statsbomb",
            })
        return results

    async def close(self) -> None:
        """Compatibility no-op."""
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _season_code_to_full(code: str) -> str:
    """Convert "20-21" → "2020/2021" or "23-24" → "2023/2024"."""
    parts = code.split("-")
    if len(parts) != 2:
        return code
    a, b = parts
    try:
        ya = int(a)
        yb = int(b)
    except ValueError:
        return code

    century_a = 2000 if ya < 50 else 1900
    century_b = 2000 if yb < 50 else 1900
    return f"{century_a + ya}/{century_b + yb}"
