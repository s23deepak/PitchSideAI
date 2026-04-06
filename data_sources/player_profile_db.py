"""
PlayerProfileDB — SQLite-backed persistent cache for immutable player data.

Stores:
  - Static bio fields (DOB, birthplace, nationality, height, previous clubs)
  - Completed-season stats (goals, assists, xG — frozen once a season ends)

Does NOT store (volatile / manager-dependent):
  - Career summary, playing style, LLM-generated profiles
  - Current-season stats (fetched live)
  - Injury status
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "player_profiles.db"
)

# Current season is always fetched live; completed seasons are permanent.
_CURRENT_SEASON = "25-26"


def _player_key(name: str, sport: str) -> str:
    """Normalize player name + sport into a stable lookup key."""
    return f"{name.strip().lower()}|{sport.strip().lower()}"


class PlayerProfileDB:
    """Thin SQLite wrapper for permanent player data."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("PLAYER_DB_PATH", _DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ── schema ────────────────────────────────────────────────────────────────

    def _ensure_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS player_profiles (
                player_key   TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                sport        TEXT NOT NULL DEFAULT 'soccer',
                espn_id      TEXT,
                position     TEXT,
                position_abbr TEXT,
                nationality  TEXT,
                nationality_abbr TEXT,
                age          INTEGER,
                headshot     TEXT,
                date_of_birth TEXT,
                birth_place  TEXT,
                height_cm    REAL,
                weight_kg    REAL,
                wikipedia_url TEXT,
                notable_achievements TEXT,  -- JSON array
                fetched_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS player_season_stats (
                player_key   TEXT NOT NULL,
                season       TEXT NOT NULL,
                league       TEXT NOT NULL DEFAULT '',
                source       TEXT NOT NULL DEFAULT 'espn',
                stats_json   TEXT NOT NULL,  -- full stats blob
                fetched_at   TEXT NOT NULL,
                PRIMARY KEY (player_key, season, source)
            );

            CREATE INDEX IF NOT EXISTS idx_profiles_sport ON player_profiles(sport);
            CREATE INDEX IF NOT EXISTS idx_stats_season ON player_season_stats(season);
        """)
        self._conn.commit()

    # ── bio read / write ──────────────────────────────────────────────────────

    def get_profile(self, player_name: str, sport: str) -> Optional[Dict[str, Any]]:
        """Look up a player's static profile. Returns None on miss."""
        key = _player_key(player_name, sport)
        row = self._conn.execute(
            "SELECT * FROM player_profiles WHERE player_key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        profile = dict(row)
        if profile.get("notable_achievements"):
            try:
                profile["notable_achievements"] = json.loads(profile["notable_achievements"])
            except (json.JSONDecodeError, TypeError):
                pass
        return profile

    def upsert_profile(self, player_name: str, sport: str, data: Dict[str, Any]) -> None:
        """Insert or update a player's static bio fields."""
        key = _player_key(player_name, sport)
        now = datetime.utcnow().isoformat()

        achievements = data.get("notable_achievements")
        if isinstance(achievements, list):
            achievements = json.dumps(achievements)

        self._conn.execute(
            """
            INSERT INTO player_profiles
                (player_key, name, sport, espn_id, position, position_abbr,
                 nationality, nationality_abbr, age, headshot,
                 date_of_birth, birth_place, height_cm, weight_kg,
                 wikipedia_url, notable_achievements, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_key) DO UPDATE SET
                espn_id = COALESCE(excluded.espn_id, espn_id),
                position = COALESCE(excluded.position, position),
                position_abbr = COALESCE(excluded.position_abbr, position_abbr),
                nationality = COALESCE(excluded.nationality, nationality),
                nationality_abbr = COALESCE(excluded.nationality_abbr, nationality_abbr),
                age = COALESCE(excluded.age, age),
                headshot = COALESCE(excluded.headshot, headshot),
                date_of_birth = COALESCE(excluded.date_of_birth, date_of_birth),
                birth_place = COALESCE(excluded.birth_place, birth_place),
                height_cm = COALESCE(excluded.height_cm, height_cm),
                weight_kg = COALESCE(excluded.weight_kg, weight_kg),
                wikipedia_url = COALESCE(excluded.wikipedia_url, wikipedia_url),
                notable_achievements = COALESCE(excluded.notable_achievements, notable_achievements),
                updated_at = excluded.updated_at
            """,
            (
                key,
                player_name,
                sport,
                data.get("id") or data.get("espn_id"),
                data.get("position"),
                data.get("position_abbr"),
                data.get("nationality"),
                data.get("nationality_abbr"),
                data.get("age"),
                data.get("headshot"),
                data.get("date_of_birth"),
                data.get("birth_place"),
                data.get("height_cm"),
                data.get("weight_kg"),
                data.get("wikipedia_url"),
                achievements,
                now,
                now,
            ),
        )
        self._conn.commit()

    # ── season stats read / write ─────────────────────────────────────────────

    def get_season_stats(
        self,
        player_name: str,
        sport: str,
        season: str,
        source: str = "espn",
    ) -> Optional[Dict[str, Any]]:
        """Look up completed-season stats. Returns None if not cached or if current season."""
        if season == _CURRENT_SEASON:
            return None  # always fetch current season live
        key = _player_key(player_name, sport)
        row = self._conn.execute(
            "SELECT stats_json FROM player_season_stats WHERE player_key = ? AND season = ? AND source = ?",
            (key, season, source),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["stats_json"])
        except (json.JSONDecodeError, TypeError):
            return None

    def upsert_season_stats(
        self,
        player_name: str,
        sport: str,
        season: str,
        source: str,
        stats: Dict[str, Any],
    ) -> None:
        """Store season stats. Current-season data is accepted (will be overwritten next fetch)."""
        key = _player_key(player_name, sport)
        now = datetime.utcnow().isoformat()
        self._conn.execute(
            """
            INSERT INTO player_season_stats (player_key, season, league, source, stats_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_key, season, source) DO UPDATE SET
                stats_json = excluded.stats_json,
                fetched_at = excluded.fetched_at
            """,
            (
                key,
                season,
                stats.get("league", ""),
                source,
                json.dumps(stats, default=str),
                now,
            ),
        )
        self._conn.commit()

    def get_all_season_stats(
        self, player_name: str, sport: str
    ) -> List[Dict[str, Any]]:
        """Get all stored seasons for a player."""
        key = _player_key(player_name, sport)
        rows = self._conn.execute(
            "SELECT season, source, stats_json, fetched_at FROM player_season_stats WHERE player_key = ? ORDER BY season DESC",
            (key,),
        ).fetchall()
        results = []
        for row in rows:
            try:
                stats = json.loads(row["stats_json"])
            except (json.JSONDecodeError, TypeError):
                stats = {}
            results.append({
                "season": row["season"],
                "source": row["source"],
                "fetched_at": row["fetched_at"],
                **stats,
            })
        return results

    # ── utility ───────────────────────────────────────────────────────────────

    def close(self):
        self._conn.close()


# ── module-level singleton ────────────────────────────────────────────────────

_instance: Optional[PlayerProfileDB] = None


def get_player_db() -> PlayerProfileDB:
    """Return the module-level singleton."""
    global _instance
    if _instance is None:
        _instance = PlayerProfileDB()
        logger.info("PlayerProfileDB initialized at %s", _instance.db_path)
    return _instance
