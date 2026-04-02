"""
ESPN Data Retriever — live data via ESPN public API.
No API key required; uses the unofficial but stable ESPN site API.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .cache import DataCache
from .base import BaseRetriever

logger = logging.getLogger(__name__)

# ── ESPN API base ────────────────────────────────────────────────────────────
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# league slug by sport keyword
LEAGUE_SLUGS: Dict[str, str] = {
    "soccer": "eng.1",   # Premier League default; overridden by lookup
    "basketball": "nba",
    "american_football": "nfl",
    "baseball": "mlb",
    "hockey": "nhl",
}

# Pre-built team name → ESPN team ID for the most-requested clubs.
# Lookup falls back to a live search if the name isn't here.
TEAM_ID_CACHE: Dict[str, str] = {
    # Premier League
    "manchester united": "360",
    "man utd": "360",
    "man united": "360",
    "liverpool": "364",
    "arsenal": "359",
    "chelsea": "363",
    "manchester city": "382",
    "man city": "382",
    "tottenham": "367",
    "spurs": "367",
    "tottenham hotspur": "367",
    "newcastle": "361",
    "newcastle united": "361",
    "aston villa": "362",
    "west ham": "371",
    "west ham united": "371",
    "wolves": "380",
    "wolverhampton": "380",
    "brighton": "331",
    "everton": "368",
    "fulham": "370",
    "brentford": "337",
    "crystal palace": "384",
    "nottingham forest": "393",
    "bournemouth": "349",
    "leeds": "357",
    "leeds united": "357",
    "sunderland": "366",
    # La Liga
    "barcelona": "83",
    "real madrid": "86",
    "atletico madrid": "1068",
    "sevilla": "243",
    # Bundesliga
    "bayern munich": "132",
    "borussia dortmund": "124",
    # Serie A
    "juventus": "111",
    "ac milan": "103",
    "inter milan": "110",
}

# Which ESPN league does a given sport map to for roster/schedule calls?
SPORT_LEAGUE: Dict[str, tuple] = {
    "soccer": ("soccer", "eng.1"),
    "basketball": ("basketball", "nba"),
    "american_football": ("football", "nfl"),
    "baseball": ("baseball", "mlb"),
    "hockey": ("hockey", "nhl"),
    "cricket": ("cricket", "test"),
    "rugby": ("rugby", "world"),
    "tennis": ("tennis", "atp"),
}


def _get_stat(stats: List[Dict], name: str) -> float:
    for s in stats:
        if s.get("name") == name:
            return s.get("value", 0.0)
    return 0.0


def _extract_player_stats(athlete: Dict) -> Dict[str, Any]:
    """Flatten ESPN roster athlete entry into a clean dict."""
    cats = (
        athlete.get("statistics", {})
        .get("splits", {})
        .get("categories", [])
    )
    gen_stats: List[Dict] = []
    off_stats: List[Dict] = []
    gk_stats: List[Dict] = []
    for cat in cats:
        name = cat.get("name", "")
        if name == "general":
            gen_stats = cat.get("stats", [])
        elif name == "offensive":
            off_stats = cat.get("stats", [])
        elif name == "goalKeeping":
            gk_stats = cat.get("stats", [])

    injuries = athlete.get("injuries", [])
    injury_status = injuries[0].get("description", "Healthy") if injuries else "Healthy"

    return {
        "id": athlete.get("id"),
        "name": athlete.get("displayName", "Unknown"),
        "short_name": athlete.get("shortName", ""),
        "position": athlete.get("position", {}).get("displayName", "Unknown"),
        "position_abbr": athlete.get("position", {}).get("abbreviation", ""),
        "jersey": athlete.get("jersey", ""),
        "age": athlete.get("age"),
        "nationality": athlete.get("citizenship", "Unknown"),
        "nationality_abbr": athlete.get("citizenshipCountry", {}).get("abbreviation", ""),
        "headshot": athlete.get("headshot", {}).get("href", ""),
        "injury_status": injury_status,
        "stats": {
            "appearances": int(_get_stat(gen_stats, "appearances")),
            "goals": int(_get_stat(off_stats, "totalGoals")),
            "assists": int(_get_stat(off_stats, "goalAssists")),
            "shots": int(_get_stat(off_stats, "totalShots")),
            "shots_on_target": int(_get_stat(off_stats, "shotsOnTarget")),
            "yellow_cards": int(_get_stat(gen_stats, "yellowCards")),
            "red_cards": int(_get_stat(gen_stats, "redCards")),
            "fouls_committed": int(_get_stat(gen_stats, "foulsCommitted")),
            "fouls_suffered": int(_get_stat(gen_stats, "foulsSuffered")),
            # GK only
            "saves": int(_get_stat(gk_stats, "saves")),
            "goals_conceded": int(_get_stat(gk_stats, "goalsConceded")),
        },
    }


class ESPNDataRetriever:
    """Fetches live data from the ESPN public API with caching."""

    def __init__(self, cache: Optional[DataCache] = None):
        self.cache = cache or DataCache(ttl_seconds=1800)  # 30 min cache

    # ── helpers ──────────────────────────────────────────────────────────────

    def _sport_league(self, sport: str) -> tuple:
        return SPORT_LEAGUE.get(sport.lower(), ("soccer", "eng.1"))

    async def _get(self, url: str, params: Dict = None) -> Dict:
        """Async GET with a short timeout and error logging."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url, params=params or {})
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            logger.warning("ESPN API error [%s]: %s", url, exc)
            return {}

    def _team_id(self, team_name: str) -> Optional[str]:
        return TEAM_ID_CACHE.get(team_name.lower().strip())

    async def _resolve_team_id(self, team_name: str, sport_slug: str, league_slug: str) -> Optional[str]:
        """Resolve team ID: fast dict lookup first, live API search fallback."""
        tid = self._team_id(team_name)
        if tid:
            return tid
        # Live search
        data = await self._get(
            f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams"
        )
        for sport_entry in data.get("sports", []):
            for league in sport_entry.get("leagues", []):
                for team_entry in league.get("teams", []):
                    t = team_entry.get("team", {})
                    if team_name.lower() in t.get("displayName", "").lower():
                        tid = t["id"]
                        TEAM_ID_CACHE[team_name.lower()] = tid
                        return tid
        logger.warning("Could not resolve ESPN team ID for '%s'", team_name)
        return None

    # ── public methods ────────────────────────────────────────────────────────

    async def get_match_context(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Fetch the exact datetime and venue for the team's next event."""
        cached = self.cache.get("match_context", f"{sport}:{team_name}")
        if cached:
            return cached
            
        sport_slug, league_slug = self._sport_league(sport)
        tid = await self._resolve_team_id(team_name, sport_slug, league_slug)
        if not tid:
            from datetime import datetime, timezone
            return {"date": datetime.now(timezone.utc).isoformat(), "venue": "Unknown Venue"}
            
        team_data = await self._get(f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams/{tid}")
        team = team_data.get("team", {})
        next_event = team.get("nextEvent", [{}])[0]
        
        from datetime import datetime, timezone
        date = next_event.get("date", datetime.now(timezone.utc).isoformat())
        venue_info = next_event.get("competitions", [{}])[0].get("venue", {})
        venue_name = venue_info.get("fullName", "Unknown Venue")
        
        result = {"date": date, "venue": venue_name}
        self.cache.set("match_context", f"{sport}:{team_name}", result)
        return result

    async def get_team_squad(self, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Return current squad roster with real stats from ESPN."""
        cached = self.cache.get("squad", f"{sport}:{team_name}")
        if cached:
            return cached

        sport_slug, league_slug = self._sport_league(sport)
        tid = await self._resolve_team_id(team_name, sport_slug, league_slug)
        if not tid:
            return self._mock_squad(team_name)

        # Fetch roster and team detail in parallel
        roster_data, team_data = await asyncio.gather(
            self._get(f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams/{tid}/roster"),
            self._get(f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams/{tid}"),
        )

        athletes = roster_data.get("athletes", [])
        players = [_extract_player_stats(a) for a in athletes]

        team = team_data.get("team", {})
        record_items = team.get("record", {}).get("items", [{}])
        record_summary = record_items[0].get("summary", "0-0-0") if record_items else "0-0-0"
        # e.g. "15-10-6" → wins-draws-losses for soccer
        parts = record_summary.split("-")
        wins, draws, losses = (int(parts[0]), int(parts[1]), int(parts[2])) if len(parts) == 3 else (0, 0, 0)

        standing = team.get("standingSummary", "Unknown standing")

        players.sort(
            key=lambda p: (
                p.get("stats", {}).get("appearances", 0),
                p.get("stats", {}).get("goals", 0)
            ),
            reverse=True
        )

        result = {
            "team": team_name,
            "team_id": tid,
            "league": league_slug,
            "standing": standing,
            "record": {"wins": wins, "draws": draws, "losses": losses, "summary": record_summary},
            "players": players,
            "player_count": len(players),
        }
        self.cache.set("squad", f"{sport}:{team_name}", result)
        return result

    async def get_recent_form(self, team_name: str, sport: str = "soccer", num_games: int = 5) -> Dict[str, Any]:
        """Return recent form data from ESPN scoreboard/schedule."""
        cached = self.cache.get("form", f"{sport}:{team_name}:{num_games}")
        if cached:
            return cached

        sport_slug, league_slug = self._sport_league(sport)
        tid = await self._resolve_team_id(team_name, sport_slug, league_slug)
        if not tid:
            return self._mock_form(team_name)

        # Get the team detail which includes next event and standings
        team_data = await self._get(f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams/{tid}")
        team = team_data.get("team", {})

        record_items = team.get("record", {}).get("items", [{}])
        record = record_items[0] if record_items else {}
        stats = {s["name"]: s["value"] for s in record.get("stats", [])}

        wins = int(stats.get("wins", 0))
        draws = int(stats.get("ties", 0))
        losses = int(stats.get("losses", 0))
        goals_for = int(stats.get("pointsFor", 0))
        goals_against = int(stats.get("pointsAgainst", 0))
        points = int(stats.get("points", 0))
        rank = int(stats.get("rank", 0))
        ppg = round(points / max(wins + draws + losses, 1), 2)

        # Use schedule to get recent results for this team
        schedule = await self._get(f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams/{tid}/schedule")
        recent_results = []
        events = schedule.get("events", [])
        
        # Filter for completed events
        completed_events = [
            e for e in events 
            if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("completed", False)
        ]
        
        # Sort by date descending (most recent first)
        completed_events.sort(key=lambda x: x.get("date", ""), reverse=True)
        recent_events = completed_events[:num_games]
        
        for event in recent_events:
            comps = event.get("competitions", [])
            if not comps: continue
            competitors = comps[0].get("competitors", [])
            
            team_score = 0
            opp_score = 0
            for c in competitors:
                score = float(c.get("score", {}).get("value", 0))
                if c.get("id") == str(tid):
                    team_score = score
                else:
                    opp_score = score
                    
            if team_score > opp_score:
                recent_results.append("W")
            elif team_score < opp_score:
                recent_results.append("L")
            else:
                recent_results.append("D")
                
        # Reverse to chronological order (oldest to newest) for form string
        recent_results.reverse()
        form_string = "".join(recent_results)

        result = {
            "team": team_name,
            "form_string": form_string or "UNKNOWN",
            "recent_results": list(form_string) if form_string else [],
            "record": {"wins": wins, "draws": draws, "losses": losses},
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_difference": goals_for - goals_against,
            "points": points,
            "rank": rank,
            "ppg": ppg,
            "standing": team.get("standingSummary", ""),
        }
        self.cache.set("form", f"{sport}:{team_name}:{num_games}", result)
        return result

    async def get_player_stats(self, player_name: str, team_name: str, sport: str = "soccer") -> Dict[str, Any]:
        """Return stats for a specific player by searching the team roster."""
        cached = self.cache.get("player", f"{sport}:{team_name}:{player_name}")
        if cached:
            return cached

        squad = await self.get_team_squad(team_name, sport)
        for player in squad.get("players", []):
            if player_name.lower() in player["name"].lower():
                self.cache.set("player", f"{sport}:{team_name}:{player_name}", player)
                return player

        return {"name": player_name, "team": team_name, "stats": {}, "error": "Player not found"}

    async def get_head_to_head(self, home_team: str, away_team: str, sport: str = "soccer") -> Dict[str, Any]:
        """
        ESPN's public API doesn't expose H2H history directly.
        Returns a structured stub with the teams' current-season records.
        """
        cached = self.cache.get("h2h", f"{sport}:{home_team}:{away_team}")
        if cached:
            return cached

        home_form, away_form = await asyncio.gather(
            self.get_recent_form(home_team, sport),
            self.get_recent_form(away_team, sport),
        )

        result = {
            "home_team": home_team,
            "away_team": away_team,
            "note": "Live H2H history not available via ESPN public API. Current-season form shown.",
            "home_record": home_form.get("record", {}),
            "away_record": away_form.get("record", {}),
            "home_standing": home_form.get("standing", ""),
            "away_standing": away_form.get("standing", ""),
        }
        self.cache.set("h2h", f"{sport}:{home_team}:{away_team}", result)
        return result

    async def get_team_news(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Fetch team news headlines from ESPN."""
        cached = self.cache.get("news", f"{sport}:{team_name}")
        if cached:
            return cached

        sport_slug, league_slug = self._sport_league(sport)
        tid = await self._resolve_team_id(team_name, sport_slug, league_slug)
        if not tid:
            return []

        data = await self._get(
            f"{ESPN_BASE}/{sport_slug}/{league_slug}/teams/{tid}/news"
        )
        articles = data.get("articles", [])[:10]
        result = [
            {
                "headline": a.get("headline", ""),
                "description": a.get("description", ""),
                "published": a.get("published", ""),
                "url": a.get("links", {}).get("web", {}).get("href", ""),
            }
            for a in articles
        ]
        self.cache.set("news", f"{sport}:{team_name}", result)
        return result

    async def get_injuries(self, team_name: str, sport: str = "soccer") -> List[Dict[str, Any]]:
        """Return injured players by reading the roster's injury field."""
        squad = await self.get_team_squad(team_name, sport)
        return [
            {
                "player": p["name"],
                "position": p["position"],
                "status": p["injury_status"],
            }
            for p in squad.get("players", [])
            if p.get("injury_status") not in ("Healthy", "", None)
        ]

    # ── mock fallbacks ────────────────────────────────────────────────────────

    def _mock_squad(self, team_name: str) -> Dict[str, Any]:
        logger.warning("Using mock squad for '%s' (ESPN lookup failed)", team_name)
        return {
            "team": team_name,
            "players": [
                {"name": f"{team_name} Player {i}", "position": "Midfielder",
                 "stats": {"goals": 0, "assists": 0, "appearances": 0},
                 "injury_status": "Healthy"}
                for i in range(1, 6)
            ],
            "standing": "Unknown",
            "record": {"wins": 0, "draws": 0, "losses": 0},
        }

    def _mock_form(self, team_name: str) -> Dict[str, Any]:
        logger.warning("Using mock form for '%s' (ESPN lookup failed)", team_name)
        return {
            "team": team_name,
            "form_string": "UNKNOWN",
            "record": {"wins": 0, "draws": 0, "losses": 0},
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "rank": 0,
        }
