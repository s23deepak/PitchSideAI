"""
Bright Data Retriever — fetches FBref pages via Bright Data Web Unlocker proxy.

Bright Data handles JavaScript rendering, anti-bot countermeasures, and residential
proxy rotation. We construct well-known FBref URLs and parse the HTML tables with
pandas.read_html — same approach as FBrefRetriever but bypassing 403 blocks.

Required env vars:
  BD_CUSTOMER_ID    e.g. "hl_abc123"
  BD_ZONE_NAME      e.g. "web_unlocker1"
  BD_ZONE_PASSWORD  zone password from Bright Data dashboard
"""

import asyncio
import logging
import os
import re
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import requests

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

_BD_HOST = "brd.superproxy.io:33335"

# FBref competition IDs for known leagues
_LEAGUE_TO_FBREF: Dict[str, Tuple[int, str]] = {
    "ENG-Premier League": (9,  "Premier-League"),
    "ESP-La Liga":        (12, "La-Liga"),
    "GER-Bundesliga":     (20, "Bundesliga"),
    "ITA-Serie A":        (11, "Serie-A"),
    "FRA-Ligue 1":        (13, "Ligue-1"),
}

_LEAGUE_ALIASES: Dict[str, str] = {
    "premier league":     "ENG-Premier League",
    "epl":                "ENG-Premier League",
    "eng-premier league": "ENG-Premier League",
    "la liga":            "ESP-La Liga",
    "esp-la liga":        "ESP-La Liga",
    "bundesliga":         "GER-Bundesliga",
    "ger-bundesliga":     "GER-Bundesliga",
    "serie a":            "ITA-Serie A",
    "ita-serie a":        "ITA-Serie A",
    "ligue 1":            "FRA-Ligue 1",
    "fra-ligue 1":        "FRA-Ligue 1",
}


def _normalize_league(league: Optional[str]) -> str:
    if not league:
        return "ENG-Premier League"
    return _LEAGUE_ALIASES.get(league.lower(), league)


def _season_to_full(code: str) -> str:
    """Convert "24-25" → "2024-2025" for FBref URL paths."""
    parts = code.split("-")
    if len(parts) != 2:
        return code
    try:
        a, b = int(parts[0]), int(parts[1])
        ca = 2000 if a < 50 else 1900
        cb = 2000 if b < 50 else 1900
        return f"{ca + a}-{cb + b}"
    except ValueError:
        return code


def _flatten_col(column: Any) -> str:
    """Flatten pandas MultiIndex columns into snake_case strings."""
    if isinstance(column, tuple):
        parts = [str(p).strip().lower().replace(" ", "_") for p in column if str(p).strip()]
        return "_".join(parts)
    return str(column).strip().lower().replace(" ", "_")


def _first_val(row: Dict[str, Any], *keys: str) -> Optional[float]:
    """Return first numeric match among candidate column name substrings."""
    for key in keys:
        for col, val in row.items():
            if key in col:
                try:
                    return float(str(val).replace(",", ""))
                except (ValueError, TypeError):
                    pass
    return None


class BrightDataRetriever:
    """
    Retriever that proxies FBref requests through Bright Data Web Unlocker.

    Mirrors the FBrefRetriever interface (same 5 public async methods).
    Falls back gracefully when credentials are absent.
    """

    def __init__(self, cache: Optional[DataCache] = None):
        self.cache = cache or DataCache(ttl_seconds=3600)
        customer = os.environ.get("BD_CUSTOMER_ID", "")
        zone     = os.environ.get("BD_ZONE_NAME", "")
        password = os.environ.get("BD_ZONE_PASSWORD", "")
        self._proxy_url = (
            f"http://{customer}-zone-{zone}:{password}@{_BD_HOST}"
            if customer and zone and password else ""
        )
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = bool(self._proxy_url)
        if not self._available:
            logger.warning(
                "BD_CUSTOMER_ID / BD_ZONE_NAME / BD_ZONE_PASSWORD not set — "
                "BrightDataRetriever disabled"
            )
        return self._available

    # ── Internal HTTP helpers ─────────────────────────────────────────────────

    def _session(self) -> requests.Session:
        s = requests.Session()
        s.proxies = {"http": self._proxy_url, "https": self._proxy_url}
        s.verify = False  # Bright Data uses its own CA; disable verification
        s.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
        return s

    def _fetch_html_sync(self, url: str) -> str:
        try:
            resp = self._session().get(url, timeout=45)
            if resp.ok:
                return resp.text
            logger.warning("BrightData fetch %s → %s", url, resp.status_code)
        except Exception as exc:
            logger.warning("BrightData fetch error [%s]: %s", url, exc)
        return ""

    async def _fetch_html(self, url: str) -> str:
        return await asyncio.to_thread(self._fetch_html_sync, url)

    # ── Public interface (mirrors FBrefRetriever) ─────────────────────────────

    async def get_player_season_stats(
        self,
        player_name: str,
        team_name: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        if not self.is_available:
            return {}

        norm_league = _normalize_league(league)
        comp = _LEAGUE_TO_FBREF.get(norm_league)
        if not comp:
            return {}
        comp_id, league_slug = comp

        season_full = _season_to_full(season) if season else "2024-2025"
        cache_key = f"bd_player|{player_name}|{norm_league}|{season_full}"
        cached = self.cache.get("brightdata_player", cache_key)
        if cached:
            return cached

        url = (
            f"https://fbref.com/en/comps/{comp_id}/{season_full}/stats/"
            f"{season_full}-{league_slug}-Stats"
        )

        try:
            html = await self._fetch_html(url)
            if not html:
                return {}
            result = await asyncio.to_thread(
                _parse_player_from_html, player_name, html
            )
            if result:
                result["data_source"] = "brightdata"
                result["source_url"] = url
                self.cache.set("brightdata_player", cache_key, result)
                return result
        except Exception as exc:
            logger.warning("BrightData player stats failed [%s]: %s", player_name, exc)

        return {}

    async def get_team_season_stats(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        if not self.is_available:
            return {}

        norm_league = _normalize_league(league)
        comp = _LEAGUE_TO_FBREF.get(norm_league)
        if not comp:
            return {}
        comp_id, league_slug = comp

        season_full = _season_to_full(season) if season else "2024-2025"
        cache_key = f"bd_team|{team_name}|{norm_league}|{season_full}"
        cached = self.cache.get("brightdata_team", cache_key)
        if cached:
            return cached

        url = (
            f"https://fbref.com/en/comps/{comp_id}/{season_full}/stats/"
            f"{season_full}-{league_slug}-Stats"
        )

        try:
            html = await self._fetch_html(url)
            if not html:
                return {}
            result = await asyncio.to_thread(
                _parse_team_from_html, team_name, html
            )
            if result:
                result["data_source"] = "brightdata"
                result["source_url"] = url
                self.cache.set("brightdata_team", cache_key, result)
                return result
        except Exception as exc:
            logger.warning("BrightData team stats failed [%s]: %s", team_name, exc)

        return {}

    async def get_tactical_profile(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Tactical data requires additional FBref possession/press tables;
        # delegate to Firecrawl for now.
        return {}

    async def get_team_match_log(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        last_n: int = 5,
    ) -> List[Dict[str, Any]]:
        if not self.is_available:
            return []

        norm_league = _normalize_league(league)
        comp = _LEAGUE_TO_FBREF.get(norm_league)
        if not comp:
            return []
        comp_id, league_slug = comp

        season_full = _season_to_full(season) if season else "2024-2025"
        cache_key = f"bd_matchlog|{team_name}|{norm_league}|{season_full}"
        cached = self.cache.get("brightdata_matchlog", cache_key)
        if cached:
            return cached[:last_n]

        # FBref scores/fixtures page for the league (no team ID needed)
        url = (
            f"https://fbref.com/en/comps/{comp_id}/{season_full}/schedule/"
            f"{season_full}-{league_slug}-Scores-and-Fixtures"
        )

        try:
            html = await self._fetch_html(url)
            if not html:
                return []
            matches = await asyncio.to_thread(
                _parse_match_log_from_html, team_name, html
            )
            if matches:
                self.cache.set("brightdata_matchlog", cache_key, matches)
                return matches[:last_n]
        except Exception as exc:
            logger.warning("BrightData match log failed [%s]: %s", team_name, exc)

        return []

    async def get_head_to_head_matches(
        self,
        team1: str,
        team2: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.is_available:
            return []

        norm_league = _normalize_league(league)
        comp = _LEAGUE_TO_FBREF.get(norm_league)
        if not comp:
            return []
        comp_id, league_slug = comp

        season_full = _season_to_full(season) if season else "2024-2025"
        cache_key = f"bd_h2h|{team1}|{team2}|{norm_league}|{season_full}"
        cached = self.cache.get("brightdata_h2h", cache_key)
        if cached:
            return cached

        url = (
            f"https://fbref.com/en/comps/{comp_id}/{season_full}/schedule/"
            f"{season_full}-{league_slug}-Scores-and-Fixtures"
        )

        try:
            html = await self._fetch_html(url)
            if not html:
                return []
            matches = await asyncio.to_thread(
                _parse_h2h_from_html, team1, team2, html
            )
            if matches:
                self.cache.set("brightdata_h2h", cache_key, matches)
                return matches
        except Exception as exc:
            logger.warning("BrightData H2H failed [%s vs %s]: %s", team1, team2, exc)

        return []

    async def close(self) -> None:
        return None


# ── HTML parsing helpers ───────────────────────────────────────────────────────

def _read_tables(html: str):
    """Parse all HTML tables via pandas, returns list of DataFrames."""
    try:
        import pandas as pd
        tables = pd.read_html(StringIO(html))
        return tables
    except Exception:
        return []


def _parse_player_from_html(player_name: str, html: str) -> Optional[Dict[str, Any]]:
    """Find player row across all tables on the FBref stats page."""
    import pandas as pd
    tables = _read_tables(html)
    p_lower = player_name.lower()

    for df in tables:
        # Flatten MultiIndex columns
        df.columns = [_flatten_col(c) for c in df.columns]
        # Find name column
        name_col = next((c for c in df.columns if "player" in c or "name" in c), None)
        if name_col is None:
            continue
        df[name_col] = df[name_col].astype(str).str.lower()
        match = df[df[name_col].str.contains(p_lower, na=False)]
        if match.empty:
            continue

        row = match.iloc[0].to_dict()
        stats: Dict[str, Any] = {}

        def get(*keys: str) -> Optional[float]:
            return _first_val(row, *keys)

        stats["goals"]              = get("_gls", "goals")
        stats["assists"]            = get("_ast", "assists")
        stats["appearances"]        = get("_mp", "matches")
        stats["minutes"]            = get("_min", "minutes")
        stats["xg"]                 = get("_xg", "expected_g")
        stats["xag"]                = get("_xag",)
        stats["shots"]              = get("_sh", "shots")
        stats["shots_on_target"]    = get("_sot",)
        stats["pass_completion_pct"]= get("cmp%", "pass_cmp")
        stats["progressive_passes"] = get("_prgp", "prog_pass")
        stats["tackles"]            = get("_tkl", "tackles")
        stats["interceptions"]      = get("_int", "interceptions")

        stats = {k: v for k, v in stats.items() if v is not None}
        if not stats:
            continue

        # Player / team name from row
        stats["player_name"] = player_name
        squad_col = next((c for c in row if "squad" in c or "team" in c or "club" in c), None)
        if squad_col:
            stats["team_name"] = str(row[squad_col])

        return stats

    return None


def _parse_team_from_html(team_name: str, html: str) -> Optional[Dict[str, Any]]:
    """Extract team-level aggregated stats from squad summary tables."""
    import pandas as pd
    tables = _read_tables(html)
    t_lower = team_name.lower()

    for df in tables:
        df.columns = [_flatten_col(c) for c in df.columns]
        squad_col = next((c for c in df.columns if "squad" in c or "team" in c), None)
        if squad_col is None:
            continue
        df[squad_col] = df[squad_col].astype(str).str.lower()
        match = df[df[squad_col].str.contains(t_lower, na=False)]
        if match.empty:
            continue

        row = match.iloc[0].to_dict()

        def get(*keys: str) -> Optional[float]:
            return _first_val(row, *keys)

        stats: Dict[str, Any] = {
            "goals":        get("_gls", "goals"),
            "xg":           get("_xg",),
            "possession":   get("poss",),
            "appearances":  get("_mp",),
            "team_name":    team_name,
            "data_source":  "brightdata",
        }
        return {k: v for k, v in stats.items() if v is not None}

    return None


def _parse_match_log_from_html(
    team_name: str, html: str
) -> List[Dict[str, Any]]:
    """Extract match results from a league schedule/fixtures table."""
    import pandas as pd
    tables = _read_tables(html)
    t_lower = team_name.lower()
    matches: List[Dict[str, Any]] = []

    for df in tables:
        df.columns = [_flatten_col(c) for c in df.columns]

        # Need date, home/away team columns, and a score/result
        date_col = next((c for c in df.columns if c == "date"), None)
        if date_col is None:
            continue

        home_col  = next((c for c in df.columns if "home" in c), None)
        away_col  = next((c for c in df.columns if "away" in c), None)
        score_col = next((c for c in df.columns if "score" in c or c in ("xg", "notes")), None)

        if not (home_col and away_col):
            continue

        df = df.dropna(subset=[date_col])
        df[home_col] = df[home_col].astype(str).str.lower()
        df[away_col] = df[away_col].astype(str).str.lower()

        team_rows = df[
            df[home_col].str.contains(t_lower, na=False) |
            df[away_col].str.contains(t_lower, na=False)
        ]

        for _, row in team_rows.iterrows():
            score_raw = str(row.get(score_col, "")) if score_col else ""
            score_match = re.search(r"(\d+)[–\-](\d+)", score_raw)
            if not score_match:
                continue

            home_team = str(row[home_col])
            away_team = str(row[away_col])
            home_score = int(score_match.group(1))
            away_score = int(score_match.group(2))
            is_home = t_lower in home_team

            gf = home_score if is_home else away_score
            ga = away_score if is_home else home_score
            result = "W" if gf > ga else ("D" if gf == ga else "L")
            opponent = away_team if is_home else home_team

            matches.append({
                "date":          str(row[date_col])[:10],
                "opponent":      opponent,
                "venue":         "Home" if is_home else "Away",
                "result":        result,
                "goals_for":     gf,
                "goals_against": ga,
                "data_source":   "brightdata",
            })

    matches.sort(key=lambda x: x["date"], reverse=True)
    return matches


def _parse_h2h_from_html(
    team1: str, team2: str, html: str
) -> List[Dict[str, Any]]:
    """Filter schedule table to rows where both teams appear."""
    import pandas as pd
    tables = _read_tables(html)
    t1, t2 = team1.lower(), team2.lower()
    matches: List[Dict[str, Any]] = []

    for df in tables:
        df.columns = [_flatten_col(c) for c in df.columns]
        date_col  = next((c for c in df.columns if c == "date"), None)
        home_col  = next((c for c in df.columns if "home" in c), None)
        away_col  = next((c for c in df.columns if "away" in c), None)
        score_col = next((c for c in df.columns if "score" in c), None)

        if not (date_col and home_col and away_col):
            continue

        df = df.dropna(subset=[date_col])
        df[home_col] = df[home_col].astype(str).str.lower()
        df[away_col] = df[away_col].astype(str).str.lower()

        mask = (
            (df[home_col].str.contains(t1, na=False) & df[away_col].str.contains(t2, na=False)) |
            (df[home_col].str.contains(t2, na=False) & df[away_col].str.contains(t1, na=False))
        )
        for _, row in df[mask].iterrows():
            matches.append({
                "date":        str(row[date_col])[:10],
                "home":        str(row[home_col]),
                "away":        str(row[away_col]),
                "score":       str(row.get(score_col, "")) if score_col else "",
                "data_source": "brightdata",
            })

    return matches
