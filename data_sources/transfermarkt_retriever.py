"""
Transfermarkt Retriever — PitchAI
Player market values, stats, and profile data scraped from Transfermarkt.

Uses httpx with proper headers to avoid bot detection.
Rate limit: 20 requests/minute recommended.

Data available:
- Player market values (historical)
- Player stats (goals, assists, appearances by competition)
- Profile info (age, nationality, position, club)
- Transfer history

Usage:
    tm = TransfermarktRetriever()
    profile = await tm.get_player_stats("Salah", "Liverpool")
    # Returns: {name, position, market_value, stats: {goals, assists, ...}}
"""
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

# Transfermarkt URLs and patterns
BASE_URL = "https://www.transfermarkt.com"
SEARCH_URL = "https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche"

# Common player position mappings
POSITION_MAP = {
    "Goalkeeper": "GK",
    "Centre-Back": "CB",
    "Left-Back": "LB",
    "Right-Back": "RB",
    "Defensive Midfield": "DM",
    "Central Midfield": "CM",
    "Attacking Midfield": "AM",
    "Left Winger": "LW",
    "Right Winger": "RW",
    "Second Striker": "SS",
    "Centre-Forward": "CF",
}

# Team name mappings for better search results
TEAM_ALIASES = {
    "manchester united": "Manchester United",
    "man utd": "Manchester United",
    "man united": "Manchester United",
    "liverpool": "Liverpool FC",
    "arsenal": "Arsenal FC",
    "chelsea": "Chelsea FC",
    "manchester city": "Manchester City",
    "man city": "Manchester City",
    "tottenham": "Tottenham Hotspur",
    "spurs": "Tottenham Hotspur",
    "newcastle": "Newcastle United",
    "aston villa": "Aston Villa",
    "west ham": "West Ham United",
    "brighton": "Brighton & Hove Albion",
    "wolves": "Wolverhampton Wanderers",
    "everton": "Everton FC",
    "barcelona": "FC Barcelona",
    "real madrid": "Real Madrid",
    "atletico madrid": "Atlético Madrid",
    "bayern munich": "Bayern Munich",
    "borussia dortmund": "Borussia Dortmund",
    "juventus": "Juventus FC",
    "ac milan": "AC Milan",
    "inter milan": "Inter Milan",
    "psg": "Paris Saint-Germain",
    "paris saint-germain": "Paris Saint-Germain",
}


def _clean_market_value(value_str: str) -> str:
    """Parse market value string like '€120.00m' or '€15.00m'."""
    if not value_str:
        return "Unknown"
    # Keep the formatted string as-is for display
    return value_str.strip()


def _parse_number(value: Any) -> Optional[float]:
    """Parse a number from various string formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove commas and currency symbols
        cleaned = re.sub(r"[€,mM]", "", value.strip())
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    return None


class TransfermarktRetriever:
    """
    Async scraper for Transfermarkt player data.

    Note: This is a lightweight scraper. For production use,
    consider using the felipeall/transfermarkt-api wrapper.
    """

    def __init__(self, cache: Optional[DataCache] = None):
        self.cache = cache or DataCache(ttl_seconds=3600)
        self._available: Optional[bool] = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        # Transfermarkt is always "available" (no API key needed)
        # but may rate-limit or block requests
        self._available = True
        return True

    @property
    def is_available(self) -> bool:
        return self._check_available()

    async def _get(self, url: str, params: Dict = None) -> str:
        """Async GET with browser-like headers and redirect following."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.transfermarkt.com/",
        }
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                headers=headers,
                follow_redirects=True
            ) as client:
                r = await client.get(url, params=params or {})
                r.raise_for_status()
                return r.text
        except Exception as exc:
            logger.warning("Transfermarkt request failed [%s]: %s", url, exc)
            return ""

    def _normalize_team_name(self, team_name: str) -> str:
        """Map common team name variations to Transfermarkt names."""
        return TEAM_ALIASES.get(team_name.lower().strip(), team_name)

    async def _search_player(self, player_name: str, team_name: Optional[str] = None) -> Optional[str]:
        """
        Search for a player and return their profile URL.
        Returns the player_id if found.
        """
        html = await self._get(SEARCH_URL, {"query": player_name})
        if not html:
            return None

        # Parse search results - look for player links
        # Pattern: /profil/spieler/123456
        player_pattern = r'href="/([^/]+)/profil/spieler/(\d+)"'
        matches = re.findall(player_pattern, html)

        if not matches:
            return None

        # If team filter provided, try to match
        if team_name:
            team_normalized = self._normalize_team_name(team_name)
            for link_type, player_id in matches:
                # Check if this player's club matches
                player_html = await self._get(f"{BASE_URL}/{link_type}/profil/spieler/{player_id}")
                if player_html and team_normalized.lower() in player_html.lower():
                    return player_id

        # Return first match if no team filter or no match found
        return matches[0][1] if matches else None

    async def _fetch_player_profile(self, player_id: str) -> Dict[str, Any]:
        """Fetch player profile page and extract data."""
        url = f"{BASE_URL}/{player_id}/profil/spieler/{player_id}"
        html = await self._get(url)

        if not html:
            return {}

        # Extract player name
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        player_name = name_match.group(1).strip() if name_match else "Unknown"

        # Extract position
        pos_match = re.search(r'<span[^>]*class="tooltip"[^>]*>([^<]+)</span>', html)
        position = pos_match.group(1).strip() if pos_match else "Unknown"
        position_abbr = POSITION_MAP.get(position, position)

        # Extract age/date of birth
        dob_match = re.search(r'Date of birth[^<]*<[^>]*>([^<]+)<', html)
        date_of_birth = dob_match.group(1).strip() if dob_match else ""

        # Extract nationality
        nationality_match = re.search(r'<img[^>]*flaggen[^>]*alt="([^"]+)"', html)
        nationality = nationality_match.group(1) if nationality_match else "Unknown"

        # Extract market value
        market_value_match = re.search(r'Market value[^<]*<[^>]*>([^<]+)<', html)
        market_value = _clean_market_value(market_value_match.group(1)) if market_value_match else "Unknown"

        # Extract current club
        club_match = re.search(r'href="/verein/(\d+)/[^"]*"[^>]*>([^<]+)</a>', html)
        current_club = club_match.group(2).strip() if club_match else "Unknown"

        # Extract stats table if available
        stats = self._parse_performance_stats(html)

        return {
            "id": player_id,
            "name": player_name,
            "position": position,
            "position_abbr": position_abbr,
            "date_of_birth": date_of_birth,
            "nationality": nationality,
            "market_value": market_value,
            "current_club": current_club,
            "stats": stats,
            "data_source": "transfermarkt",
        }

    def _parse_performance_stats(self, html: str) -> Dict[str, Any]:
        """Parse player performance stats from the stats table."""
        stats = {
            "appearances": 0,
            "goals": 0,
            "assists": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "minutes_played": 0,
        }

        # Look for stats table - Transfermarkt uses specific classes
        # Pattern: find table with class "items" containing performance data
        table_match = re.search(
            r'<table[^>]*class="items"[^>]*>(.*?)</table>', html, re.DOTALL
        )
        if not table_match:
            return stats

        table_html = table_match.group(1)

        # Extract all numeric values from table cells
        # This is a simplified extraction - full implementation would parse rows properly
        goals_match = re.findall(r'<td[^>]*class="rechts"[^>]*>(\d+)</td>', table_html)
        if goals_match:
            # Typically: appearances, goals, assists, yellow, red pattern
            try:
                stats["appearances"] = int(goals_match[0]) if len(goals_match) > 0 else 0
                stats["goals"] = int(goals_match[1]) if len(goals_match) > 1 else 0
                stats["assists"] = int(goals_match[2]) if len(goals_match) > 2 else 0
            except (IndexError, ValueError):
                pass

        return stats

    # ── Public API ─────────────────────────────────────────────────────────────

    async def get_player_stats(
        self,
        player_name: str,
        team_name: str,
        sport: str = "soccer"
    ) -> Dict[str, Any]:
        """
        Fetch player profile and stats from Transfermarkt.

        Returns comprehensive player data including market value.
        """
        cache_key = f"tm_{player_name}|{team_name}"
        cached = self.cache.get("transfermarkt_player", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return {}

        # Search for player
        player_id = await self._search_player(player_name, team_name)
        if not player_id:
            logger.warning("Transfermarkt: Player not found - %s (%s)", player_name, team_name)
            return {}

        # Fetch profile
        profile = await self._fetch_player_profile(player_id)
        if not profile:
            return {}

        self.cache.set("transfermarkt_player", cache_key, profile)
        return profile

    async def get_team_squad(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """
        Fetch team squad from Transfermarkt.

        Note: This is a simplified implementation. Full squad scraping
        would require parsing the team's squad page.
        """
        cache_key = f"tm_squad_{team_name}"
        cached = self.cache.get("transfermarkt_squad", cache_key)
        if cached:
            return cached

        # For now, return a stub - full implementation would scrape
        # the team's squad page at /verein/spielplan/verein/{team_id}
        logger.info("Transfermarkt: Team squad not fully implemented for %s", team_name)
        return {"team": team_name, "players": [], "data_source": "transfermarkt"}

    async def get_recent_form(self, team_name: str, sport: str = "soccer", num_games: int = 5) -> Dict[str, Any]:
        """Not implemented for Transfermarkt - delegate to other sources."""
        return {"team": team_name, "form_string": "UNKNOWN", "data_source": "transfermarkt"}

    async def get_head_to_head(self, team1: str, team2: str, sport: str = "soccer") -> Dict[str, Any]:
        """Not implemented for Transfermarkt - delegate to other sources."""
        return {"team1": team1, "team2": team2, "total_matches": 0}

    async def get_team_news(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Not implemented for Transfermarkt - delegate to other sources."""
        return []

    async def get_injuries(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Not implemented for Transfermarkt - delegate to other sources."""
        return []

    async def get_match_context(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Not implemented for Transfermarkt - delegate to other sources."""
        from datetime import datetime, timezone
        return {"date": datetime.now(timezone.utc).isoformat(), "venue": "Unknown"}

    async def close(self) -> None:
        """No-op for cleanup."""
        return None
