"""
Firecrawl Retriever — scrapes current-season player and team data.

Uses Firecrawl's search + scrape API to pull clean page content from
sports data sites (FBref, Sofascore, BBC Sport) and extracts structured
stats from the returned markdown. Firecrawl handles JavaScript rendering,
anti-bot countermeasures, and proxy rotation automatically.

Set FIRECRAWL_API_KEY in your environment to enable.
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

_FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"

# Stat columns → canonical output keys
_PLAYER_STAT_MAP = [
    ("goals",               ["Gls", "Goals"]),
    ("assists",             ["Ast", "Assists"]),
    ("appearances",         ["MP", "Matches Played", "Apps"]),
    ("starts",              ["Starts", "GS"]),
    ("minutes",             ["Min", "Minutes"]),
    ("xg",                  ["xG", "Expected Goals"]),
    ("xag",                 ["xAG"]),
    ("shots",               ["Sh", "Shots"]),
    ("shots_on_target",     ["SoT", "Shots on Target"]),
    ("pass_completion_pct", ["Cmp%", "Pass Cmp%"]),
    ("progressive_passes",  ["PrgP", "Progressive Passes"]),
    ("tackles",             ["Tkl", "Tackles"]),
    ("interceptions",       ["Int", "Interceptions"]),
]


class FirecrawlRetriever:
    """
    Retriever backed by the Firecrawl web scraping API.

    Mirrors the FBrefRetriever interface. Specialised for current-season
    data that is unavailable in StatsBomb's free historical dataset.
    """

    def __init__(self, cache: Optional[DataCache] = None, api_key: Optional[str] = None):
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY", "")
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = bool(self.api_key)
        if not self._available:
            logger.warning("FIRECRAWL_API_KEY not set — FirecrawlRetriever disabled")
        return self._available

    # ── Internal HTTP helpers ─────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _search_sync(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search + scrape via Firecrawl. Returns list of {url, title, markdown}."""
        resp = requests.post(
            f"{_FIRECRAWL_BASE}/search",
            headers=self._headers(),
            json={
                "query": query,
                "limit": limit,
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "proxy": "auto",
                },
            },
            timeout=45,
        )
        if not resp.ok:
            logger.warning("Firecrawl search error %s: %s", resp.status_code, resp.text[:200])
            return []
        return resp.json().get("data", [])

    def _scrape_sync(self, url: str) -> str:
        """Scrape a single URL and return its clean markdown."""
        resp = requests.post(
            f"{_FIRECRAWL_BASE}/scrape",
            headers=self._headers(),
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "proxy": "auto",
            },
            timeout=45,
        )
        if not resp.ok:
            return ""
        return resp.json().get("data", {}).get("markdown", "")

    async def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    async def scrape(self, url: str) -> str:
        return await asyncio.to_thread(self._scrape_sync, url)

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

        cache_key = f"fc_player|{player_name}|{team_name}|{season}"
        cached = self.cache.get("firecrawl_player", cache_key)
        if cached:
            return cached

        season_str = _season_code_to_full_hyphen(season) if season else ""
        team_part = f" {team_name}" if team_name else ""
        query = (
            f'"{player_name}"{team_part} season stats {season_str} '
            f"site:fbref.com OR site:sofascore.com"
        ).strip()

        try:
            results = await self.search(query, limit=3)
            for r in results:
                markdown = r.get("markdown", "")
                stats = _extract_player_stats_from_markdown(player_name, markdown)
                if stats:
                    stats["data_source"] = "firecrawl"
                    stats["source_url"] = r.get("url", "")
                    self.cache.set("firecrawl_player", cache_key, stats)
                    return stats
        except Exception as exc:
            logger.warning("Firecrawl player stats failed [%s]: %s", player_name, exc)

        return {}

    async def get_team_season_stats(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
        stat_type: str = "standard",
    ) -> Dict[str, Any]:
        # Team aggregates are less useful from scraped pages; delegate to other sources
        return {}

    async def get_tactical_profile(
        self,
        team_name: str,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        cache_key = f"fc_matchlog|{team_name}|{season}"
        cached = self.cache.get("firecrawl_matchlog", cache_key)
        if cached:
            return cached[:last_n]

        season_str = _season_code_to_full_hyphen(season) if season else "current season"
        query = (
            f"{team_name} match results {season_str} "
            f"site:fbref.com OR site:bbc.com/sport"
        )

        try:
            results = await self.search(query, limit=3)
            for r in results:
                markdown = r.get("markdown", "")
                matches = _extract_match_log_from_markdown(team_name, markdown)
                if matches:
                    self.cache.set("firecrawl_matchlog", cache_key, matches)
                    return matches[:last_n]
        except Exception as exc:
            logger.warning("Firecrawl match log failed [%s]: %s", team_name, exc)

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

        cache_key = f"fc_h2h|{team1}|{team2}|{season}"
        cached = self.cache.get("firecrawl_h2h", cache_key)
        if cached:
            return cached

        query = (
            f'"{team1}" vs "{team2}" head to head results history '
            f"site:fbref.com OR site:11v11.com OR site:transfermarkt.com"
        )

        try:
            results = await self.search(query, limit=3)
            for r in results:
                markdown = r.get("markdown", "")
                matches = _extract_h2h_from_markdown(team1, team2, markdown)
                if matches:
                    self.cache.set("firecrawl_h2h", cache_key, matches)
                    return matches
        except Exception as exc:
            logger.warning("Firecrawl H2H failed [%s vs %s]: %s", team1, team2, exc)

        return []

    async def close(self) -> None:
        return None


# ── Markdown extraction helpers ───────────────────────────────────────────────

def _parse_markdown_table(markdown: str) -> List[Dict[str, str]]:
    """
    Parse all markdown tables in a page into a list of row dicts.
    Handles multi-line headers by collapsing them.
    """
    rows: List[Dict[str, str]] = []
    header: Optional[List[str]] = None
    in_table = False

    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if in_table:
                header = None
                in_table = False
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]

        # Separator row (|---|---|)
        if all(re.match(r"^[-: ]+$", c) for c in cells if c.strip()):
            in_table = bool(header)
            continue

        if header is None:
            header = cells
        elif in_table and len(cells) >= len(header) - 2:
            rows.append(dict(zip(header, cells)))

    return rows


def _extract_player_stats_from_markdown(
    player_name: str, markdown: str
) -> Optional[Dict[str, Any]]:
    """Find the player's row in any table in the markdown and return mapped stats."""
    rows = _parse_markdown_table(markdown)
    p_lower = player_name.lower()

    target_row: Optional[Dict[str, str]] = None
    for row in rows:
        if any(p_lower in v.lower() for v in row.values()):
            target_row = row
            break

    if not target_row:
        return None

    def _get(*candidates: str) -> Optional[float]:
        for candidate in candidates:
            for col, val in target_row.items():
                if candidate.lower() in col.lower():
                    try:
                        return float(val.replace(",", ""))
                    except (ValueError, AttributeError):
                        pass
        return None

    stats = {k: _get(*cols) for k, cols in _PLAYER_STAT_MAP}
    stats = {k: v for k, v in stats.items() if v is not None}

    if not stats:
        return None

    # Pick up player name and team from the row if available
    for col, val in target_row.items():
        if "player" in col.lower() or "name" in col.lower():
            stats.setdefault("player_name", val)
        if "squad" in col.lower() or "team" in col.lower() or "club" in col.lower():
            stats.setdefault("team_name", val)

    return stats


def _extract_match_log_from_markdown(
    team_name: str, markdown: str
) -> List[Dict[str, Any]]:
    """Extract a match results table from markdown."""
    rows = _parse_markdown_table(markdown)
    matches: List[Dict[str, Any]] = []

    for row in rows:
        # Need at least a date and a result
        date_val = next((v for k, v in row.items() if "date" in k.lower()), None)
        result_val = next((v for k, v in row.items()
                          if k.strip() in ("Result", "Res", "W/D/L")), None)

        if not date_val or not result_val:
            continue

        result_upper = result_val.strip().upper()
        if result_upper not in ("W", "D", "L"):
            continue

        opponent = next((v for k, v in row.items()
                        if "opponent" in k.lower() or "opp" in k.lower()), "")
        gf = next((v for k, v in row.items() if k.strip() in ("GF", "For", "Gls")), None)
        ga = next((v for k, v in row.items() if k.strip() in ("GA", "Against")), None)
        venue = next((v for k, v in row.items() if "venue" in k.lower()), "")

        try:
            gf_val = int(float(gf)) if gf else None
        except (ValueError, TypeError):
            gf_val = None
        try:
            ga_val = int(float(ga)) if ga else None
        except (ValueError, TypeError):
            ga_val = None

        matches.append({
            "date": str(date_val)[:10],
            "opponent": str(opponent),
            "venue": str(venue),
            "result": result_upper,
            "goals_for": gf_val,
            "goals_against": ga_val,
            "data_source": "firecrawl",
        })

    matches.sort(key=lambda x: x["date"], reverse=True)
    return matches


def _extract_h2h_from_markdown(
    team1: str, team2: str, markdown: str
) -> List[Dict[str, Any]]:
    """Extract H2H match rows from markdown content."""
    rows = _parse_markdown_table(markdown)
    t1, t2 = team1.lower(), team2.lower()
    matches: List[Dict[str, Any]] = []

    for row in rows:
        all_vals = " ".join(row.values()).lower()
        if t1 not in all_vals or t2 not in all_vals:
            continue

        date_val = next((v for k, v in row.items() if "date" in k.lower()), None)
        if not date_val:
            continue

        home = next((v for k, v in row.items() if "home" in k.lower()), "")
        away = next((v for k, v in row.items() if "away" in k.lower()), "")
        score = next((v for k, v in row.items()
                     if k.strip() in ("Score", "Result", "FT")), "")

        matches.append({
            "date": str(date_val)[:10],
            "home": str(home),
            "away": str(away),
            "score": str(score),
            "data_source": "firecrawl",
        })

    return matches


# ── Season format helpers ─────────────────────────────────────────────────────

def _season_code_to_full_hyphen(code: str) -> str:
    """Convert "24-25" → "2024-2025" for URL/search use."""
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
