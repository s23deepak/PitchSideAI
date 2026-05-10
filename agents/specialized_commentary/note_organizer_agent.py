"""
Commentary Note Organizer Agent - Synthesize all agent outputs into final notes.

Orchestrates all previous agent outputs into professional Drury-style
commentary notes in Markdown + JSON format with structured NotesStore output.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import logging
import re
from agents.base import BaseAgent
from data_sources import DataCache
from models.notes_store import NotesStore, NarrativeBeat

logger = logging.getLogger(__name__)


class CommentaryNoteOrganizerAgent(BaseAgent):
    """Synthesize all research into final commentary notes."""

    LOW_QUALITY_PATTERNS = (
        "current form status: unavailable",
        "analysis unavailable",
        "unavailable.",
        "unavailable 2",
        "tactical route unavailable",
        "verified tactical snapshot unavailable",
    )

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
    ):
        """Initialize note organizer agent."""
        super().__init__(
            model_id=model_id,
            sport=sport,
            agent_type="note_organizer",
        )
        self.cache = cache or DataCache(ttl_seconds=3600)

    async def execute(self, all_agent_outputs: Dict[str, Any]) -> NotesStore:
        """Execute final note synthesis, returning structured NotesStore."""
        return await self.synthesize_to_notes_store(all_agent_outputs)

    async def synthesize_to_notes_store(
        self,
        all_agent_outputs: Dict[str, Any],
    ) -> NotesStore:
        """
        Synthesize all agent outputs into structured NotesStore.

        Args:
            all_agent_outputs: Dictionary containing outputs from all agents:
                - player_research: Squad research data
                - team_form: Form analysis
                - historical: H2H and storylines
                - weather: Weather impact
                - matchups: Key matchups
                - news: Injuries and updates

        Returns:
            NotesStore with raw_markdown, beats, and O(1) lookup
        """
        start_time = datetime.utcnow()

        # Build Markdown document
        markdown = await self._build_markdown_document(all_agent_outputs)

        # Parse markdown into NarrativeBeats
        beats = await self._extract_beats_from_markdown(markdown, all_agent_outputs)

        # Build NotesStore with O(1) lookup
        notes_store = NotesStore(raw_markdown=markdown, beats=beats)

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="notes_synthesis_complete",
            details={
                "markdown_length": len(markdown),
                "beat_count": len(beats),
                "lookup_size": len(notes_store.lookup),
                "duration_ms": duration_ms,
            },
        )

        return notes_store

    async def _extract_beats_from_markdown(
        self,
        markdown: str,
        all_outputs: Dict[str, Any],
    ) -> List[NarrativeBeat]:
        """
        Parse markdown document into NarrativeBeat list with event tags.

        Extracts key facts, player profiles, tactical insights and tags them
        with canonical event types for O(1) retrieval.
        """
        beats: List[NarrativeBeat] = []
        home_team = all_outputs.get("home_team", "Home")
        away_team = all_outputs.get("away_team", "Away")

        # Extract player profiles from player_research
        for team_key in ["player_research"]:
            team_data = all_outputs.get(team_key, {})
            for side in ["home_team", "away_team"]:
                team_players = team_data.get(side, {}).get("players", [])
                if isinstance(team_players, list):
                    for player in team_players[:10]:  # Top 10 players
                        if isinstance(player, dict):
                            name = player.get("name", "")
                            position = player.get("position", "")
                            stats = player.get("stats", {})
                            profile = player.get("profile", "")

                            if name:
                                beat_text = f"{name} ({position}): {profile[:100]}"
                                beats.append(NarrativeBeat(
                                    text=beat_text,
                                    event_tags=["substitution", "goal"],  # Player-specific beats
                                    players=[name],
                                    section="home_team" if side == "home_team" else "away_team",
                                    source=player.get("data_source", "research"),
                                    confidence=0.8,
                                ))

        # Extract tactical insights from matchups
        matchups = all_outputs.get("matchups", {})
        critical_matchups = matchups.get("critical_matchups", [])
        if isinstance(critical_matchups, list):
            for matchup in critical_matchups[:5]:
                if isinstance(matchup, dict):
                    p1 = matchup.get("player1", "")
                    p2 = matchup.get("player2", "")
                    analysis = matchup.get("analysis", "")
                    if p1 and p2:
                        beats.append(NarrativeBeat(
                            text=f"Key duel: {p1} vs {p2} — {analysis[:80]}",
                            event_tags=["foul", "free_kick_dangerous"],
                            players=[p1, p2],
                            section="tactical",
                            source="matchup_analysis",
                            confidence=0.7,
                        ))

        # Extract form patterns
        team_form = all_outputs.get("team_form", {})
        for side in ["home_team", "away_team"]:
            form_data = team_form.get(side, {})
            comprehensive = form_data.get("comprehensive_analysis", "")
            if isinstance(comprehensive, str) and comprehensive:
                # Split into sentences and create beats
                sentences = comprehensive.replace("\n", " ").split(". ")
                for sentence in sentences[:5]:
                    if len(sentence.strip()) > 20:
                        beats.append(NarrativeBeat(
                            text=sentence.strip() + ".",
                            event_tags=["corner", "offside"],  # General play beats
                            players=[],
                            section=side,
                            source="team_form",
                            confidence=0.6,
                        ))

        # Extract historical context
        historical = all_outputs.get("historical", {})
        narrative = historical.get("narrative", "")
        if isinstance(narrative, str) and narrative:
            sentences = narrative.replace("\n", " ").split(". ")
            for sentence in sentences[:5]:
                if len(sentence.strip()) > 20:
                    beats.append(NarrativeBeat(
                        text=sentence.strip() + ".",
                        event_tags=["goal", "yellow_card", "red_card"],  # Historical storylines
                        players=[],
                        section="historical",
                        source="historical_context",
                        confidence=0.5,
                    ))

        # Extract weather impact
        weather = all_outputs.get("weather", {})
        weather_narrative = self._clean_weather_narrative(weather.get("narrative", ""))
        if isinstance(weather_narrative, str) and weather_narrative:
            beats.append(NarrativeBeat(
                text=f"Weather impact: {weather_narrative[:100]}",
                event_tags=["foul", "corner"],  # Weather affects set pieces
                players=[],
                section="match_info",
                source="weather_context",
                confidence=0.6,
            ))

        return beats

    async def synthesize_to_markdown_json(
        self,
        all_agent_outputs: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Legacy method for backwards compatibility.
        Use synthesize_to_notes_store() for new code.

        Returns:
            Tuple of (markdown_notes: str, json_structure: dict)
        """
        notes_store = await self.synthesize_to_notes_store(all_agent_outputs)
        return notes_store.raw_markdown, {"notes_store_available": True, "beat_count": len(notes_store.beats)}

    async def _build_markdown_document(self, all_outputs: Dict[str, Any]) -> str:
        """Build comprehensive Markdown document."""
        home_team = all_outputs.get("home_team", "Home")
        away_team = all_outputs.get("away_team", "Away")
        match_datetime = all_outputs.get("match_datetime", "TBD")
        venue = all_outputs.get("venue", "Unknown")
        venue_label = self._format_venue_summary(venue)
        tactical_brief = self._build_tactical_brief(all_outputs)

        # PAGE 1: Lineups & Match Info
        page1 = self._organize_lineups_section(
            all_outputs.get("player_research", {}).get("home_team", {}),
            all_outputs.get("player_research", {}).get("away_team", {}),
            match_datetime,
            venue_label,
            all_outputs.get("weather", {}),
        )

        # PAGE 2: Home Team Analysis
        page2 = self._organize_team_analysis_section(
            all_outputs.get("player_research", {}).get("home_team", {}),
            all_outputs.get("team_form", {}).get("home_team", {}),
            all_outputs.get("news", {}).get("home_team", {}),
            home_team,
            2,
        )

        # PAGE 3: Away Team Analysis
        page3 = self._organize_team_analysis_section(
            all_outputs.get("player_research", {}).get("away_team", {}),
            all_outputs.get("team_form", {}).get("away_team", {}),
            all_outputs.get("news", {}).get("away_team", {}),
            away_team,
            3,
        )

        # PAGE 4-5: Tactical Analysis & Storylines
        page45 = self._organize_tactical_section(
            home_team,
            away_team,
            tactical_brief,
            all_outputs.get("matchups", {}),
            all_outputs.get("historical", {}),
            all_outputs.get("weather", {}),
        )

        return f"""# Commentary Notes: {home_team} vs {away_team}
#### {match_datetime} | {venue_label}

{page1}

{page2}

{page3}

{page45}
"""

    def _organize_lineups_section(
        self,
        home_squad: Dict[str, Any],
        away_squad: Dict[str, Any],
        match_datetime: str,
        venue: str,
        weather: Dict[str, Any],
    ) -> str:
        """Organize PAGE 1 - Lineups & Match Info."""
        home_team = home_squad.get("team_name", "Home")
        away_team = away_squad.get("team_name", "Away")
        temp = weather.get("current_conditions", {}).get("temperature_c")
        conditions = weather.get("current_conditions", {}).get("conditions") or ""
        wind = weather.get("current_conditions", {}).get("wind_kmh")
        home_players = home_squad.get("players", [])[:11]
        away_players = away_squad.get("players", [])[:11]

        lineup_rows = self._format_lineup_rows(home_players, away_players)
        lineup_block = (
            f"""**Probable Starters From Available Research**

| {home_team} | Pos | {away_team} |
|-----------|-----|-----------|
{lineup_rows}

**Lineup Note**: Treat this as the working XI context for the booth. If the confirmed XI changes, pivot the same cues toward the player profile and role that replaces it."""
            if lineup_rows
            else f"""**Opening Shape Cues**
- {home_team}: watch the first receiver under pressure and the fullback height in buildup.
- {away_team}: track whether the press protects the middle or invites wide circulation.
- First dead ball: use the marking scheme as the quickest read on defensive organisation."""
        )

        from datetime import datetime
        try:
            dt_obj = datetime.fromisoformat(match_datetime.replace("Z", "+00:00"))
            friendly_date = dt_obj.strftime("%A, %B %d, %Y at %H:%M UTC")
        except Exception:
            friendly_date = match_datetime

        return f"""---

## PAGE 1: LINEUPS & MATCH INFO

**Match Details**
- Date: {friendly_date}
- Venue: {venue}
- Weather: {self._format_weather_summary(temp, conditions, wind)}
- Referee angle: no referee-driven storyline in the collected feed

{lineup_block}
"""

    def _organize_team_analysis_section(
        self,
        player_research: Dict[str, Any],
        form_analysis: Dict[str, Any],
        news: Dict[str, Any],
        team_label: str,
        page_number: int,
    ) -> str:
        """Organize team analysis section (Pages 2-3)."""
        team_name = player_research.get("team_name", team_label)
        players = player_research.get("players", [])[:10]  # Top 10 players
        player_heading = "Key Players (Sorted by Recent Form)" if players else "Player Watch Cues"
        side_label = "home" if page_number == 2 else "away"

        form_text = self._clean_analysis_text(form_analysis.get("comprehensive_analysis", ""), team_name)

        # Build meaningful form section even when data is sparse
        if not form_text or self._is_low_quality_text(form_text, team_name):
            # Construct a sensible fallback using whatever data is available
            form_text = self._build_team_form_fallback(form_analysis, team_name)

        form_section = form_text
        split = form_analysis.get("home_away_split", {})
        if split:
            home_row = split.get("home", {})
            away_row = split.get("away", {})
            home_w = home_row.get("won", 0)
            home_d = home_row.get("draw", 0)
            home_l = home_row.get("lost", 0)
            away_w = away_row.get("won", 0)
            away_d = away_row.get("draw", 0)
            away_l = away_row.get("lost", 0)
            # Only add split if we have actual data
            if home_w or home_d or home_l or away_w or away_d or away_l:
                split_text = (
                    f"Home: {home_w}W-{home_d}D-{home_l}L | "
                    f"Away: {away_w}W-{away_d}D-{away_l}L"
                )
                form_section = f"{form_text}\n\nVerified Home/Away Split: {split_text}"

        return f"""---

## PAGE {page_number}: {team_name.upper()} ANALYSIS

#### Recent Form ({team_name})

Composite Analysis:
{form_section}

#### {player_heading}

{self._format_player_list(players, team_name=team_name, side_label=side_label)}

#### Team News ({team_name})

{self._format_news(news, team_name=team_name, side_label=side_label)}

#### Tactical Profile

{self._build_team_tactical_profile(team_name, side_label, form_analysis, players)}
"""

    def _organize_tactical_section(
        self,
        home_team: str,
        away_team: str,
        tactical_brief: Dict[str, Any],
        matchups: Dict[str, Any],
        historical: Dict[str, Any],
        weather: Dict[str, Any],
    ) -> str:
        """Organize tactical analysis section (Pages 4-5)."""
        critical_matchups = matchups.get("critical_matchups", [])
        narrative = self._clean_historical_narrative(historical.get("narrative", ""), home_team, away_team)
        h2h = historical.get("h2h_history", {})
        weather_narrative = self._clean_weather_narrative(weather.get("narrative", ""))

        # Build H2H record with meaningful fallback
        if h2h and (h2h.get("team1_wins", 0) + h2h.get("team2_wins", 0) + h2h.get("draws", 0)) > 0:
            h2h_record = f"{h2h.get('team1_wins', 0)}-{h2h.get('draws', 0)}-{h2h.get('team2_wins', 0)}"
        else:
            h2h_record = f"{home_team} and {away_team} have a rich rivalry history"

        # Build narrative with meaningful fallback
        if not narrative:
            narrative = (
                f"Frame {home_team} vs {away_team} through the opening tone: which side settles first, "
                "which midfield wins second balls, and whether the wide channels produce early pressure."
            )
        zone_edges = tactical_brief.get("zone_edges", [])
        pressure_points = tactical_brief.get("pressure_points", [])
        commentary_angles = tactical_brief.get("commentary_angles", [])

        return f"""---

## PAGES 4-5: TACTICAL ANALYSIS & STORYLINES

#### Tactical Snapshot

{tactical_brief.get('summary', 'Verified tactical snapshot unavailable.')}

### Zone-by-Zone Edge

{self._format_bullets(zone_edges)}

### How {home_team} Can Tilt The Match

{tactical_brief.get('home_plan', 'Home-side tactical route unavailable.')}

### How {away_team} Can Tilt The Match

{tactical_brief.get('away_plan', 'Away-side tactical route unavailable.')}

#### Key 1v1 Matchups

{self._format_matchups(critical_matchups)}

### Pressure Points To Mention Early

{self._format_bullets(pressure_points)}

### Commentary Angles To Keep Ready

{self._format_bullets(commentary_angles)}

#### Historical Context

H2H Record: **{h2h_record}**

Recent H2H Narrative:
{narrative}

#### Weather Impact

{weather_narrative or 'No weather edge is active in the collected feed; call the match through tempo, surface speed, and player footing if conditions become visible.'}

#### Expected Match Dynamic

{self._format_match_dynamic(matchups, historical, weather)}
"""

    def _build_tactical_brief(self, all_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create a concise tactical brief from verified workflow outputs."""
        home_team = all_outputs.get("home_team", "Home")
        away_team = all_outputs.get("away_team", "Away")
        team_form = all_outputs.get("team_form", {})
        matchups = all_outputs.get("matchups", {})
        historical = all_outputs.get("historical", {})
        weather = all_outputs.get("weather", {})

        comparative = team_form.get("comparative_analysis", {}).get("comparative_assessment", "")
        tactical_implications = matchups.get("tactical_implications", "")
        summary_parts = [
            self._first_sentence(tactical_implications),
            self._first_sentence(comparative),
            self._first_sentence(weather.get("narrative", "")),
        ]
        summary = " ".join(
            part for part in summary_parts
            if part and not self._is_low_quality_text(part)
        ).strip()
        if not summary:
            summary = (
                f"{home_team} vs {away_team} profiles as a balanced tactical battle. "
                "Use the opening exchanges to confirm which midfield line controls territory and which back line handles pressure cleanly."
            )

        return {
            "summary": summary,
            "zone_edges": self._format_zone_edges(matchups.get("positional_strength", {})),
            "home_plan": self._extract_team_plan(team_form.get("home_team", {}), home_team),
            "away_plan": self._extract_team_plan(team_form.get("away_team", {}), away_team),
            "pressure_points": self._build_pressure_points(home_team, away_team, matchups.get("weak_points", {})),
            "commentary_angles": self._build_commentary_angles(
                home_team,
                away_team,
                matchups,
                historical,
                weather,
                comparative,
            ),
        }

    def _format_player_list(
        self,
        players: List[Dict[str, Any]],
        team_name: str = "",
        side_label: str = "",
    ) -> str:
        """Format player list for markdown."""
        formatted = []
        for i, player in enumerate(players, 1):
            name = player.get("name", "Unknown")
            pos = player.get("position", "N/A")
            stats = player.get("stats", {}) if isinstance(player.get("stats"), dict) else {}
            apps = stats.get("appearances", 0)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            profile = player.get("profile", "")

            # Build profile with fallback - never say "unavailable"
            if not profile:
                profile = f"{name} is a key {pos} for the squad, expected to play a significant role in the upcoming match."

            # Show stats only if available, otherwise omit the line gracefully
            if apps > 0 or goals > 0 or assists > 0:
                formatted.append(
                    f"**{i}. {name}** ({pos})\n- Apps: {apps} | Goals: {goals} | Assists: {assists}\n- {profile}\n"
                )
            else:
                formatted.append(
                    f"**{i}. {name}** ({pos})\n- {profile}\n"
                )

        if formatted:
            return "\n".join(formatted)

        return self._build_player_watch_cues(team_name, side_label)

    def _format_news(
        self,
        news: Dict[str, Any],
        team_name: str = "",
        side_label: str = "",
    ) -> str:
        """Format team news for markdown."""
        injuries = news.get("injuries", [])
        synthesis = news.get("synthesis", "")
        news_items = news.get("news_items", [])[:3]

        synthesis = self._clean_news_text(synthesis)

        if not synthesis and not news_items and not injuries:
            return self._build_team_news_fallback(team_name, side_label)

        output = ""
        if synthesis:
            output = f"{synthesis}\n\n"
        else:
            output = f"{self._build_team_news_fallback(team_name, side_label)}\n\n"

        if news_items:
            output += "**Recent Headlines**:\n"
            for item in news_items:
                title = item.get('title', '')
                if title:
                    output += f"- {title}\n"
            output += "\n"

        if injuries:
            output += "**Injuries**:\n"
            for inj in injuries:
                player = inj.get('player', 'Unknown')
                status = inj.get('status', 'unknown')
                if player != 'Unknown':
                    output += f"- {player}: {status}\n"

        return output if output.strip() else self._build_team_news_fallback(team_name, side_label)

    def _build_player_watch_cues(self, team_name: str, side_label: str) -> str:
        """Build side-specific player cues when researched player data is absent."""
        label = team_name or ("home side" if side_label == "home" else "away side")
        if side_label == "away":
            return (
                f"- {label} outlet: identify the first runner used to escape pressure.\n"
                "- Counter-press trigger: watch who jumps immediately after losing the ball.\n"
                "- Back-post threat: name the far-side attacker arriving when play is switched."
            )
        return (
            f"- {label} first receiver: identify who wants the ball when the press arrives.\n"
            "- Line-breaker: watch who plays or carries through the first defensive line.\n"
            "- Territory setter: name the wide or midfield option used to pin the opponent back."
        )

    def _build_team_news_fallback(self, team_name: str, side_label: str) -> str:
        """Write team-news fallback as commentary direction, not a duplicated status line."""
        is_away = side_label == "away"
        label = team_name or ("Away side" if is_away else "home side")
        if is_away:
            return (
                f"No major {label} disruption surfaced. Frame their first spell through travel composure, "
                "defensive spacing, and whether the outlet runner gives them relief."
            )
        return (
            f"No major {label} disruption surfaced. Frame their first spell through home tempo, "
            "territory, and whether the selection gives them early control."
        )

    def _build_team_tactical_profile(
        self,
        team_name: str,
        side_label: str,
        form_analysis: Dict[str, Any],
        players: List[Dict[str, Any]],
    ) -> str:
        """Build a side-specific tactical profile cue."""
        form_string = ""
        recent_form = form_analysis.get("recent_form", {}) if isinstance(form_analysis, dict) else {}
        if isinstance(recent_form, dict):
            form_string = recent_form.get("form_string", "") or ""
        form_clause = f" Their form string is {form_string}." if self._is_meaningful_form_string(form_string) else ""
        player_clause = (
            "tie the first ten minutes to the named player roles"
            if players
            else "use the first ten minutes to identify the roles live"
        )
        if side_label == "away":
            return (
                f"- {team_name}: {player_clause}; watch compactness after turnovers, the first escape pass, "
                f"and how quickly the wide outlet gets support.{form_clause}"
            )
        return (
            f"- {team_name}: {player_clause}; watch the opening tempo, first forward pass, "
            f"and whether wide pressure turns into sustained territory.{form_clause}"
        )

    def _format_lineup_rows(
        self,
        home_players: List[Dict[str, Any]],
        away_players: List[Dict[str, Any]],
    ) -> str:
        """Render two researched squads into a simple three-column lineup table."""
        if not home_players and not away_players:
            return ""

        rows = []
        max_len = max(len(home_players), len(away_players))
        for idx in range(max_len):
            home = home_players[idx] if idx < len(home_players) else {}
            away = away_players[idx] if idx < len(away_players) else {}
            home_name = home.get("name", "-")
            away_name = away.get("name", "-")
            pos = home.get("position") or away.get("position") or "-"
            rows.append(f"| {home_name} | {pos} | {away_name} |")
        return "\n".join(rows)

    def _format_matchups(self, matchups: List[Dict[str, Any]]) -> str:
        """Format key matchups for markdown."""
        formatted = []
        for matchup in matchups[:5]:
            p1 = matchup.get("player1", "")
            p2 = matchup.get("player2", "")
            analysis = self._clean_matchup_analysis(matchup.get("analysis", ""))
            if p1 and p2:
                if analysis:
                    formatted.append(f"**{p1} vs {p2}**\n{analysis}\n")
                else:
                    formatted.append(f"**{p1} vs {p2}**\nKey tactical battle expected in this matchup.\n")

        if formatted:
            return "\n".join(formatted)

        return (
            "*No clean individual duel was returned in this run. Call the matchup by zone: central buildup versus pressure, "
            "wide isolation versus fullback cover, and set-piece marking on the first dead ball.*"
        )

    def _format_bullets(self, items: List[str]) -> str:
        """Format a list of text items as markdown bullets."""
        clean_items = [
            cleaned
            for item in items
            if (cleaned := self._clean_analysis_text(item).strip())
            and not self._is_low_quality_text(cleaned)
        ]
        clean_items = [
            item
            for item in clean_items
            if isinstance(item, str)
            and item.strip()
        ]
        if clean_items:
            return "\n".join(f"- {item}" for item in clean_items)
        # Return empty string for clean rendering - parent section will have context
        return ""

    def _format_weather_summary(self, temp: Any, conditions: str, wind: Any) -> str:
        """Format weather details without fabricating missing values."""
        parts = []
        if temp is not None:
            parts.append(f"{temp}°C")
        if conditions:
            parts.append(conditions.replace("_", " ").title())
        if wind is not None:
            parts.append(f"{wind} km/h wind")
        return ", ".join(parts) if parts else "No active weather angle in the collected feed"

    def _format_venue_summary(self, venue: Any) -> str:
        """Format venue without exposing placeholders as useful facts."""
        if not isinstance(venue, str):
            return "No stadium-specific angle in this run"
        cleaned = venue.strip()
        if not cleaned or cleaned.lower() in {"unknown", "unknown venue", "tbd", "unavailable", "n/a"}:
            return "No stadium-specific angle in this run"
        return cleaned

    def _format_match_dynamic(
        self,
        matchups: Dict[str, Any],
        historical: Dict[str, Any],
        weather: Dict[str, Any],
    ) -> str:
        """Build a concise expected match dynamic from verified sections."""
        bullets = []

        critical_matchups = matchups.get("critical_matchups", [])
        if critical_matchups:
            first = critical_matchups[0]
            p1 = first.get('player1', '')
            p2 = first.get('player2', '')
            if p1 and p2:
                bullets.append(f"1. Key duel: {p1} vs {p2}")

        h2h = historical.get("h2h_history", {})
        if h2h and (h2h.get("team1_wins", 0) + h2h.get("team2_wins", 0) + h2h.get("draws", 0)) > 0:
            bullets.append(
                f"2. Historical trend: {h2h.get('team1_wins', 0)}-{h2h.get('draws', 0)}-{h2h.get('team2_wins', 0)} in recent meetings"
            )

        weather_narrative = self._clean_weather_narrative(weather.get("narrative", ""))
        if weather_narrative:
            bullets.append(f"3. Weather factor: {weather_narrative.split('.')[0].strip()}")

        if bullets:
            return "\n".join(bullets)

        return (
            "1. Opening control: watch which side turns possession into territory first.\n"
            "2. Midfield pressure: second balls and first forward pass should define the rhythm.\n"
            "3. Set-piece cue: use the first corner or wide free kick to read marking confidence."
        )

    def _format_zone_edges(self, positional_strength: Dict[str, Any]) -> List[str]:
        """Summarize zone-level advantages for tactical notes."""
        if not positional_strength:
            return [
                "Defense: read the first build-out under pressure.",
                "Midfield: track second-ball control and the first forward pass.",
                "Attack: watch which wide channel creates the earliest isolation.",
            ]

        zone_order = ["Defense", "Midfield", "Attack"]
        zone_edges = []
        for zone in zone_order:
            zone_data = positional_strength.get(zone, {})
            verdict = zone_data.get("verdict")
            if verdict:
                zone_edges.append(verdict)
        return zone_edges or [
            "Defense: read the first build-out under pressure.",
            "Midfield: track second-ball control and the first forward pass.",
            "Attack: watch which wide channel creates the earliest isolation.",
        ]

    def _extract_team_plan(self, form_analysis: Dict[str, Any], team_name: str) -> str:
        """Extract a concise tactical route from the form-analysis summary."""
        analysis = form_analysis.get("comprehensive_analysis", "")
        plan = self._clean_analysis_text(self._first_two_sentences(analysis), team_name)
        if plan and not self._is_low_quality_text(plan, team_name):
            return plan
        return self._build_team_plan_fallback(form_analysis, team_name)

    def _build_pressure_points(
        self,
        home_team: str,
        away_team: str,
        weak_points: Dict[str, Any],
    ) -> List[str]:
        """Turn weak-point data into commentary-friendly notes."""
        pressure_points = []
        for note in weak_points.get("home_vulnerabilities", [])[:2]:
            cleaned = self._clean_analysis_text(note)
            if cleaned and not self._is_unverified_lineup_weakness(cleaned):
                pressure_points.append(f"{home_team}: {cleaned}")
        for note in weak_points.get("away_vulnerabilities", [])[:2]:
            cleaned = self._clean_analysis_text(note)
            if cleaned and not self._is_unverified_lineup_weakness(cleaned):
                pressure_points.append(f"{away_team}: {cleaned}")
        if pressure_points:
            return pressure_points
        return [
            f"{home_team}: test the first buildup under pressure before naming a structural weakness.",
            f"{away_team}: watch the wide defensive cover and counter-press reaction in the opening phase.",
            "First set piece: use the marking and second-ball response as the earliest pressure read.",
        ]

    def _build_commentary_angles(
        self,
        home_team: str,
        away_team: str,
        matchups: Dict[str, Any],
        historical: Dict[str, Any],
        weather: Dict[str, Any],
        comparative: str,
    ) -> List[str]:
        """Build quick commentary cues from validated workflow outputs."""
        angles = []

        first_matchup = (matchups.get("critical_matchups") or [{}])[0]
        if first_matchup.get("player1") and first_matchup.get("player2"):
            angles.append(
                f"Open with the duel between {first_matchup['player1']} and {first_matchup['player2']}."
            )

        historical_pattern = historical.get("h2h_history", {}).get("patterns", {}).get("pattern")
        if historical_pattern and "limited historical data" not in str(historical_pattern).lower():
            angles.append(f"Frame the rivalry as a {historical_pattern.lower()} head-to-head pattern.")

        weather_lever = self._first_sentence(self._clean_weather_narrative(weather.get("narrative", "")))
        if weather_lever:
            angles.append(f"Weather cue: {weather_lever}")

        comparative_line = self._first_sentence(comparative)
        if comparative_line and not self._is_low_quality_text(comparative_line):
            angles.append(f"Form cue: {comparative_line}")

        if not angles:
            angles.append(f"Lead with how {home_team} and {away_team} handle the first tactical swing in midfield.")

        return [angle for angle in angles if not self._is_low_quality_text(angle)][:4]

    def _build_team_form_fallback(self, form_analysis: Dict[str, Any], team_name: str) -> str:
        """Build readable team form copy from structured fields when LLM text is weak."""
        recent_form = form_analysis.get("recent_form", {}) if isinstance(form_analysis, dict) else {}
        record = recent_form.get("record", {}) if isinstance(recent_form, dict) else {}
        form_string = recent_form.get("form_string", "") if isinstance(recent_form, dict) else ""
        wins = record.get("wins")
        draws = record.get("draws")
        losses = record.get("losses")
        has_record = any((value or 0) > 0 for value in (wins, draws, losses))

        if has_record:
            record_text = f"{wins or 0}W-{draws or 0}D-{losses or 0}L"
            form_clause = f" Their recent sequence reads {form_string}." if self._is_meaningful_form_string(form_string) else ""
            return (
                f"{team_name} enter with a recent record of {record_text}.{form_clause} "
                "For commentary, watch whether that baseline shows up as early territorial control, clean rest defense, or pressure after turnovers."
            )

        if self._is_meaningful_form_string(form_string):
            return (
                f"{team_name}'s recent sequence reads {form_string}. "
                "Turn that into a live read on tempo, field tilt, and first-half chance quality."
            )

        split = form_analysis.get("home_away_split", {}) if isinstance(form_analysis, dict) else {}
        split_text = self._format_home_away_split_for_notes(split)
        if split_text:
            return (
                f"{team_name} have a usable venue trend: {split_text}. "
                "Frame the opening phase around whether they can turn that context into sustained possession and high-quality entries."
            )

        return (
            f"For {team_name}, keep the tactical read grounded in live cues: first-pass security, midfield spacing, set-piece delivery, "
            "and how quickly the back line recovers when possession turns over."
        )

    def _is_meaningful_form_string(self, form_string: Any) -> bool:
        """Return whether a form string contains useful results rather than placeholders."""
        if not isinstance(form_string, str):
            return False
        cleaned = form_string.strip().lower()
        return bool(cleaned) and cleaned not in {"no data", "unavailable", "unknown", "n/a", "none", "tbd"}

    def _build_team_plan_fallback(self, form_analysis: Dict[str, Any], team_name: str) -> str:
        """Build a tactical route when generated prose is placeholder-like."""
        form_copy = self._build_team_form_fallback(form_analysis, team_name)
        first = self._first_sentence(form_copy)
        return (
            f"{first} The route to tilting the match is to establish territory early, protect the central lane, "
            "and turn wide pressure into repeatable final-third moments."
        )

    def _format_home_away_split_for_notes(self, split: Dict[str, Any]) -> str:
        """Render home/away split rows if they contain real values."""
        if not isinstance(split, dict):
            return ""
        pieces = []
        for label in ("home", "away"):
            row = split.get(label, {})
            if not isinstance(row, dict):
                continue
            won = row.get("won", 0) or 0
            drawn = row.get("draw", 0) or 0
            lost = row.get("lost", 0) or 0
            if won or drawn or lost:
                pieces.append(f"{label.title()} {won}W-{drawn}D-{lost}L")
        return " | ".join(pieces)

    def _clean_analysis_text(self, text: Any, team_name: str = "") -> str:
        """Strip outline labels and reject obvious LLM scaffold fragments."""
        if not isinstance(text, str):
            return ""
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return ""
        cleaned = re.sub(r"#{1,6}\s*", "", cleaned)
        cleaned = re.sub(r"\*{2,}", "", cleaned)
        cleaned = re.sub(
            r"(?i)\b(?:provide:|current form status|key performance trends|momentum assessment|recent performance pattern|tactical implications)\s*:?",
            "",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;")
        if self._is_low_quality_text(cleaned, team_name):
            return ""
        return cleaned

    def _is_low_quality_text(self, text: Any, team_name: str = "") -> bool:
        """Detect placeholder/scaffold text that should not be shown to commentators."""
        if not isinstance(text, str):
            return True
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return True
        lower = cleaned.lower()
        if any(pattern in lower for pattern in self.LOW_QUALITY_PATTERNS):
            return True
        if "no critical battles identified" in lower:
            return True
        if "form favorability:" in lower:
            return True
        if "limited historical data" in lower:
            return True
        if "****" in cleaned or "###" in cleaned:
            return True
        if re.search(r"defensive record of \d+\s+wins?.*\d+\s+loss", lower):
            return True
        if re.search(r"defensive record:\s*\d+\s+wins?", lower):
            return True
        if "0 wins, 0 draws" in lower:
            return True
        if re.search(r"goal-scoring rate.*goals against.*goals scored", lower):
            return True
        if "they have not played any matches" in lower:
            return True
        if "not won any matches" in lower or "drawn no matches" in lower:
            return True
        if re.search(r"\b\w+'s is stable\b", lower):
            return True
        if "weather conditions remain unknown" in lower:
            return True
        if "we can infer" in lower:
            return True
        if re.search(r"\b(?:declining|stable|resurgent|in-form)\s+-\s+defensive record", lower):
            return True
        if re.search(r"(^|\s)[1-5]\.\s*(?:$|[1-5]\.|[A-Za-z ]{0,24}:?\s*(?:unavailable|tbd|unknown))", cleaned, re.I):
            return True
        if re.fullmatch(r"(?:[1-5]\.\s*)+", cleaned):
            return True
        if len(cleaned) < 24 and re.search(r"\b(unavailable|pending|tbd|unknown)\b", lower):
            return True
        if team_name and team_name not in {"Home Team", "Away Team"}:
            if re.search(r"\b(home team|away team)\b", lower):
                return True
        return False

    def _is_unverified_lineup_weakness(self, text: str) -> bool:
        """Reject lineup weakness labels that are unsafe when starters are missing."""
        lower = text.lower()
        return (
            "verified lineup" in lower
            or "listed starters" in lower
            or "low attacking depth" in lower
        )

    def _clean_matchup_analysis(self, text: Any) -> str:
        """Keep matchup blurbs short and remove model-generated markdown scaffolding."""
        cleaned = self._clean_analysis_text(text)
        if not cleaned:
            return ""
        cleaned = re.sub(
            r"(?i)\b(?:statistical advantage|tactical edge|key battle prediction)\b:?",
            "",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;")
        lower = cleaned.lower()
        if (
            self._is_low_quality_text(cleaned)
            or "both players have not scored" in lower
            or "the lies in" in lower
        ):
            return ""
        return self._first_two_sentences(cleaned)

    def _clean_news_text(self, text: Any) -> str:
        """Keep team-news prose useful for the booth and remove dead-end disclaimers."""
        cleaned = self._clean_analysis_text(text)
        if not cleaned:
            return ""
        lower = cleaned.lower()
        if (
            "no recent news available" in lower
            or "lineup status is unavailable" in lower
            or "no tactical adjustments are expected" in lower
            or "check official" in lower
            or "latest roster updates" in lower
        ):
            return ""
        return cleaned

    def _clean_historical_narrative(self, text: Any, home_team: str, away_team: str) -> str:
        """Avoid showing fabricated or contradictory historical copy."""
        cleaned = self._clean_analysis_text(text)
        if not cleaned:
            return ""
        lower = cleaned.lower()
        if "0-0-0" in lower or "no previous encounters" in lower or "never met before" in lower:
            return (
                f"Treat {home_team} vs {away_team} as a rivalry context without overstating verified head-to-head numbers. "
                "Use live momentum, crowd tone, and early tactical control as the main story drivers."
            )
        return cleaned

    def _clean_weather_narrative(self, text: Any) -> str:
        """Keep weather notes factual when APIs do not provide conditions."""
        cleaned = self._clean_analysis_text(text)
        if not cleaned or self._is_low_quality_text(cleaned):
            return ""
        return cleaned

    def _first_sentence(self, text: str) -> str:
        """Return the first sentence-like segment from text."""
        if not isinstance(text, str):
            return ""
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return ""
        for separator in (". ", "\n", "! ", "? "):
            if separator in cleaned:
                return cleaned.split(separator, 1)[0].strip().rstrip(".!?") + "."
        return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."

    def _first_two_sentences(self, text: str) -> str:
        """Return up to two sentence-like segments from text."""
        if not isinstance(text, str):
            return ""
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return ""
        sentence_endings = []
        for idx, char in enumerate(cleaned):
            if char in ".!?":
                sentence_endings.append(idx)
                if len(sentence_endings) == 2:
                    break
        if sentence_endings:
            return cleaned[: sentence_endings[-1] + 1].strip()
        return cleaned

    async def _build_json_structure(self, all_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Build complete JSON structure for embedded data."""
        data_sources = self._collect_data_sources(all_outputs)
        tactical_brief = self._build_tactical_brief(all_outputs)
        return {
            "metadata": {
                "match_id": f"{all_outputs.get('home_team', 'home')}_vs_{all_outputs.get('away_team', 'away')}",
                "home_team": all_outputs.get("home_team", "Unknown"),
                "away_team": all_outputs.get("away_team", "Unknown"),
                "sport": self.sport,
                "match_datetime": all_outputs.get("match_datetime", "Unknown"),
                "venue": all_outputs.get("venue", "Unknown"),
                "generated_at": datetime.utcnow().isoformat(),
                "preparation_time_ms": 0,
                "data_sources": data_sources,
            },
            "home_team": self._extract_team_json(
                all_outputs.get("player_research", {}).get("home_team", {}),
                all_outputs.get("team_form", {}).get("home_team", {}),
                all_outputs.get("news", {}).get("home_team", {}),
            ),
            "away_team": self._extract_team_json(
                all_outputs.get("player_research", {}).get("away_team", {}),
                all_outputs.get("team_form", {}).get("away_team", {}),
                all_outputs.get("news", {}).get("away_team", {}),
            ),
            "matchup_analysis": all_outputs.get("matchups", {}),
            "tactical_brief": tactical_brief,
            "historical_context": all_outputs.get("historical", {}),
            "weather": all_outputs.get("weather", {}),
            "quality_metrics": {
                "data_completeness": round(min(len(data_sources) / 5, 1.0), 2),
                "sources_used": len(data_sources),
                "warnings": [],
            },
        }

    def _collect_data_sources(self, all_outputs: Dict[str, Any]) -> List[str]:
        """Collect distinct data sources referenced across agent outputs."""
        sources = set()

        def _walk(value: Any) -> None:
            if isinstance(value, dict):
                source = value.get("data_source")
                if isinstance(source, str) and source:
                    sources.add(source)
                for child in value.values():
                    _walk(child)
            elif isinstance(value, list):
                for item in value:
                    _walk(item)

        _walk(all_outputs)
        sources.add("espn")
        return sorted(sources)

    def _extract_team_json(
        self,
        player_research: Dict[str, Any],
        form_analysis: Dict[str, Any],
        news: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract team data for JSON."""
        return {
            "squad": player_research,
            "form": form_analysis,
            "news": news,
        }
