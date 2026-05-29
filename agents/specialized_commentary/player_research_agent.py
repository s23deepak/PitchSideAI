"""
Player Research Agent - Research team squads with detailed player information.

Gathers biographical, statistical, and contextual data for players using
Tavily search (biography), FBref (statistics), and ESPN (roster) data sources.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import json
import logging
import re
from agents.base import BaseAgent
from data_sources import DataCache, WikipediaRetriever
from data_sources.factory import (
    get_retriever,
    get_fbref_retriever,
    get_search_service,
)
from data_sources.player_profile_db import get_player_db

logger = logging.getLogger(__name__)


class PlayerResearchAgent(BaseAgent):
    """Research and profile team squads with real data."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        fbref_retriever: Optional[Any] = None,
        search_service: Optional[Any] = None,
    ):
        """
        Initialize player research agent.

        Args:
            model_id: Bedrock model ID (default: Nova Pro for quality)
            sport: Sport type
            cache: Optional shared cache instance
            fbref_retriever: Optional FBref retriever for player stats
            search_service: Optional Tavily search service
        """
        super().__init__(model_id=model_id, sport=sport, agent_type="player_research")
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.retriever = get_retriever(self.sport, cache=self.cache)
        self.fbref = fbref_retriever or (get_fbref_retriever(cache=self.cache) if sport == "soccer" else None)
        self.search_service = search_service or get_search_service(cache=self.cache)
        self.wiki_retriever = WikipediaRetriever(
            cache=self.cache,
            search_service=self.search_service
        )

    async def execute(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Main execution method for compatibility with BaseAgent.

        Args:
            home_team: Home team name
            away_team: Away team name

        Returns:
            Combined squad research for both teams
        """
        return await self.research_squad_pair(home_team, away_team)

    async def research_squad_pair(
        self,
        home_team: str,
        away_team: str,
        fixture_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Research both team squads simultaneously.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            Squad data for both teams
        """
        start_time = datetime.utcnow()
        fixture_players = (fixture_context or {}).get("players", {})

        # Research both squads in parallel
        home_squad, away_squad = await asyncio.gather(
            self.research_squad(
                home_team,
                fixture_players=fixture_players.get("home_team", []),
            ),
            self.research_squad(
                away_team,
                fixture_players=fixture_players.get("away_team", []),
            ),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="squad_research_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "home_count": len(home_squad.get("players", [])),
                "away_count": len(away_squad.get("players", [])),
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_team": home_squad,
            "away_team": away_squad,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def research_squad(
        self,
        team_name: str,
        fixture_players: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Research complete team squad with player-by-player analysis.

        Args:
            team_name: Team name

        Returns:
            Squad data with researched players
        """
        # Fetch ESPN squad data
        espn_squad = await self.retriever.get_team_squad(team_name, self.sport)

        # ESPN's fallback can fabricate "{team} Player 1" rows. Treat those as
        # unavailable evidence instead of allowing mock names into notes.
        raw_players = espn_squad.get("players", [])
        players = [
            player for player in raw_players
            if not self._is_placeholder_player(player, team_name)
        ][:5]  # 5 for local dev (bump to 25 for production)

        enriched_players = await asyncio.gather(
            *[self._research_player_detailed(p, team_name) for p in players],
            return_exceptions=True,
        )

        # Filter out any errors
        enriched_players = [p for p in enriched_players if not isinstance(p, Exception)]
        enriched_players = self._merge_fixture_candidates(
            enriched_players,
            fixture_players or [],
            team_name,
        )
        enriched_players = await self._synthesize_player_profiles(team_name, enriched_players)

        return {
            "team_name": team_name,
            "players": enriched_players,
            "total_players_researched": len(enriched_players),
            "data_sources": self._data_sources(enriched_players),
            "data_status": "accepted" if enriched_players else "unavailable",
            "research_timestamp": datetime.utcnow().isoformat(),
        }

    def _is_placeholder_player(self, player: Dict[str, Any], team_name: str) -> bool:
        """Reject deterministic mock squad rows from upstream fallbacks."""
        if not isinstance(player, dict):
            return True
        name = str(player.get("name") or "").strip()
        if not name or name.lower() == "unknown":
            return True
        normalized_team = re.escape(" ".join(team_name.split()))
        if re.fullmatch(rf"{normalized_team}\s+Player\s+\d+", name, flags=re.I):
            return True
        return bool(re.fullmatch(r"(?:Home|Away|Team|Player)\s*\d*", name, flags=re.I))

    def _merge_fixture_candidates(
        self,
        researched_players: List[Dict[str, Any]],
        fixture_players: List[Dict[str, Any]],
        team_name: str,
    ) -> List[Dict[str, Any]]:
        merged = list(researched_players)
        seen = {self._normalize_player_name(player.get("name", "")) for player in merged}

        for player in fixture_players:
            if not isinstance(player, dict) or self._is_placeholder_player(player, team_name):
                continue
            name_key = self._normalize_player_name(player.get("name", ""))
            if not name_key or name_key in seen:
                continue
            merged.append(self._fixture_candidate(player, team_name))
            seen.add(name_key)
            if len(merged) >= 8:
                break
        return merged

    def _fixture_candidate(self, player: Dict[str, Any], team_name: str) -> Dict[str, Any]:
        evidence = str(player.get("evidence") or player.get("profile") or "").strip()
        return {
            "name": player.get("name", "Unknown"),
            "position": player.get("position") or "Unknown",
            "squad_number": "N/A",
            "age": "Unknown",
            "stats": {},
            "biography": "",
            "nationality": "N/A",
            "injury_status": "Not verified",
            "profile": evidence[:180] or (
                f"{player.get('name', 'This player')} is a fixture-evidence candidate for "
                f"{team_name}; role and starter status are not verified."
            ),
            "data_source": player.get("data_source") or "fixture_resolver",
            "source_urls": player.get("source_urls") or [],
            "evidence": evidence,
            "confidence": player.get("confidence", 0.55),
            "candidate_status": player.get("candidate_status") or "fixture-evidence; not confirmed starter",
        }

    def _normalize_player_name(self, name: str) -> str:
        return re.sub(r"\W+", "", str(name or "").lower())

    def _data_sources(self, players: List[Dict[str, Any]]) -> List[str]:
        sources = set()
        if any(player.get("data_source") != "fixture_resolver" for player in players):
            sources.update({"ESPN", "FBref", "Tavily"})
        if any(player.get("data_source") == "fixture_resolver" for player in players):
            sources.add("FixtureResolver")
        return sorted(sources)

    async def _research_player_detailed(
        self,
        player_data: Dict[str, Any],
        team_name: str,
    ) -> Dict[str, Any]:
        """
        Deep research on individual player using multiple data sources.
        Checks the local SQLite DB first to avoid redundant external calls.

        Args:
            player_data: Basic player data from ESPN
            team_name: Team name for context

        Returns:
            Enriched player profile
        """
        player_name = player_data.get("name", "Unknown")
        db = get_player_db()

        try:
            # ── Check local DB for cached static profile ──
            cached_profile = db.get_profile(player_name, self.sport)
            if cached_profile:
                logger.info("DB hit for %s — skipping ESPN bio fields", player_name)
                # Merge DB fields into player_data (ESPN may have fresher injury_status)
                for field in ("nationality", "nationality_abbr", "position", "headshot", "wikipedia_url"):
                    if cached_profile.get(field) and not player_data.get(field):
                        player_data[field] = cached_profile[field]

            # ── Save ESPN bio fields to DB (static data we already have) ──
            db.upsert_profile(player_name, self.sport, player_data)

            # ── Fetch external data (Tavily bio + FBref stats) in parallel ──
            wiki_bio, player_stats = await asyncio.gather(
                self.wiki_retriever.get_player_biography(player_name, self.sport),
                self._fetch_player_stats(player_name, team_name),
                return_exceptions=True,
            )

            # Handle potential exceptions
            if isinstance(wiki_bio, Exception):
                wiki_bio = {}
            if isinstance(player_stats, Exception):
                player_stats = {}
            player_stats = player_stats or player_data.get("stats", {})

            # ── Save FBref stats to DB for this season ──
            if player_stats and any(player_stats.get(k) for k in ("goals", "assists", "appearances")):
                db.upsert_season_stats(
                    player_name, self.sport, "25-26", "fbref", player_stats
                )

            # ── Save notable achievements from Wikipedia if present ──
            if wiki_bio.get("notable_achievements") or wiki_bio.get("wikipedia_url"):
                db.upsert_profile(player_name, self.sport, {
                    "wikipedia_url": wiki_bio.get("wikipedia_url"),
                    "notable_achievements": wiki_bio.get("notable_achievements"),
                })

            return {
                "name": player_name,
                "position": player_data.get("position", "Unknown"),
                "squad_number": player_data.get("squad_number") or player_data.get("jersey", "N/A"),
                "age": player_data.get("age", "Unknown"),
                "stats": player_stats,
                "biography": wiki_bio.get("career_summary", "")[:100],
                "nationality": wiki_bio.get("nationality") or player_data.get("nationality", "N/A"),
                "injury_status": player_data.get("injury_status", "Healthy"),
                "profile": "",
            }

        except Exception as e:
            logger.error("Error researching player %s: %s", player_name, e)
            # Return basic profile on error
            return {
                "name": player_name,
                "position": player_data.get("position", "Unknown"),
                "squad_number": player_data.get("squad_number") or player_data.get("jersey", "N/A"),
                "error": str(e),
            }

    async def _synthesize_player_profiles(
        self,
        team_name: str,
        players: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Create all player blurbs for a squad with one LLM call."""
        if not players:
            return players
        players_needing_profiles = [player for player in players if not player.get("profile")]
        if not players_needing_profiles:
            return players

        payload = []
        for player in players_needing_profiles:
            stats = player.get("stats", {}) if isinstance(player.get("stats"), dict) else {}
            payload.append({
                "name": player.get("name", "Unknown"),
                "position": player.get("position", "Unknown"),
                "age": player.get("age", "Unknown"),
                "goals": stats.get("goals", 0) or 0,
                "assists": stats.get("assists", 0) or 0,
                "appearances": stats.get("appearances", 0) or 0,
                "career": player.get("biography", "")[:150],
            })

        prompt = f"""Create concise {self.sport} commentary profiles for these {team_name} players.

Use only the provided facts. For each player, write one compact sentence covering playing style, main strength, and likely match impact.

Return valid JSON only:
{{"profiles": [{{"name": "Player Name", "profile": "One sentence."}}]}}

Players:
{json.dumps(payload, ensure_ascii=True)}
"""

        try:
            response = await self.call_llm(prompt=prompt, temperature=0.3, max_tokens=420)
            parsed = await self.parse_json_response(response)
            profile_by_name = {
                item.get("name", ""): item.get("profile", "")
                for item in parsed.get("profiles", [])
                if isinstance(item, dict)
            }
        except Exception as exc:
            logger.warning("Batch profile synthesis failed for %s: %s", team_name, exc)
            profile_by_name = {}

        for player in players:
            name = player.get("name", "Unknown")
            if not player.get("profile"):
                player["profile"] = profile_by_name.get(name) or self._fallback_profile(player, team_name)
        return players

    def _fallback_profile(self, player: Dict[str, Any], team_name: str) -> str:
        """Deterministic profile when the batch LLM call is unavailable."""
        name = player.get("name", "This player")
        position = player.get("position", "player")
        stats = player.get("stats", {}) if isinstance(player.get("stats"), dict) else {}
        goals = stats.get("goals", 0) or 0
        assists = stats.get("assists", 0) or 0
        contribution = []
        if goals:
            contribution.append(f"{goals} goals")
        if assists:
            contribution.append(f"{assists} assists")
        contribution_text = f" with {' and '.join(contribution)}" if contribution else ""
        return f"{name} is a {position} for {team_name}{contribution_text}, profiled for likely match impact from verified squad data."

    async def _fetch_player_stats(
        self, player_name: str, team_name: str
    ) -> Dict[str, Any]:
        """Fetch player stats from local DB first, then MultiSourceRetriever as fallback."""
        db = get_player_db()

        # Check DB for current season stats (saved from a previous successful fetch)
        cached_stats = db.get_season_stats(player_name, self.sport, "25-26", "multi")
        if cached_stats:
            logger.info("DB stats hit for %s — skipping external fetch", player_name)
            return cached_stats

        if not self.fbref or not self.fbref.is_available:
            return {}

        try:
            # MultiSourceRetriever uses get_player_stats(player_name, team_name, sport)
            stats = await self.fbref.get_player_stats(player_name, team_name, self.sport)
            if stats and not stats.get("error"):
                db.upsert_season_stats(player_name, self.sport, "25-26", stats.get("data_source", "multi"), stats)
                return stats
            return {}
        except Exception as exc:
            logger.warning("MultiSource player stats failed for %s: %s", player_name, exc)
            return {}

    async def close(self):
        """Clean up resources."""
        pass
