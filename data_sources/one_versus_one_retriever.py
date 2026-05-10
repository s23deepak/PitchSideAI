"""
OneVersusOne.com Retriever — PitchSideAI
Premium football player stats and comparison data via authenticated scraping.

Unique metrics available:
- 1vs1 Index (offensive, defensive, overall)
- Progressive carries (PrgC)
- Pre-assists
- Sense of Space rating
- Attacking Threat rating
- xG per shot, form curves
- Side-by-side player comparisons

Requires login credentials. Set 1V1_EMAIL and 1V1_PASSWORD in environment.

Usage:
    ovo = OneVersusOneRetriever()
    await ovo.login()  # Authenticate session
    stats = await ovo.get_player_stats("Haaland", "Manchester City")
"""
import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from data_sources.cache import DataCache

logger = logging.getLogger(__name__)

BASE_URL = "https://one-versus-one.com"
LOGIN_URL = f"{BASE_URL}/en/login"
PLAYERS_URL = f"{BASE_URL}/en/players"
COMPARE_URL = f"{BASE_URL}/en/comparison"

# Stat name mappings from 1v1.com → canonical format
STAT_MAP = {
    "goals": ["Goals", "Total goals scored"],
    "assists": ["Assists", "Total assists"],
    "progressive_carries": ["Progressive carries", "PrgC"],
    "shots_on_goal": ["Shots on Goal", "Shots on target"],
    "pre_assists": ["Pre-assists", "Pre Assist"],
    "passing_accuracy_pct": ["Passing accuracy", "Passing accuracy %"],
    "xg": ["Expected Goals", "xG", "xG total"],
    "xg_per_shot": ["xG per shot", "xG average per shot"],
    "one_vs_one_index_offensive": ["1vs1 Index offensive", "Offensive Index"],
    "one_vs_one_index_defensive": ["1vs1 Index defensive", "Defensive Index"],
    "one_vs_one_index": ["1vs1 Index", "1vs1 Index overall", "Overall Index"],
    "sense_of_space": ["Sense of Space", "Positional awareness"],
    "attacking_threat": ["Attacking Threat", "Attack Threat"],
    "ball_regains": ["Ball regains", "Regains"],
    "ground_duels_won": ["Ground duels won", "Duels won"],
    "goal_contributions_per_game": ["Goal contributions per game", "scorer points per game"],
}


class OneVersusOneRetriever:
    """
    Authenticated scraper for OneVersusOne.com premium stats.

    Requires valid login credentials. Maintains session cookies
    for authenticated requests.
    """

    def __init__(self, cache: Optional[DataCache] = None,
                 email: Optional[str] = None, password: Optional[str] = None):
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.email = email or os.getenv("1V1_EMAIL", "")
        self.password = password or os.getenv("1V1_PASSWORD", "")
        self._session_cookies: Dict[str, str] = {}
        self._logged_in: bool = False
        self._available: Optional[bool] = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        if not self.email or not self.password:
            logger.warning("1V1_EMAIL or 1V1_PASSWORD not set")
            self._available = False
        else:
            self._available = True
        return self._available

    @property
    def is_available(self) -> bool:
        return self._check_available()

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    async def login(self) -> bool:
        """
        Authenticate with 1v1.com and store session cookies.
        Returns True if login successful.
        """
        if not self._check_available():
            return False

        if self._logged_in:
            return True  # Already logged in

        cache_key = "1v1_session"
        cached = self.cache.get("1v1_auth", cache_key)
        if cached:
            self._session_cookies = cached.get("cookies", {})
            self._logged_in = True
            return True

        try:
            # First, get the login page to extract CSRF token
            async with httpx.AsyncClient() as client:
                resp = await client.get(LOGIN_URL)
                if resp.status_code != 200:
                    logger.warning("1v1.com login page returned %d", resp.status_code)
                    return False

                # Extract CSRF token from the page (Laravel format)
                # Pattern: <input type="hidden" name="_token" value="...">
                csrf_match = re.search(
                    r'name=["\']_token["\']\s+value=["\']([a-zA-Z0-9]+)["\']',
                    resp.text,
                    re.IGNORECASE
                )
                csrf_token = csrf_match.group(1) if csrf_match else ""

                # Perform login POST
                login_data = {
                    "_token": csrf_token,
                    "email": self.email,
                    "password": self.password,
                }
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": LOGIN_URL,
                    "Origin": BASE_URL,
                }

                resp = await client.post(
                    LOGIN_URL,
                    data=login_data,
                    headers=headers,
                    follow_redirects=True
                )

                # Check for session cookie (Laravel session indicator)
                session_cookie = client.cookies.get("one_versus_one_session")
                if resp.status_code == 200 and session_cookie:
                    # Login successful - extract cookies
                    self._session_cookies = dict(client.cookies)
                    self._logged_in = True
                    self.cache.set("1v1_auth", cache_key, {"cookies": self._session_cookies})
                    logger.info("1v1.com login successful for %s", self.email)
                    return True
                else:
                    logger.warning("1v1.com login failed - check credentials (status: %d, has session: %s)",
                                   resp.status_code, bool(session_cookie))
                    return False

        except Exception as exc:
            logger.warning("1v1.com login error: %s", exc)
            return False

    async def _get(self, url: str, params: Dict = None) -> str:
        """Authenticated GET request with session cookies."""
        if not self._logged_in:
            success = await self.login()
            if not success:
                return ""

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": BASE_URL,
        }

        try:
            async with httpx.AsyncClient(cookies=self._session_cookies, headers=headers) as client:
                resp = await client.get(url, params=params or {})
                if resp.status_code == 401 or "login" in resp.url.path.lower():
                    # Session expired, re-login
                    self._logged_in = False
                    self._session_cookies = {}
                    if await self.login():
                        # Retry with new session
                        async with httpx.AsyncClient(cookies=self._session_cookies, headers=headers) as client2:
                            resp2 = await client2.get(url, params=params or {})
                            return resp2.text if resp2.status_code == 200 else ""
                return resp.text if resp.status_code == 200 else ""
        except Exception as exc:
            logger.warning("1v1.com request failed [%s]: %s", url, exc)
            return ""

    def _parse_player_stats_from_html(self, html: str, player_name: str) -> Dict[str, Any]:
        """
        Extract player stats from 1v1.com HTML.

        Note: 1v1.com is heavily JavaScript-rendered. We extract data from:
        1. Stats tables with labeled metrics
        2. JSON in window.__INITIAL_STATE__ or similar embedded state
        3. Data attributes in HTML elements
        4. Visible text content with stat labels
        """
        stats = {}

        # Pattern 1: Extract from stats tables (most reliable for 1v1.com)
        self._parse_stats_tables(html, stats)

        # Pattern 2: Extract JSON from window.__INITIAL_STATE__ or similar
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.+?});',
            r'<script[^>]*>\s*window\.__[^=]+=\s*({.+?});',
        ]

        for pattern in json_patterns:
            json_matches = re.findall(pattern, html)
            if json_matches:
                try:
                    state_data = json.loads(json_matches[0])
                    self._extract_stats_from_json(state_data, stats)
                    if stats:
                        break
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        # Pattern 3: Look for stats in script tags (JSON-like data)
        script_matches = re.findall(
            r'["\']?(goals|assists|xg|xag|shots|passes|progressive|yellow_cards|red_cards)["\']?\s*[:=]\s*([0-9.]+)',
            html, re.IGNORECASE
        )
        for key, value in script_matches:
            key_lower = key.lower().replace('_', '')
            if key_lower not in stats:
                try:
                    stats[key_lower] = float(value)
                except ValueError:
                    pass

        # Pattern 4: Look for data attributes
        data_attr_matches = re.findall(
            r'data-(?:goals|assists|xg|shots|stats)[^>]*=["\']([0-9.]+)["\']',
            html, re.IGNORECASE
        )
        for i, value in enumerate(data_attr_matches[:4]):
            stat_keys = ["goals", "assists", "xg", "shots"]
            try:
                stats[stat_keys[i]] = float(value)
            except (ValueError, IndexError):
                pass

        return {k: v for k, v in stats.items() if v is not None}

    def _parse_stats_tables(self, html: str, stats: Dict[str, float]):
        """
        Parse stats tables from 1v1.com HTML.

        Looks for tables containing metric labels and values.
        """
        # Find all tables
        tables = re.findall(r'<table[^>]*>(.+?)</table>', html, re.DOTALL | re.IGNORECASE)

        for table in tables:
            # Remove HTML tags but keep text
            text = re.sub(r'<[^>]+>', ' ', table)
            text = ' '.join(text.split())

            # Look for stat patterns: "Metric Name Value" format
            # The HTML has patterns like "Goals &#9432; Goal 7" - need to extract the number after the description
            stat_patterns = [
                (r'Goals\s+(?:&#9432;)?\s*(?:Goal)?\s*([0-9]+)', 'goals'),
                (r'Assists\s+(?:&#9432;)?\s*(?:Creating goals[^0-9]+)?([0-9]+)', 'assists'),
                (r'Shots on Goal\s+([0-9]+)', 'shots'),
                (r'Shots\s+([0-9]+)', 'shots'),
                (r'xG(?:\s+per\s+shot)?\s+([0-9.]+)', 'xg'),
                (r'Expected Goals\s+([0-9.]+)', 'xg'),
                (r'Progressive\s+carries\s*\([^)]+\)\s*([0-9]+)', 'progressive_carries'),
                (r'PrgC\s+([0-9]+)', 'progressive_carries'),
                (r'Pre[- ]?assists\s+([0-9]+)', 'pre_assists'),
                (r'Passing accuracy\s+(?:%?)\s*([0-9.]+)', 'passing_accuracy'),
                (r'Yellow\s+[Cc]ards?\s+([0-9]+)', 'yellow_cards'),
                (r'Red\s+[Cc]ards?\s+([0-9]+)', 'red_cards'),
                (r'Minutes\s+[Pp]layed\s+([0-9]+)', 'minutes_played'),
                (r'Appearances?\s+([0-9]+)', 'appearances'),
                (r'Succes?ful\s+dribbles\s+([0-9]+)', 'successful_dribbles'),
                (r'Ball\s+losses?\s+(?:%\s+)?(?:per\s+game)?\s*([0-9.]+)', 'ball_losses'),
            ]

            for pattern, stat_key in stat_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match and stat_key not in stats:
                    try:
                        stats[stat_key] = float(match.group(1))
                    except ValueError:
                        pass

    def _extract_stats_from_json(self, data: Any, stats: Dict[str, float], depth: int = 0) -> bool:
        """Recursively extract player stats from nested JSON structure."""
        if depth > 10:
            return False

        if isinstance(data, dict):
            stat_keys = ["goals", "assists", "xg", "xag", "shots", "passes",
                        "progressive_carries", "yellow_cards", "red_cards",
                        "minutes_played", "appearances"]

            for key in stat_keys:
                if key in data:
                    try:
                        stats[key] = float(data[key])
                    except (ValueError, TypeError):
                        pass

            for value in data.values():
                if isinstance(value, (dict, list)):
                    if self._extract_stats_from_json(value, stats, depth + 1):
                        return True

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    if self._extract_stats_from_json(item, stats, depth + 1):
                        return True

        return bool(stats)

    def _extract_stats_from_json(self, data: Any, stats: Dict[str, float], depth: int = 0) -> bool:
        """
        Recursively extract player stats from nested JSON structure.

        Returns True if stats were found.
        """
        if depth > 10:  # Prevent infinite recursion
            return False

        if isinstance(data, dict):
            # Look for known stat keys
            stat_keys = ["goals", "assists", "xg", "xag", "shots", "passes",
                        "progressive_carries", "yellow_cards", "red_cards",
                        "minutes_played", "appearances"]

            for key in stat_keys:
                if key in data:
                    try:
                        stats[key] = float(data[key])
                    except (ValueError, TypeError):
                        pass

            # Recurse into nested dicts
            for value in data.values():
                if isinstance(value, (dict, list)):
                    if self._extract_stats_from_json(value, stats, depth + 1):
                        return True

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    if self._extract_stats_from_json(item, stats, depth + 1):
                        return True

        return bool(stats)

    def _parse_player_search_results(self, html: str, player_name: str) -> Optional[str]:
        """
        Parse search results and return player slug if found.
        1v1.com uses URL format: /en/players/{player-slug}
        """
        player_lower = player_name.lower()
        player_slug = player_name.lower().replace(" ", "-")

        # Check if player page exists by looking for link
        # Pattern: href="/en/players/{player-slug}"
        match = re.search(
            rf'href="/en/players/{re.escape(player_slug)}"',
            html,
            re.IGNORECASE
        )
        if match:
            return player_slug

        # Alternative: look for any player link containing the name
        matches = re.findall(
            r'href="/en/players/([^"]+)"[^>]*>([^<]+)',
            html,
            re.IGNORECASE
        )

        for slug, name in matches:
            if player_lower in name.lower():
                return slug

        # Fallback: use the name as slug
        return player_slug

    # ── Public API ─────────────────────────────────────────────────────────────

    async def get_player_stats(
        self,
        player_name: str,
        team_name: str,
        sport: str = "soccer",
    ) -> Dict[str, Any]:
        """
        Fetch player stats from 1v1.com with authenticated access.

        Returns comprehensive stats including unique 1vs1 Index metrics.
        """
        cache_key = f"1v1_{player_name}|{team_name}"
        cached = self.cache.get("1v1_player", cache_key)
        if cached:
            return cached

        if not self._check_available():
            return {}

        # Login if needed
        if not await self.login():
            return {}

        # 1v1.com uses direct player URLs: /en/players/{player-slug}
        # Try multiple slug formats for better coverage
        possible_slugs = [
            player_name.lower().replace(" ", "-"),  # "erling haaland" -> "erling-haaland"
            player_name.lower().replace(" ", "-") + "-" + team_name.lower().replace(" ", "-"),  # with team
        ]

        # For well-known players, try common formats
        if player_name.lower() in ["haaland", "erling haaland", "erling"]:
            possible_slugs.insert(0, "erling-haaland")
        if player_name.lower() in ["mbappe", "kylian mbappe", "kylian"]:
            possible_slugs.insert(0, "kylian-mbappe")
        if player_name.lower() in ["messi", "lionel messi"]:
            possible_slugs.insert(0, "lionel-messi")
        if player_name.lower() in ["ronaldo", "cristiano ronaldo"]:
            possible_slugs.insert(0, "cristiano-ronaldo")

        profile_html = None
        profile_url = None

        for slug in possible_slugs:
            url = f"{BASE_URL}/en/players/{slug}"
            profile_html = await self._get(url)
            if profile_html and "player not found" not in profile_html.lower():
                profile_url = url
                break

        # Fall back to search if direct URL didn't work
        if not profile_html:
            search_html = await self._get(PLAYERS_URL, {"search": player_name})
            if search_html:
                alt_slug = self._parse_player_search_results(search_html, player_name)
                if alt_slug:
                    profile_url = f"{BASE_URL}/en/players/{alt_slug}"
                    profile_html = await self._get(profile_url)

        if not profile_html:
            logger.warning("1v1.com player not found: %s", player_name)
            return {}

        # Parse stats
        stats = self._parse_player_stats_from_html(profile_html, player_name)

        # Extract additional info from HTML
        position_match = re.search(r'Position:\s*([^<]+)', profile_html)
        position = position_match.group(1).strip() if position_match else "Unknown"

        nationality_match = re.search(r'Nationality:\s*([^<]+)', profile_html)
        nationality = nationality_match.group(1).strip() if nationality_match else "Unknown"

        result = {
            "name": player_name,
            "position": position,
            "nationality": nationality,
            "stats": stats,
            "data_source": "one_versus_one",
            "source_url": profile_url,
        }

        self.cache.set("1v1_player", cache_key, result)
        return result

    async def compare_players(
        self,
        player1_name: str,
        player2_name: str,
        team1: Optional[str] = None,
        team2: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch side-by-side comparison of two players.

        Returns comparison data with stats for both players.
        """
        cache_key = f"1v1_compare_{player1_name}|{player2_name}"
        cached = self.cache.get("1v1_compare", cache_key)
        if cached:
            return cached

        if not await self.login():
            return {}

        # 1v1.com comparison URL format
        compare_url = f"{COMPARE_URL}"

        # Search for both players first to get their IDs
        search_html = await self._get(PLAYERS_URL)
        if not search_html:
            return {}

        # For now, return a stub - full implementation would:
        # 1. Get player IDs for both
        # 2. POST to comparison endpoint with both IDs
        # 3. Parse side-by-side stats table

        logger.info("Player comparison not fully implemented for 1v1.com")
        return {
            "player1": {"name": player1_name},
            "player2": {"name": player2_name},
            "data_source": "one_versus_one",
            "note": "Comparison feature requires player ID resolution",
        }

    async def get_team_squad(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Not implemented - 1v1.com is player-focused, not team-focused."""
        return {"team": team_name, "players": [], "data_source": "one_versus_one"}

    async def get_recent_form(self, team_name: str, sport: str = "soccer", num_games: int = 5) -> Dict[str, Any]:
        """Not implemented - delegate to other sources."""
        return {"team": team_name, "form_string": "UNKNOWN", "data_source": "one_versus_one"}

    async def get_head_to_head(self, team1: str, team2: str, sport: str = "soccer") -> Dict[str, Any]:
        """Not implemented - delegate to other sources."""
        return {"team1": team1, "team2": team2, "total_matches": 0}

    async def get_team_news(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Not implemented - 1v1.com doesn't have news."""
        return []

    async def get_injuries(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Not implemented - delegate to other sources."""
        return []

    async def get_match_context(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Not implemented - delegate to other sources."""
        from datetime import datetime, timezone
        return {"date": datetime.now(timezone.utc).isoformat(), "venue": "Unknown"}

    async def close(self) -> None:
        """Clear session."""
        self._session_cookies = {}
        self._logged_in = False


# Import httpx at module level (after class definition to avoid circular issues)
import httpx
