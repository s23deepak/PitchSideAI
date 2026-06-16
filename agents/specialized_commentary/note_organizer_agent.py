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
from quality.evidence import source_tier_priority

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
        "commentary notes:",
        "maximum confidence level",
        "currently operating at an elite level",
        "elite defensive record",
        "potent goal-scoring rate",
        "opponents must prioritize",
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

                            if name and not self._is_placeholder_player_name(name):
                                source_urls = self._extract_source_urls(player)
                                beat_text = f"{name} ({position}): {profile[:100]}"
                                beats.append(NarrativeBeat(
                                    text=beat_text,
                                    event_tags=[],
                                    players=[name],
                                    section="home_team" if side == "home_team" else "away_team",
                                    source=player.get("data_source", "research"),
                                    source_urls=source_urls,
                                    source_attribution=self._build_source_attribution(
                                        player.get("data_source", "research"),
                                        source_urls,
                                    ),
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
                    if (
                        p1
                        and p2
                        and not self._is_placeholder_player_name(p1)
                        and not self._is_placeholder_player_name(p2)
                        and not self._is_low_quality_text(analysis)
                    ):
                        source_urls = self._extract_source_urls(matchup)
                        beats.append(NarrativeBeat(
                            text=f"Key duel: {p1} vs {p2} — {analysis[:80]}",
                            event_tags=["foul", "free_kick_dangerous"],
                            players=[p1, p2],
                            section="tactical",
                            source="matchup_analysis",
                            source_urls=source_urls,
                            source_attribution=self._build_source_attribution("matchup_analysis", source_urls),
                            confidence=0.7,
                        ))

        # Extract form patterns
        team_form = all_outputs.get("team_form", {})
        for side in ["home_team", "away_team"]:
            form_data = team_form.get(side, {})
            comprehensive = form_data.get("comprehensive_analysis", "")
            if isinstance(comprehensive, str) and comprehensive:
                source_urls = self._extract_source_urls(form_data)
                # Split into sentences and create beats
                sentences = comprehensive.replace("\n", " ").split(". ")
                for sentence in sentences[:5]:
                    if len(sentence.strip()) > 20:
                        beats.append(NarrativeBeat(
                            text=sentence.strip() + ".",
                            event_tags=[],
                            players=[],
                            section=side,
                            source="team_form",
                            source_urls=source_urls,
                            source_attribution=self._build_source_attribution(
                                form_data.get("data_source", "team_form"),
                                source_urls,
                            ),
                            confidence=0.6,
                        ))

        # Extract historical context
        historical = all_outputs.get("historical", {})
        narrative = historical.get("narrative", "")
        if isinstance(narrative, str) and narrative:
            source_urls = self._extract_source_urls(historical)
            sentences = narrative.replace("\n", " ").split(". ")
            for sentence in sentences[:5]:
                if len(sentence.strip()) > 20:
                    beats.append(NarrativeBeat(
                        text=sentence.strip() + ".",
                        event_tags=[],
                        players=[],
                        section="historical",
                        source="historical_context",
                        source_urls=source_urls,
                        source_attribution=self._build_source_attribution(
                            historical.get("data_source", "historical_context"),
                            source_urls,
                        ),
                        confidence=0.5,
                    ))

        # Extract weather impact
        weather = all_outputs.get("weather", {})
        weather_narrative = self._clean_weather_narrative(weather.get("narrative", ""))
        if isinstance(weather_narrative, str) and weather_narrative:
            source_urls = self._extract_source_urls(weather)
            beats.append(NarrativeBeat(
                text=f"Weather impact: {weather_narrative[:100]}",
                event_tags=["foul", "corner"],  # Weather affects set pieces
                players=[],
                section="match_info",
                source="weather_context",
                source_urls=source_urls,
                source_attribution=self._build_source_attribution(
                    weather.get("data_source", "weather_context"),
                    source_urls,
                ),
                confidence=0.6,
            ))

        beats.extend(self._build_canonical_live_trigger_narrative_beats(home_team, away_team))
        return beats

    def _build_canonical_live_trigger_narrative_beats(
        self,
        home_team: str,
        away_team: str,
    ) -> List[NarrativeBeat]:
        """Provide event-safe lookup beats without pretending pre-match facts occurred."""
        trigger_specs = [
            (
                "goal",
                f"Goal trigger: after any confirmed goal, reset the broadcast around score state, scorer role, tactical cause, and how {home_team} and {away_team} must now adjust.",
            ),
            (
                "substitution",
                "Substitution trigger: connect the change to role, shape, energy, and the matchup it is meant to alter.",
            ),
            (
                "yellow_card",
                "Yellow-card trigger: explain how the booking changes duel risk, pressing aggression, and defensive cover.",
            ),
            (
                "red_card",
                "Red-card trigger: immediately reframe territory, rest defense, substitutions, and the side that must manage space.",
            ),
            (
                "corner",
                "Corner trigger: call delivery side, marking scheme, blockers, second-ball shape, and the counter-attack risk.",
            ),
            (
                "free_kick_dangerous",
                "Dangerous free-kick trigger: identify the taker, wall setup, delivery angle, runners, and rebound coverage.",
            ),
        ]
        return [
            NarrativeBeat(
                text=text,
                event_tags=[tag],
                players=[],
                section="live_triggers",
                source="broadcast_rundown",
                confidence=0.8,
            )
            for tag, text in trigger_specs
        ]

    def _extract_source_urls(self, value: Any, limit: int = 5) -> List[str]:
        """Collect source URLs nested under a source object."""
        urls: List[str] = []

        def _walk(item: Any) -> None:
            if len(urls) >= limit:
                return
            if isinstance(item, dict):
                for key in ("source_url", "url", "link"):
                    url = item.get(key)
                    if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in urls:
                        urls.append(url)
                        if len(urls) >= limit:
                            return
                source_urls = item.get("source_urls")
                if isinstance(source_urls, list):
                    for url in source_urls:
                        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in urls:
                            urls.append(url)
                            if len(urls) >= limit:
                                return
                for child in item.values():
                    _walk(child)
            elif isinstance(item, list):
                for child in item:
                    _walk(child)

        _walk(value)
        return urls

    def _build_source_attribution(self, source: Any, source_urls: List[str]) -> List[Dict[str, str]]:
        """Create display-ready attribution objects for generated beats."""
        label = str(source or "research")
        if source_urls:
            return [{"label": label, "url": url} for url in source_urls[:3]]
        return [{"label": label, "url": ""}]

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
        competition = str(all_outputs.get("competition") or "").strip()
        match_datetime = all_outputs.get("match_datetime", "TBD")
        venue = all_outputs.get("venue", "Unknown")
        venue_label = self._format_venue_summary(venue)
        tactical_brief = self._build_tactical_brief(all_outputs)
        quality_report = all_outputs.get("quality_report", {})
        evidence_status = self._format_evidence_status(quality_report)
        friendly_date = self._format_match_datetime(match_datetime)
        news = all_outputs.get("news", {})
        matchups = all_outputs.get("matchups", {})
        historical = all_outputs.get("historical", {})
        weather = all_outputs.get("weather", {})
        team_form = all_outputs.get("team_form", {})
        broadcast_dossier = all_outputs.get("broadcast_dossier", {})
        match_facts = broadcast_dossier.get("match_facts", {}) if isinstance(broadcast_dossier, dict) else {}
        possible_lineups = all_outputs.get("possible_lineups", {})
        plausible_lineups = all_outputs.get("plausible_lineups", {}) or (
            broadcast_dossier.get("lineups", {}).get("plausible", {})
            if isinstance(broadcast_dossier, dict)
            else {}
        )
        home_players = all_outputs.get("player_research", {}).get("home_team", {}).get("players", [])
        away_players = all_outputs.get("player_research", {}).get("away_team", {}).get("players", [])
        h2h_record, h2h_narrative = self._format_historical_frame(historical, home_team, away_team)
        weather_narrative = self._clean_weather_narrative(weather.get("narrative", ""))
        competition_line = f"{competition} | " if competition else ""
        final_stakes = (
            f"This is framed as {competition}; use trophy-stage language, but keep every specific claim tied to verified feed data."
            if competition
            else "Competition/stakes were not provided; keep the booth frame tactical and evidence-led."
        )
        air_ready_rundown = self._format_air_ready_rundown(
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            quality_report=quality_report,
            tactical_brief=tactical_brief,
            news=news,
            historical=historical,
        )
        broadcast_folder_pages = self._format_broadcast_folder_pages(
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            venue=venue_label,
            friendly_date=friendly_date,
            h2h_record=h2h_record,
            tactical_brief=tactical_brief,
            team_form=team_form,
            historical=historical,
            news=news,
            matchups=matchups,
            home_players=home_players,
            away_players=away_players,
            possible_lineups=possible_lineups,
            plausible_lineups=plausible_lineups,
            broadcast_dossier=broadcast_dossier,
        )
        deep_notes = self._format_deep_notes_section(all_outputs.get("deep_notes", {}))

        tactical_summary = self._clean_section_text(tactical_brief.get("summary", ""))

        return f"""# Broadcast Prep: {home_team} vs {away_team}
#### {competition_line}{friendly_date} | {venue_label}

{evidence_status}

{air_ready_rundown}

## Match Frame

- Fixture: **{home_team} vs {away_team}**
- Stage: {competition or 'Unverified in this run'}
- Date/time: {friendly_date}
- Venue: {venue_label}
- Referee/officials: {self._format_officials_summary(match_facts.get('officials', {}))}
- Broadcast frame: {final_stakes}
- Lineups: see Broadcast Folder Page 1; treat plausible and source-predicted XIs as unconfirmed until team sheets arrive.

## Narrative Spine

- Opening frame: {final_stakes}
- First read: confirm whether the match settles into controlled buildup, fast transition, or set-piece pressure.
- Evidence posture: use confirmed team sheets and live pictures before making hard claims about form, injuries, or tactical intent.

## Tactical Dossier

{tactical_summary}

### Zone Watch

{self._format_bullets(tactical_brief.get('zone_edges', []))}

### Key Player Battles

{self._format_matchups(matchups.get('critical_matchups', []))}

### Set-Piece Watch

- First corner: identify marking type, delivery side, primary runner, and second-ball reaction.
- First wide free kick: call whether the defensive line holds, drops, or leaves the back-post channel open.
- First attacking throw-in: watch whether either side can lock the ball in or force a clean escape.

## Form, History And Conditions

### Form Cards

{self._format_bullets([
    self._folder_form_line(team_form.get('home_team', {}), home_team),
    self._folder_form_line(team_form.get('away_team', {}), away_team),
])}

### Historical Frame

H2H Record: **{h2h_record}**

{h2h_narrative}

### Weather / Surface

{weather_narrative or 'Weather unavailable from accepted evidence.'}

## Team News Caveats

### {home_team}

{self._format_news(news.get('home_team', {}), team_name=home_team, side_label='home')}

### {away_team}

{self._format_news(news.get('away_team', {}), team_name=away_team, side_label='away')}

{broadcast_folder_pages}

## Pronunciation

- Confirm names from official broadcast/team media before adding phonetic spellings.
- Avoid guessing pronunciation for players without an accepted source.

## Live Trigger Lines

{self._format_bullets(self._build_live_trigger_beats(home_team, away_team, tactical_brief, home_players, away_players))}

## Halftime And Postgame Angles

- Halftime: compare the intended tactical routes with territory, chance quality, and the first set-piece pattern.
- If {home_team} lead: ask whether control came from sustained pressure or isolated transition moments.
- If {away_team} lead: ask whether their outlet and counter-press gave them repeatable relief.
- Postgame: anchor the first question in the clearest verified swing, not in unverified pre-match assumptions.

{deep_notes}
"""

    def _format_match_datetime(self, match_datetime: Any) -> str:
        if not isinstance(match_datetime, str) or not match_datetime.strip():
            return "Kickoff time unverified in this run"
        try:
            dt_obj = datetime.fromisoformat(match_datetime.replace("Z", "+00:00"))
            friendly_date = dt_obj.strftime("%A, %B %d, %Y at %H:%M")
            if dt_obj.tzinfo is not None:
                offset = dt_obj.strftime("%z")
                return f"{friendly_date} UTC{offset[:3]}:{offset[3:]}" if offset else friendly_date
            return friendly_date
        except Exception:
            return match_datetime

    def _team_form_for_broadcast(self, form_analysis: Dict[str, Any], team_name: str) -> str:
        form_text = self._clean_analysis_text(form_analysis.get("comprehensive_analysis", ""), team_name)
        if (
            not form_text
            or self._is_low_quality_text(form_text, team_name)
            or self._looks_like_numbered_homework(form_text)
        ):
            form_text = self._build_team_form_fallback(form_analysis, team_name)
        return form_text

    def _format_historical_frame(
        self,
        historical: Dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> Tuple[str, str]:
        h2h = historical.get("h2h_history", {}) if isinstance(historical, dict) else {}
        h2h_available = h2h and h2h.get("status") != "unavailable" and (
            (h2h.get("team1_wins") or 0) + (h2h.get("team2_wins") or 0) + (h2h.get("draws") or 0)
        ) > 0
        source_backed = h2h.get("status") == "source_available" or bool(h2h.get("source_urls"))
        record = (
            f"{h2h.get('team1_wins', 0)}-{h2h.get('draws', 0)}-{h2h.get('team2_wins', 0)}"
            if h2h_available
            else "Trusted H2H source available; exact record not extracted"
            if source_backed
            else "Unavailable from trusted sources in this run"
        )
        narrative = self._clean_historical_narrative(historical.get("narrative", ""), home_team, away_team)
        if not narrative:
            narrative = "Historical H2H unavailable from accepted evidence."
        return record, narrative

    def _build_live_trigger_beats(
        self,
        home_team: str,
        away_team: str,
        tactical_brief: Dict[str, Any],
        home_players: List[Dict[str, Any]],
        away_players: List[Dict[str, Any]],
    ) -> List[str]:
        beats = [
            f"First 10 minutes: identify whether {home_team} can turn possession into territory.",
            f"First away transition: note whether {away_team}'s outlet receives support or becomes isolated.",
            "First corner or wide free kick: call marking type, second-ball reaction, and delivery quality.",
        ]
        first_home_player = next(
            (player for player in home_players if not self._is_placeholder_player_name(player.get("name"))),
            None,
        )
        first_away_player = next(
            (player for player in away_players if not self._is_placeholder_player_name(player.get("name"))),
            None,
        )
        first_matchup = tactical_brief.get("first_matchup") if isinstance(tactical_brief, dict) else {}
        if isinstance(first_matchup, dict) and first_matchup.get("player1") and first_matchup.get("player2"):
            beats.append(
                f"First named duel: if {first_matchup['player1']} and {first_matchup['player2']} meet in the same channel, call who gets help first."
            )
        elif first_home_player and first_away_player:
            first_home = first_home_player.get("name")
            first_away = first_away_player.get("name")
            if first_home and first_away:
                beats.append(f"First named duel: if {first_home} and {first_away} meet in the same channel, call who gets help first.")
        for point in tactical_brief.get("pressure_points", [])[:3]:
            beats.append(point)
        return beats[:8]

    def _format_deep_notes_section(self, deep_notes: Dict[str, Any]) -> str:
        """Format optional DeepAgents synthesis guidance."""
        if not isinstance(deep_notes, dict) or not deep_notes.get("enabled"):
            return ""

        def _items(key: str) -> str:
            value = deep_notes.get(key, [])
            if isinstance(value, str):
                return f"- {value}"
            if isinstance(value, list):
                return "\n".join(f"- {item}" for item in value[:8] if item)
            return ""

        sections = []
        for key, title in (
            ("storylines", "Deep Storyline Guidance"),
            ("tactical_questions", "Deep Tactical Questions"),
            ("precision_checks", "Precision Checks"),
            ("commentary_directives", "Commentary Directives"),
        ):
            body = _items(key)
            if body:
                sections.append(f"### {title}\n\n{body}")
        if not sections:
            raw = deep_notes.get("raw")
            if raw:
                sections.append(f"### Deep Research Brief\n\n{raw}")
        return "\n\n---\n\n## DEEP RESEARCH SYNTHESIS\n\n" + "\n\n".join(sections) if sections else ""

    def _organize_lineups_section(
        self,
        home_squad: Dict[str, Any],
        away_squad: Dict[str, Any],
        match_datetime: str,
        venue: str,
        weather: Dict[str, Any],
        news: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Organize PAGE 1 - Lineups & Match Info."""
        home_team = home_squad.get("team_name", "Home")
        away_team = away_squad.get("team_name", "Away")
        temp = weather.get("current_conditions", {}).get("temperature_c")
        conditions = weather.get("current_conditions", {}).get("conditions") or ""
        wind = weather.get("current_conditions", {}).get("wind_kmh")
        home_players = home_squad.get("players", [])[:11]
        away_players = away_squad.get("players", [])[:11]
        news = news or {}
        home_lineup_status = (news.get("home_team", {}) or {}).get("lineup_status", {}).get("status")
        away_lineup_status = (news.get("away_team", {}) or {}).get("lineup_status", {}).get("status")
        confirmed_lineups = home_lineup_status == "confirmed" and away_lineup_status == "confirmed"

        lineup_rows = self._format_lineup_rows(home_players, away_players)
        lineup_block = (
            f"""**Confirmed Starters From Accepted Evidence**

| {home_team} | Pos | {away_team} |
|-----------|-----|-----------|
{lineup_rows}

**Lineup Note**: Use this as the working XI context for the booth; if the feed shows a late change, pivot the same cues toward the replacement role."""
            if lineup_rows and confirmed_lineups
            else f"""**Opening Shape Cues**
- {home_team}: watch the first receiver under pressure and the fullback height in buildup.
- {away_team}: track whether the press protects the middle or invites wide circulation.
- First dead ball: use the marking scheme as the quickest read on defensive organisation."""
        )

        try:
            dt_obj = datetime.fromisoformat(match_datetime.replace("Z", "+00:00"))
            friendly_date = dt_obj.strftime("%A, %B %d, %Y at %H:%M")
            if dt_obj.tzinfo is not None:
                offset = dt_obj.strftime("%z")
                friendly_date = f"{friendly_date} UTC{offset[:3]}:{offset[3:]}" if offset else friendly_date
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

        h2h_available = h2h and h2h.get("status") != "unavailable" and (
            (h2h.get("team1_wins") or 0) + (h2h.get("team2_wins") or 0) + (h2h.get("draws") or 0)
        ) > 0
        if h2h_available:
            h2h_record = f"{h2h.get('team1_wins', 0)}-{h2h.get('draws', 0)}-{h2h.get('team2_wins', 0)}"
        else:
            h2h_record = "Unavailable from trusted sources in this run"

        # Build narrative with meaningful fallback
        if not narrative and h2h_available:
            narrative = (
                f"Frame {home_team} vs {away_team} through the opening tone: which side settles first, "
                "which midfield wins second balls, and whether the wide channels produce early pressure."
            )
        elif not narrative:
            narrative = "No verified head-to-head narrative was accepted in this run; anchor this section in live tactical cues."
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

{weather_narrative or 'Weather unavailable from accepted evidence.'}

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
        if self._is_unsafe_tactical_summary(summary):
            summary = ""
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
            "first_matchup": self._first_valid_matchup(matchups.get("critical_matchups", [])),
            "commentary_angles": self._build_commentary_angles(
                home_team,
                away_team,
                matchups,
                historical,
                weather,
                comparative,
            ),
        }

    def _first_valid_matchup(self, matchups: List[Dict[str, Any]]) -> Dict[str, Any]:
        for matchup in matchups or []:
            p1 = matchup.get("player1")
            p2 = matchup.get("player2")
            if p1 and p2 and not self._is_placeholder_player_name(p1) and not self._is_placeholder_player_name(p2):
                return matchup
        return {}

    def _is_unsafe_tactical_summary(self, summary: str) -> bool:
        lower = (summary or "").lower()
        return (
            "weak points" in lower
            or "vulnerabilities" in lower
            or "based on the identification" in lower
            or "based on the limited information" in lower
            or "in your prompt" in lower
            or "i cannot" in lower
            or "i can't" in lower
            or "unable to provide" in lower
            or "cannot generate" in lower
            or "five critical battles" in lower
            or "critical matchups" in lower
            or "tactical analysis:" in lower
        )

    def _clean_section_text(self, text: Any) -> str:
        cleaned = self._clean_analysis_text(text)
        cleaned = re.sub(r"(?m)^#{1,6}\s*", "", cleaned)
        cleaned = re.sub(r"(?i)\btactical analysis:\s*", "", cleaned).strip()
        return cleaned

    def _format_evidence_status(self, quality_report: Dict[str, Any]) -> str:
        """Expose degraded sections without turning weak evidence into claims."""
        if not isinstance(quality_report, dict) or not quality_report.get("strict_mode"):
            return ""
        degraded = quality_report.get("degraded_sections", []) or []
        unavailable = quality_report.get("unavailable_facts", []) or []
        if not degraded and not unavailable:
            return "## EVIDENCE STATUS\n\n- Strict evidence mode: all accepted claims passed source validation."
        degraded_text = ", ".join(str(item) for item in degraded[:6]) or "none"
        unavailable_lines = "\n".join(f"- {item}" for item in unavailable[:6]) or "- None"
        return f"""## EVIDENCE STATUS

- Strict evidence mode: degraded sections are marked instead of filled with weak claims.
- Degraded sections: {degraded_text}

Unavailable or uncertain facts:
{unavailable_lines}"""

    def _format_air_ready_rundown(
        self,
        *,
        home_team: str,
        away_team: str,
        competition: str,
        quality_report: Dict[str, Any],
        tactical_brief: Dict[str, Any],
        news: Dict[str, Any],
        historical: Dict[str, Any],
    ) -> str:
        accepted = quality_report.get("accepted_evidence", []) if isinstance(quality_report, dict) else []
        ready_facts = self._source_backed_facts(accepted)
        blocked_claims = quality_report.get("unavailable_facts", []) if isinstance(quality_report, dict) else []
        opener = (
            f"{home_team} and {away_team} meet with {competition} stakes; "
            "the first job is to verify whether the occasion settles into control or becomes a transition game."
            if competition
            else f"{home_team} and {away_team} meet with the live pictures carrying the story; start with territory, tempo, and pressure."
        )
        setup = (
            f"Ready to say: {ready_facts[0]}"
            if ready_facts
            else "Ready to say: fixture frame is available, but detailed claims should wait for confirmed sources and the live feed."
        )
        watch_cards = [
            f"Watch: {home_team}'s first buildup under pressure. Say: if they play through the first line twice, the tone becomes control rather than survival. Prove: two clean exits into midfield.",
            f"Watch: {away_team}'s first transition outlet. Say: the counter only becomes a pattern if the runner receives support. Prove: second runner arrives before the recycle.",
        ]
        if tactical_brief.get("first_matchup"):
            matchup = tactical_brief["first_matchup"]
            watch_cards.append(
                f"Watch: {matchup.get('player1')} vs {matchup.get('player2')}. Say: the duel matters only once it decides territory. Prove: a tackle, foul, forced pass, or carried escape."
            )
        wait_items = blocked_claims[:4] or ["confirmed lineups", "late injury updates"]

        return f"""## Air-Ready Rundown

### Ready To Say

- 15-second opener: {opener}
- 45-second setup: {setup}
{self._format_bullets(ready_facts[1:4])}

### Opening Lines Bank

{self._format_bullets(self._build_opening_lines_bank(home_team, away_team, competition))}

### Watch, Say, Prove

{self._format_bullets(watch_cards)}

### Wait For Confirmation

{self._format_bullets([f"Do not state {item} until an official, structured, or trusted-media source confirms it." for item in wait_items])}"""

    def _source_backed_facts(self, accepted: Any) -> List[str]:
        facts = []
        seen = set()
        if isinstance(accepted, list):
            sorted_items = sorted(
                (item for item in accepted if isinstance(item, dict)),
                key=lambda item: source_tier_priority(str(item.get("source_tier") or "")),
            )
            for item in sorted_items:
                claim = self._clean_analysis_text(item.get("claim", "")).strip()
                tier = item.get("source_tier") or "source"
                source = item.get("source_name") or item.get("url") or "source"
                key = re.sub(r"\W+", "", claim.lower())
                if claim and key not in seen and not self._is_low_quality_text(claim) and not self._is_unrelated_storyline(claim):
                    facts.append(f"{claim} ({tier}: {source})")
                    seen.add(key)
        return facts[:5]

    def _build_opening_lines_bank(self, home_team: str, away_team: str, competition: str) -> List[str]:
        stage = competition or "the night"
        return [
            f"{home_team} and {away_team} bring the occasion; {stage} will decide which story survives contact with the first whistle.",
            f"For {home_team}: start with territory, courage on the ball, and the players trusted to turn preparation into control.",
            f"For {away_team}: watch the first release pass, the first counter-press, and whether speed becomes a pattern rather than a moment.",
        ]

    def _source_backed_storylines(self, historical: Dict[str, Any], news: Dict[str, Any]) -> List[str]:
        storylines = []
        seen = set()

        def add_storyline(title: Any, label: str) -> None:
            cleaned_title = self._clean_analysis_text(title).strip()
            key = re.sub(r"\W+", "", cleaned_title.lower())
            if not cleaned_title or key in seen or self._is_unrelated_storyline(cleaned_title):
                return
            seen.add(key)
            storylines.append(f"Ready to say: {cleaned_title} ({label}).")

        historical_storylines = historical.get("storylines", []) if isinstance(historical, dict) else []
        for story in historical_storylines:
            label = story.get("source_policy_label") or story.get("source_tier") or story.get("source") or "accepted source"
            add_storyline(story.get("title", ""), label)
        for side in ("home_team", "away_team"):
            team_news = news.get(side, {}) if isinstance(news, dict) else {}
            for item in team_news.get("news_items", [])[:2]:
                label = item.get("source_policy_label") or item.get("source_tier") or item.get("source") or "accepted source"
                add_storyline(item.get("title", ""), label)
        if storylines:
            return storylines[:5]
        return ["No source-backed storyline is strong enough yet; sell the opening through live tempo, territory, and confirmed team-sheet facts."]

    def _is_unrelated_storyline(self, text: str) -> bool:
        lower = (text or "").lower()
        return any(marker in lower for marker in (
            "kimmich",
            "germany don't have",
            "germany dont have",
            "teenage prodigy bouaddi",
            "england players shelter",
        ))

    def _format_broadcast_folder_pages(
        self,
        *,
        home_team: str,
        away_team: str,
        competition: str,
        venue: str,
        friendly_date: str,
        h2h_record: str,
        tactical_brief: Dict[str, Any],
        team_form: Dict[str, Any],
        historical: Dict[str, Any],
        news: Dict[str, Any],
        matchups: Dict[str, Any],
        home_players: List[Dict[str, Any]],
        away_players: List[Dict[str, Any]],
        possible_lineups: Dict[str, Any],
        plausible_lineups: Dict[str, Any],
        broadcast_dossier: Dict[str, Any],
    ) -> str:
        """Build A4-folder style quick-reference pages for live commentary."""
        player_cards = broadcast_dossier.get("player_cards", {}) if isinstance(broadcast_dossier, dict) else {}
        home_rows = self._format_player_profile_grid(
            player_cards.get("home_team") or home_players,
            home_team,
        )
        away_rows = self._format_player_profile_grid(
            player_cards.get("away_team") or away_players,
            away_team,
        )
        match_facts = broadcast_dossier.get("match_facts", {}) if isinstance(broadcast_dossier, dict) else {}
        club_context = broadcast_dossier.get("club_context", {}) if isinstance(broadcast_dossier, dict) else {}
        statistics_context = broadcast_dossier.get("statistics_context", {}) if isinstance(broadcast_dossier, dict) else {}
        tactical_pages = self._format_folder_tactical_pages(
            home_team=home_team,
            away_team=away_team,
            h2h_record=h2h_record,
            tactical_brief=tactical_brief,
            team_form=team_form,
            matchups=matchups,
            historical=historical,
        )
        trivia = self._format_folder_trivia(historical, news)
        return f"""## Broadcast Folder Pages

### Page 1: Team Sheets And Officials

Broadcast page role: **Match Overview & Lineups**

- Match: {home_team} vs {away_team}
- Stage: {competition or 'Unverified in this run'}
- Kickoff: {friendly_date}
- Venue: {venue}
- Officials: {self._format_officials_summary(match_facts.get('officials', {}))}
- Confirmed XIs: {self._format_confirmed_lineup_status(broadcast_dossier)}
- Substitutes: add from the confirmed team sheet, then mark tactical alternatives by role.
- Pencil rule: keep this page editable until the official team sheet lands.

#### Plausible XIs - Recent-Start Model

{self._format_plausible_lineups(plausible_lineups, home_team, away_team)}

#### Source-Predicted XIs - Not Confirmed

{self._format_source_lineup_delta(possible_lineups, plausible_lineups, home_team, away_team)}

### Pages 2-3: Player Cards

#### Page 2: {home_team} Deep-Dive

{home_rows}

#### Page 3: {away_team} Deep-Dive

{away_rows}

### Page 4: Club Context & Staff

{self._format_club_context_pages(home_team, away_team, club_context)}

### Pages 5-6: Tactical And Historical Context

Broadcast page role: **Pages 5-6: Statistics & Historical Context**

{tactical_pages}

{self._format_statistics_context(statistics_context)}

### Archival Trivia

{trivia}"""

    def _format_player_profile_grid(self, players: List[Dict[str, Any]], team_name: str) -> str:
        rows = []
        seen_names: set[str] = set()
        for player in players or []:
            name = player.get("name", "")
            if self._is_placeholder_player_name(name):
                continue
            canonical = self._canonical_player_name(name)
            if canonical in seen_names:
                continue
            seen_names.add(canonical)
            number = player.get("squad_number") or player.get("shirt_number") or "tbc"
            position = self._clean_player_field(player.get("position"), fallback="fixture-evidence role")
            age = self._clean_player_field(player.get("age"), fallback="")
            nationality = self._clean_player_field(player.get("nationality"), fallback=team_name)
            stats_line = player.get("stats_line")
            if not stats_line:
                stats = player.get("stats", {}) if isinstance(player.get("stats"), dict) else {}
                stats_line = self._format_compact_stats(stats)
            if stats_line == "season stats not verified":
                stats_line = "season stats tbc"
            cue = self._first_sentence(str(player.get("cue") or player.get("profile") or player.get("evidence") or "")).strip()
            if not cue or self._is_low_quality_text(cue) or self._is_bad_player_cue(cue):
                cue = "Use only confirmed live role, touch map, and matchup evidence."
            bio_bits = " | ".join(str(bit) for bit in (position, age, nationality, stats_line) if bit)
            rows.append(f"No. {number} | {name} | {bio_bits} | Cue: {cue}")
            if len(rows) >= 25:
                break
        if rows:
            return self._format_bullets(rows)
        return f"- {team_name}: no player grid promoted yet; fill from confirmed team sheet and verified squad notes."

    def _clean_player_field(self, value: Any, fallback: str = "") -> str:
        text = str(value or "").strip()
        if not text or text.lower() in {"unknown", "n/a", "none", "null"}:
            return fallback
        return text

    def _canonical_player_name(self, name: Any) -> str:
        text = re.sub(r"\s+", " ", str(name or "").strip().lower())
        text = re.sub(r"^mo\s+salah$", "mohamed salah", text)
        return text

    def _is_bad_player_cue(self, cue: str) -> bool:
        lower = (cue or "").lower()
        return (
            "[...]" in cue
            or "..." in cue
            or " i know " in f" {lower} "
            or "as i coached" in lower
            or " in your prompt" in lower
            or lower.count('"') == 1
        )

    def _format_officials_summary(self, officials: Any) -> str:
        if not isinstance(officials, dict) or not officials:
            return "officials not confirmed in accepted evidence"
        labels = []
        for key, label in (
            ("referee", "Referee"),
            ("var", "VAR"),
            ("assistant_referees", "Assistants"),
            ("fourth_official", "Fourth official"),
        ):
            value = officials.get(key)
            if value:
                labels.append(f"{label}: {value}")
        for key, value in officials.items():
            if key not in {"referee", "var", "assistant_referees", "fourth_official"} and value:
                labels.append(f"{str(key).replace('_', ' ').title()}: {value}")
        return "; ".join(labels) if labels else "officials not promoted from accepted evidence"

    def _format_confirmed_lineup_status(self, broadcast_dossier: Dict[str, Any]) -> str:
        lineups = broadcast_dossier.get("lineups", {}) if isinstance(broadcast_dossier, dict) else {}
        confirmed = lineups.get("confirmed", {}) if isinstance(lineups, dict) else {}
        if isinstance(confirmed, dict) and confirmed:
            return "confirmed team-sheet data is available in the dossier; check late changes before air."
        return "leave editable until official team sheets arrive; do not promote researched squads as starters."

    def _format_club_context_pages(
        self,
        home_team: str,
        away_team: str,
        club_context: Dict[str, Any],
    ) -> str:
        rows = []
        for side, team_name in (("home_team", home_team), ("away_team", away_team)):
            context = club_context.get(side, {}) if isinstance(club_context, dict) else {}
            manager = context.get("manager") or "manager not verified in accepted feed"
            staff = context.get("staff") or []
            upcoming = context.get("upcoming_fixtures") or []
            staff_line = ", ".join(str(item) for item in staff[:4]) if isinstance(staff, list) and staff else "staff not verified in accepted feed"
            fixture_line = ", ".join(str(item) for item in upcoming[:4]) if isinstance(upcoming, list) and upcoming else "upcoming fixtures not promoted in this run"
            rows.extend([
                f"{team_name} manager: {manager}",
                f"{team_name} staff box: {staff_line}",
                f"{team_name} next fixtures: {fixture_line}",
            ])
        return self._format_bullets(rows)

    def _format_statistics_context(self, statistics_context: Dict[str, Any]) -> str:
        if not isinstance(statistics_context, dict):
            return ""
        lines = []
        seen = set()
        def add_line(line: str) -> None:
            key = re.sub(r"\W+", "", line.lower())
            if not key or key in seen or self._is_unrelated_storyline(line):
                return
            seen.add(key)
            lines.append(line)
        for key in ("home_form", "away_form"):
            if statistics_context.get(key):
                add_line(str(statistics_context[key]))
        for duel in statistics_context.get("key_duels", [])[:6]:
            add_line(f"Key duel index: {duel}")
        for storyline in statistics_context.get("storylines", [])[:6]:
            add_line(f"Historical/storyline card: {storyline}")
        if not lines:
            return ""
        return "#### Statistics & Story Cards\n\n" + self._format_bullets(lines)

    def _format_compact_stats(self, stats: Dict[str, Any]) -> str:
        if not isinstance(stats, dict) or not stats:
            return "season stats not verified"
        parts = []
        for key, label in (("appearances", "apps"), ("goals", "goals"), ("assists", "assists")):
            value = stats.get(key)
            if value is not None and value != "":
                parts.append(f"{value} {label}")
        return ", ".join(parts) if parts else "season stats not verified"

    def _format_possible_lineups(
        self,
        possible_lineups: Dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> str:
        if not isinstance(possible_lineups, dict) or not possible_lineups:
            return "- Possible XIs not promoted in this run; wait for an official or trusted predicted-lineup source."

        lines = []
        source = possible_lineups.get("source") or possible_lineups.get("source_name") or "predicted-lineup source"
        source_urls = possible_lineups.get("source_urls")
        if not isinstance(source_urls, list):
            source_url = possible_lineups.get("source_url") or possible_lineups.get("url") or ""
            source_urls = [source_url] if source_url else []

        for side, team_name in (("home_team", home_team), ("away_team", away_team)):
            side_data = possible_lineups.get(side, {})
            players = side_data.get("players") if isinstance(side_data, dict) else None
            if not isinstance(players, list) or not players:
                continue
            names = [
                str(player).strip()
                for player in players
                if isinstance(player, str) and player.strip() and not self._is_placeholder_player_name(player)
            ]
            if names:
                lines.append(f"{team_name} possible XI ({source}, unconfirmed): {', '.join(names)}.")
            outs = side_data.get("out") if isinstance(side_data, dict) else None
            doubtful = side_data.get("doubtful") if isinstance(side_data, dict) else None
            if isinstance(outs, list) and outs:
                lines.append(f"{team_name} listed out: {', '.join(str(item) for item in outs)}.")
            if isinstance(doubtful, list) and doubtful:
                lines.append(f"{team_name} listed doubtful: {', '.join(str(item) for item in doubtful)}.")

        if not lines:
            return "- Possible XIs not promoted in this run; wait for an official or trusted predicted-lineup source."
        trusted_urls = [str(url) for url in source_urls if isinstance(url, str) and url.startswith("http")]
        if trusted_urls:
            lines.append(f"Sources: {'; '.join(trusted_urls[:4])}")
        return self._format_bullets(lines)

    def _format_source_lineup_delta(
        self,
        possible_lineups: Dict[str, Any],
        plausible_lineups: Dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> str:
        if not isinstance(possible_lineups, dict) or not possible_lineups:
            return "- No source-predicted XI promoted separately in this run."

        source = possible_lineups.get("source") or possible_lineups.get("source_name") or "predicted-lineup source"
        source_urls = possible_lineups.get("source_urls")
        if not isinstance(source_urls, list):
            source_url = possible_lineups.get("source_url") or possible_lineups.get("url") or ""
            source_urls = [source_url] if source_url else []
        lines = []
        for side, team_name in (("home_team", home_team), ("away_team", away_team)):
            source_names = self._lineup_names(possible_lineups.get(side, {}))
            model_names = self._lineup_names(plausible_lineups.get(side, {})) if isinstance(plausible_lineups, dict) else []
            if source_names and model_names and source_names == model_names:
                lines.append(f"{team_name}: source-predicted XI matches the plausible XI above ({source}, unconfirmed).")
            elif source_names:
                lines.append(f"{team_name} source-predicted XI ({source}, unconfirmed): {', '.join(source_names)}.")
            side_data = possible_lineups.get(side, {})
            outs = side_data.get("out") if isinstance(side_data, dict) else None
            doubtful = side_data.get("doubtful") if isinstance(side_data, dict) else None
            if isinstance(outs, list) and outs and not self._only_none_values(outs):
                lines.append(f"{team_name} listed out: {', '.join(str(item) for item in outs)}.")
            if isinstance(doubtful, list) and doubtful and not self._only_none_values(doubtful):
                lines.append(f"{team_name} listed doubtful: {', '.join(str(item) for item in doubtful)}.")

        trusted_urls = [str(url) for url in source_urls if isinstance(url, str) and url.startswith("http")]
        if trusted_urls:
            lines.append(f"Sources: {'; '.join(trusted_urls[:4])}")
        return self._format_bullets(lines) or "- No source-predicted XI promoted separately in this run."

    def _lineup_names(self, lineup: Any) -> List[str]:
        if not isinstance(lineup, dict):
            return []
        structured_players = lineup.get("lineup")
        players = structured_players if isinstance(structured_players, list) and structured_players else lineup.get("players")
        if not isinstance(players, list):
            return []
        names = []
        for player in players:
            if isinstance(player, dict):
                name = str(player.get("name") or "").strip()
            elif isinstance(player, str):
                name = player.strip()
            else:
                continue
            if name and not self._is_placeholder_player_name(name):
                names.append(name)
        return names

    def _only_none_values(self, values: List[Any]) -> bool:
        return all(str(value).strip().lower() in {"none", "n/a", "no", "nil"} for value in values)

    def _format_plausible_lineups(
        self,
        plausible_lineups: Dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> str:
        if not isinstance(plausible_lineups, dict) or not plausible_lineups:
            return "- Plausible XI model not run in this sample; use recent starts, minutes, role continuity, and availability before air."

        lines = []
        basis = plausible_lineups.get("basis") or "recent starts, minutes, role continuity, and availability"
        confidence = plausible_lineups.get("confidence") or "medium"
        for side, team_name in (("home_team", home_team), ("away_team", away_team)):
            side_data = plausible_lineups.get(side, {})
            players = side_data.get("players") if isinstance(side_data, dict) else None
            if not isinstance(players, list) or not players:
                continue
            names = [
                str(player).strip()
                for player in players
                if isinstance(player, str) and player.strip() and not self._is_placeholder_player_name(player)
            ]
            if not names:
                continue
            formation = side_data.get("formation") if isinstance(side_data, dict) else ""
            formation_part = f", {formation}" if formation else ""
            roles = side_data.get("roles") if isinstance(side_data, dict) else {}
            if isinstance(roles, dict) and roles and not self._lineup_roles_usable(roles):
                lines.append(
                    f"{team_name} plausible XI not promoted: researched squad order is not role-balanced enough; wait for a confirmed or trusted predicted XI."
                )
                continue
            role_line = self._format_lineup_role_groups(roles) if isinstance(roles, dict) else ""
            player_line = role_line or ", ".join(names)
            lines.append(
                f"{team_name} plausible XI ({basis}{formation_part}; confidence {confidence}): {player_line}."
            )
            caveat = side_data.get("caveat") if isinstance(side_data, dict) else ""
            if isinstance(caveat, str) and caveat.strip():
                lines.append(f"{team_name} caveat: {caveat.strip()}")

        if lines:
            return self._format_bullets(lines)
        return "- Plausible XI model not run in this sample; use recent starts, minutes, role continuity, and availability before air."

    def _lineup_roles_usable(self, roles: Dict[str, Any]) -> bool:
        goalkeepers = self._unique_player_names(roles.get("goalkeeper"))
        defenders = self._unique_player_names(roles.get("defenders"))
        midfielders = self._unique_player_names(roles.get("midfielders"))
        forwards = self._unique_player_names(roles.get("forwards"))
        total = len(goalkeepers) + len(defenders) + len(midfielders) + len(forwards)
        return len(goalkeepers) == 1 and len(defenders) >= 3 and len(midfielders) >= 2 and len(forwards) >= 1 and 10 <= total <= 11

    def _unique_player_names(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        names = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            name = value.strip()
            canonical = self._canonical_player_name(name)
            if not name or self._is_placeholder_player_name(name) or canonical in seen:
                continue
            seen.add(canonical)
            names.append(name)
        return names

    def _format_lineup_role_groups(self, roles: Dict[str, Any]) -> str:
        labels = (
            ("goalkeeper", "GK"),
            ("defenders", "DEF"),
            ("midfielders", "MID"),
            ("forwards", "FWD"),
        )
        parts = []
        for key, label in labels:
            values = roles.get(key)
            names = self._unique_player_names(values)
            if names:
                parts.append(f"{label}: {', '.join(names)}")
        return "; ".join(parts)

    def _format_folder_tactical_pages(
        self,
        *,
        home_team: str,
        away_team: str,
        h2h_record: str,
        tactical_brief: Dict[str, Any],
        team_form: Dict[str, Any],
        matchups: Dict[str, Any],
        historical: Dict[str, Any],
    ) -> str:
        home_form = self._folder_form_line(team_form.get("home_team", {}), home_team)
        away_form = self._folder_form_line(team_form.get("away_team", {}), away_team)
        matchup_names = []
        for matchup in (matchups.get("critical_matchups") or [])[:4]:
            p1 = matchup.get("player1")
            p2 = matchup.get("player2")
            if p1 and p2 and not self._is_placeholder_player_name(p1) and not self._is_placeholder_player_name(p2):
                matchup_names.append(f"{p1} vs {p2}")
        matchup_index = "; ".join(matchup_names) if matchup_names else "Map the first repeated channel battle from live pictures."
        historical_line = self._first_sentence(historical.get("narrative", "")) if isinstance(historical, dict) else ""
        if not historical_line:
            historical_line = "No verified historical narrative promoted beyond the H2H record."
        items = [
            "Tactical spine: use Tactical Dossier above for the full read.",
            f"Form cards: {home_form}; {away_form}",
            f"H2H: {h2h_record}",
            f"Historical cue: {historical_line}",
            f"Matchup index: {matchup_index}",
            "Team-shape box: confirm formations at kickoff, then update if the press or buildup changes.",
        ]
        return self._format_bullets(items)

    def _folder_form_line(self, form_data: Dict[str, Any], team_name: str) -> str:
        recent = form_data.get("recent_form", {}) if isinstance(form_data, dict) else {}
        record = recent.get("record", {}) if isinstance(recent, dict) else {}
        record_parts = []
        for key, label in (("wins", "W"), ("draws", "D"), ("losses", "L")):
            value = record.get(key)
            if value is not None:
                record_parts.append(f"{value}{label}")
        form_string = recent.get("form_string") if isinstance(recent, dict) else ""
        record_text = "-".join(record_parts) if record_parts else (form_string or "form record unavailable")
        return f"{team_name} form card: {record_text}"

    def _format_folder_trivia(self, historical: Dict[str, Any], news: Dict[str, Any]) -> str:
        trivia = []
        for item in self._source_backed_storylines(historical, news):
            cleaned = item.replace("Ready to say: ", "", 1).strip()
            if cleaned:
                trivia.append(cleaned)
        if trivia:
            return self._format_bullets(trivia[:6])
        return "- No archival trivia promoted yet; use only confirmed source-backed items."

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
            if self._is_placeholder_player_name(name):
                continue
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
        degraded = news.get("validation_status") == "degraded"

        synthesis = self._clean_news_text(synthesis)

        if degraded or self._has_only_unconfirmed_team_news(news):
            return self._build_team_news_fallback(team_name, side_label)

        if not synthesis and not news_items and not injuries:
            return self._build_team_news_fallback(team_name, side_label)

        output = ""
        if synthesis:
            output = f"{synthesis}\n\n"
        else:
            fallback = self._build_team_news_fallback(team_name, side_label)
            output = f"{fallback}\n\n"

        if news_items:
            output += "**Recent Headlines**:\n"
            for item in news_items:
                title = item.get('title', '')
                if title:
                    label = item.get("source_policy_label") or item.get("source_tier") or item.get("source") or "accepted source"
                    output += f"- {title} ({label})\n"
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
        """Write a concise team-news fallback that does not imply unverified context."""
        is_away = side_label == "away"
        label = team_name or ("Away side" if is_away else "home side")
        return f"No verified {label} team-news update was accepted in this run."

    def _has_only_unconfirmed_team_news(self, news: Dict[str, Any]) -> bool:
        lineup_status = news.get("lineup_status")
        lineup_value = ""
        if isinstance(lineup_status, dict):
            lineup_value = str(lineup_status.get("status") or "")
        elif lineup_status:
            lineup_value = str(lineup_status)

        has_confirmed_lineup = lineup_value.lower() in {"confirmed", "official"}
        if has_confirmed_lineup or news.get("injuries"):
            return False

        news_items = news.get("news_items") or []
        titles = " ".join(str(item.get("title") or "") for item in news_items if isinstance(item, dict)).lower()
        if not titles:
            return bool(lineup_value)

        unconfirmed_markers = (
            "predicted",
            "how to watch",
            "tv channel",
            "live stream",
            "schedule",
            "live",
            "preview",
        )
        return any(marker in titles for marker in unconfirmed_markers)

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
        if side_label == "away":
            player_clause = (
                "connect the early defensive block to the named player roles"
                if players
                else "identify the outlet and counter-press roles from the opening away spell"
            )
            form_clause = (
                f" Recent sequence {form_string}: call whether that confidence survives the first pressure wave."
                if self._is_meaningful_form_string(form_string)
                else ""
            )
            return (
                f"- {team_name}: {player_clause}; watch compactness after turnovers, the first escape pass, "
                f"and how quickly the wide outlet gets support.{form_clause}"
            )
        player_clause = (
            "tie early territorial control to the named player roles"
            if players
            else "identify the tempo-setter and line-breaker from the opening home spell"
        )
        form_clause = (
            f" Recent sequence {form_string}: call whether that becomes sustained territory."
            if self._is_meaningful_form_string(form_string)
            else ""
        )
        return (
            f"- {team_name}: {player_clause}; watch the opening tempo, first forward pass, "
            f"and whether wide pressure pins the opponent back.{form_clause}"
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
            if (
                p1
                and p2
                and not self._is_placeholder_player_name(p1)
                and not self._is_placeholder_player_name(p2)
            ):
                if analysis:
                    formatted.append(f"**{p1} vs {p2}**\n{analysis}\n")
                else:
                    formatted.append(f"**{p1} vs {p2}**\nKey tactical battle expected in this matchup.\n")

        if formatted:
            return "\n".join(formatted)

        return (
            "- Central lane: identify which midfield can receive under pressure and play forward cleanly.\n"
            "- Wide channels: watch whether the first isolation produces a cross, a cutback, or a turnover.\n"
            "- Defensive transition: after the first broken attack, call which back line recovers shape faster.\n"
            "- Set pieces: use the first corner or wide free kick to judge marking, second-ball reaction, and delivery quality."
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
            return "Stadium not verified in this run"
        cleaned = venue.strip()
        if not cleaned or cleaned.lower() in {"unknown", "unknown venue", "tbd", "unavailable", "n/a"}:
            return "Stadium not verified in this run"
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
            for first in critical_matchups:
                p1 = first.get('player1', '')
                p2 = first.get('player2', '')
                if p1 and p2 and not self._is_placeholder_player_name(p1) and not self._is_placeholder_player_name(p2):
                    bullets.append(f"1. Key duel: {p1} vs {p2}")
                    break

        h2h = historical.get("h2h_history", {})
        if h2h and h2h.get("status") != "unavailable" and (
            (h2h.get("team1_wins") or 0) + (h2h.get("team2_wins") or 0) + (h2h.get("draws") or 0)
        ) > 0:
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
            if verdict and not self._is_low_quality_text(verdict):
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

        first_matchup = next(
            (
                matchup for matchup in (matchups.get("critical_matchups") or [])
                if matchup.get("player1")
                and matchup.get("player2")
                and not self._is_placeholder_player_name(matchup.get("player1"))
                and not self._is_placeholder_player_name(matchup.get("player2"))
            ),
            {},
        )
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
            angles.extend([
                f"Opening hook: {home_team} vs {away_team} is a final, but the first proof point is control of the middle third.",
                "Momentum hook: after the first turnover, name whether the counter-press or the outlet pass wins.",
                "Evidence hook: keep lineup, injury, venue, and schedule claims out until the live feed verifies them.",
            ])

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

        if self._is_meaningful_form_string(form_string):
            return (
                f"{team_name}: recent results are available as {form_string}, but treat them as context rather than a script. "
                "The useful live read is whether their first three possessions create territory, whether the midfield can play through pressure, "
                "and whether the defensive line stays connected after turnovers."
            )

        if has_record:
            record_text = f"{wins or 0}W-{draws or 0}D-{losses or 0}L"
            return (
                f"{team_name}: available record context is {record_text}. Do not sell it as a match prediction. "
                "Use it to set one opening question: does that baseline show up as territorial control, clean rest defense, or repeat pressure?"
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
        recent_form = form_analysis.get("recent_form", {}) if isinstance(form_analysis, dict) else {}
        form_string = recent_form.get("form_string", "") if isinstance(recent_form, dict) else ""
        context = (
            f"Use the recent sequence {form_string} only as a context cue. "
            if self._is_meaningful_form_string(form_string)
            else ""
        )
        return (
            f"{team_name}: {context}In possession, watch first-pass security under pressure. "
            "Out of possession, check how quickly the midfield supports the ball. "
            "In transition, judge whether wide pressure becomes a repeatable final-third entry or breaks down into isolated moments."
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
        if "clear form favorability" in lower:
            return True
        if "lacking available performance metrics" in lower:
            return True
        if "balanced on verified data" in lower:
            return True
        if "no verified season-stat edge" in lower:
            return True
        if lower.startswith("as an elite"):
            return True
        if "limited historical data" in lower:
            return True
        if self._looks_like_numbered_homework(cleaned):
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
        if re.fullmatch(r"(?:\d+\.\s*)?(?:declining|stable|resurgent|in-form)[.!]?", lower):
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

    def _looks_like_numbered_homework(self, text: Any) -> bool:
        """Reject LLM outline prose that reads like an answer sheet, not booth notes."""
        if not isinstance(text, str):
            return False
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return False
        numbered_markers = len(re.findall(r"(?:^|\s)[1-5]\.\s+", cleaned))
        if numbered_markers >= 2:
            return True
        return bool(re.search(r"\b1\.\s*(?:in-form|declining|stable|resurgent)\b", cleaned, flags=re.I))

    def _is_placeholder_player_name(self, name: Any) -> bool:
        """Reject mock squad names before they become commentary copy."""
        if not isinstance(name, str):
            return True
        cleaned = " ".join(name.split()).strip()
        if not cleaned or cleaned.lower() == "unknown":
            return True
        if cleaned.endswith("-"):
            return True
        blocked_exact = {
            "against bayern",
            "and andy",
            "assistant referee bastian dankert",
            "bayern munich",
            "french ligue",
            "holders paris",
            "les parisiens",
            "marc atkins",
            "mark leech",
            "paris st germain",
            "pass-happy psg",
            "real madrid",
            "stamford bridge",
            "the gunners",
            "uefa champions league round",
        }
        if cleaned.lower() in blocked_exact:
            return True
        prefix = cleaned.split()[0]
        if prefix in {"Against", "And", "Assistant", "French", "Holders", "Pass-happy", "The"}:
            return True
        blocked_tokens = {
            "AFP",
            "Assistant",
            "Bridge",
            "Champions",
            "FIFE",
            "Fourth",
            "GER",
            "League",
            "Referee",
            "Round",
            "Stamford",
            "SUI",
            "UEFA",
            "Video",
        }
        if any(token in blocked_tokens for token in cleaned.split()):
            return True
        if any(token in {"Getty", "Reuters", "Image", "Images", "Photo", "For"} for token in cleaned.split()):
            return True
        return bool(re.search(r"\bPlayer\s+\d+\b", cleaned, flags=re.I))

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
            or "cannot be determined" in lower
            or "unquantifiable" in lower
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
            or "none reported" in lower
            or "no injuries" in lower
            or "no injury" in lower
            or "no major disruption" in lower
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
                "competition": all_outputs.get("competition", ""),
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
