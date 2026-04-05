"""
Commentary Note Organizer Agent - Synthesize all agent outputs into final notes.

Orchestrates all previous agent outputs into professional Drury-style
commentary notes in Markdown + JSON format.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import logging
from agents.base import BaseAgent
from data_sources import DataCache

logger = logging.getLogger(__name__)


class CommentaryNoteOrganizerAgent(BaseAgent):
    """Synthesize all research into final commentary notes."""

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

    async def execute(self, all_agent_outputs: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Execute final note synthesis."""
        return await self.synthesize_to_markdown_json(all_agent_outputs)

    async def synthesize_to_markdown_json(
        self,
        all_agent_outputs: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Synthesize all agent outputs into final Markdown + JSON notes.

        Args:
            all_agent_outputs: Dictionary containing outputs from all agents:
                - player_research: Squad research data
                - team_form: Form analysis
                - historical: H2H and storylines
                - weather: Weather impact
                - matchups: Key matchups
                - news: Injuries and updates

        Returns:
            Tuple of (markdown_notes: str, json_structure: dict)
        """
        start_time = datetime.utcnow()

        # Build JSON structure
        json_structure = await self._build_json_structure(all_agent_outputs)

        # Build Markdown sections
        markdown = await self._build_markdown_document(all_agent_outputs)

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="notes_synthesis_complete",
            details={
                "markdown_length": len(markdown),
                "json_size_bytes": len(json.dumps(json_structure)),
                "duration_ms": duration_ms,
            },
        )

        return markdown, json_structure

    async def _build_markdown_document(self, all_outputs: Dict[str, Any]) -> str:
        """Build comprehensive Markdown document."""
        home_team = all_outputs.get("home_team", "Home")
        away_team = all_outputs.get("away_team", "Away")
        match_datetime = all_outputs.get("match_datetime", "TBD")
        venue = all_outputs.get("venue", "Unknown")
        tactical_brief = self._build_tactical_brief(all_outputs)

        # PAGE 1: Lineups & Match Info
        page1 = self._organize_lineups_section(
            all_outputs.get("player_research", {}).get("home_team", {}),
            all_outputs.get("player_research", {}).get("away_team", {}),
            match_datetime,
            venue,
            all_outputs.get("weather", {}),
        )

        # PAGE 2: Home Team Analysis
        page2 = self._organize_team_analysis_section(
            all_outputs.get("player_research", {}).get("home_team", {}),
            all_outputs.get("team_form", {}).get("home_team", {}),
            all_outputs.get("news", {}).get("home_team", {}),
            "Home Team",
        )

        # PAGE 3: Away Team Analysis
        page3 = self._organize_team_analysis_section(
            all_outputs.get("player_research", {}).get("away_team", {}),
            all_outputs.get("team_form", {}).get("away_team", {}),
            all_outputs.get("news", {}).get("away_team", {}),
            "Away Team",
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
#### {match_datetime} | {venue}

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
        conditions = weather.get("current_conditions", {}).get("conditions") or "unavailable"
        wind = weather.get("current_conditions", {}).get("wind_kmh")
        home_players = home_squad.get("players", [])[:11]
        away_players = away_squad.get("players", [])[:11]

        lineup_rows = self._format_lineup_rows(home_players, away_players)

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
- Referee: TBD / Unannounced

**Probable Starters From Available Research**

| {home_team} | Pos | {away_team} |
|-----------|-----|-----------|
{lineup_rows}

**Lineup Note**: Derived from currently available researched squad data; official XI may differ.
"""

    def _organize_team_analysis_section(
        self,
        player_research: Dict[str, Any],
        form_analysis: Dict[str, Any],
        news: Dict[str, Any],
        team_label: str,
    ) -> str:
        """Organize team analysis section (Pages 2-3)."""
        team_name = player_research.get("team_name", team_label)
        players = player_research.get("players", [])[:10]  # Top 10 players

        form_text = form_analysis.get("comprehensive_analysis", "Form data unavailable")

        form_section = form_text
        split = form_analysis.get("home_away_split", {})
        if split:
            home_row = split.get("home", {})
            away_row = split.get("away", {})
            split_text = (
                f"Home: {home_row.get('won', 0)}W-{home_row.get('draw', 0)}D-{home_row.get('lost', 0)}L | "
                f"Away: {away_row.get('won', 0)}W-{away_row.get('draw', 0)}D-{away_row.get('lost', 0)}L"
            )
            form_section = f"{form_text}\n\nVerified Home/Away Split: {split_text}"

        return f"""---

## PAGE {2 if team_label == 'Home Team' else 3}: {team_label.upper()} ANALYSIS

**Recent Form** ({team_label})

Composite Analysis:
{form_section}

**Key Players** (Sorted by Recent Form)

{self._format_player_list(players)}

**Team News** ({team_label})

{self._format_news(news)}

**Tactical Profile**

- Verified tactical detail: use matchup analysis and team form sections for evidence-backed trends.
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
        narrative = historical.get("narrative", "No historical narrative")
        h2h = historical.get("h2h_history", {})
        h2h_record = (
            f"{h2h.get('team1_wins', 0)}-{h2h.get('draws', 0)}-{h2h.get('team2_wins', 0)}"
            if h2h else "Unavailable"
        )
        zone_edges = tactical_brief.get("zone_edges", [])
        pressure_points = tactical_brief.get("pressure_points", [])
        commentary_angles = tactical_brief.get("commentary_angles", [])

        return f"""---

## PAGES 4-5: TACTICAL ANALYSIS & STORYLINES

**Tactical Snapshot**

{tactical_brief.get('summary', 'Verified tactical snapshot unavailable.')}

### Zone-by-Zone Edge

{self._format_bullets(zone_edges)}

### How {home_team} Can Tilt The Match

{tactical_brief.get('home_plan', 'Home-side tactical route unavailable.')}

### How {away_team} Can Tilt The Match

{tactical_brief.get('away_plan', 'Away-side tactical route unavailable.')}

**Key 1v1 Matchups**

{self._format_matchups(critical_matchups)}

### Pressure Points To Mention Early

{self._format_bullets(pressure_points)}

### Commentary Angles To Keep Ready

{self._format_bullets(commentary_angles)}

**Historical Context**

H2H Record: **{h2h_record}**

Recent H2H Narrative:
{narrative}

**Weather Impact**

{weather.get('narrative', 'Standard weather conditions')}

**Expected Match Dynamic**

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
        summary = " ".join(part for part in summary_parts if part).strip()
        if not summary:
            summary = "Current inputs point to a balanced tactical battle, with matchup edges and weather cues carrying the strongest evidence."

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

    def _format_player_list(self, players: List[Dict[str, Any]]) -> str:
        """Format player list for markdown."""
        formatted = []
        for i, player in enumerate(players, 1):
            name = player.get("name", "Unknown")
            pos = player.get("position", "N/A")
            stats = player.get("stats", {}) if isinstance(player.get("stats"), dict) else {}
            apps = stats.get("appearances", 0)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            profile = player.get("profile", "Player profile unavailable")[:90]

            formatted.append(
                f"**{i}. {name}** ({pos})\n- Apps: {apps} | Goals: {goals} | Assists: {assists}\n- {profile}\n"
            )

        return "\n".join(formatted) if formatted else "Player data unavailable"

    def _format_news(self, news: Dict[str, Any]) -> str:
        """Format team news for markdown."""
        injuries = news.get("injuries", [])
        synthesis = news.get("synthesis", "No major updates")
        news_items = news.get("news_items", [])[:3]

        output = f"**Summary**: {synthesis}\n\n"

        if news_items:
            output += "**Recent Headlines**:\n"
            for item in news_items:
                output += f"- {item.get('title', 'Unknown headline')}\n"
            output += "\n"

        if injuries:
            output += "**Injuries**:\n"
            for inj in injuries:
                output += f"- {inj.get('player', 'Unknown')}: {inj.get('status', 'unknown')}\n"

        return output if output else "No news updates"

    def _format_lineup_rows(
        self,
        home_players: List[Dict[str, Any]],
        away_players: List[Dict[str, Any]],
    ) -> str:
        """Render two researched squads into a simple three-column lineup table."""
        rows = []
        max_len = max(len(home_players), len(away_players), 1)
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
            p1 = matchup.get("player1", "Unknown")
            p2 = matchup.get("player2", "Unknown")
            analysis = matchup.get("analysis", "Tactical battle expected")
            formatted.append(f"**{p1} vs {p2}**\n{analysis}\n")

        return "\n".join(formatted) if formatted else "Matchup analysis unavailable"

    def _format_bullets(self, items: List[str]) -> str:
        """Format a list of text items as markdown bullets."""
        clean_items = [item.strip() for item in items if isinstance(item, str) and item.strip()]
        return "\n".join(f"- {item}" for item in clean_items) if clean_items else "- No verified note available"

    def _format_weather_summary(self, temp: Any, conditions: str, wind: Any) -> str:
        """Format weather details without fabricating missing values."""
        parts = []
        if temp is not None:
            parts.append(f"{temp}°C")
        if conditions:
            parts.append(conditions.replace("_", " ").title())
        if wind is not None:
            parts.append(f"{wind} km/h wind")
        return ", ".join(parts) if parts else "Unavailable"

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
            bullets.append(
                f"1. Key duel: {first.get('player1', 'Unknown')} vs {first.get('player2', 'Unknown')}"
            )

        h2h = historical.get("h2h_history", {})
        if h2h:
            bullets.append(
                f"2. Historical trend: {h2h.get('team1_wins', 0)}-{h2h.get('draws', 0)}-{h2h.get('team2_wins', 0)} in the available H2H sample"
            )

        weather_narrative = weather.get("narrative")
        if weather_narrative:
            bullets.append(f"3. Weather factor: {weather_narrative.split('.')[0].strip()}")

        if not bullets:
            return "Evidence-based match dynamic unavailable from current inputs."

        return "\n".join(bullets)

    def _format_zone_edges(self, positional_strength: Dict[str, Any]) -> List[str]:
        """Summarize zone-level advantages for tactical notes."""
        if not positional_strength:
            return ["Zone-level edge unavailable from current lineup evidence."]

        zone_order = ["Defense", "Midfield", "Attack"]
        zone_edges = []
        for zone in zone_order:
            zone_data = positional_strength.get(zone, {})
            verdict = zone_data.get("verdict")
            if verdict:
                zone_edges.append(verdict)
        return zone_edges or ["Zone-level edge unavailable from current lineup evidence."]

    def _extract_team_plan(self, form_analysis: Dict[str, Any], team_name: str) -> str:
        """Extract a concise tactical route from the form-analysis summary."""
        analysis = form_analysis.get("comprehensive_analysis", "")
        plan = self._first_two_sentences(analysis)
        if plan:
            return plan
        return f"Verified tactical route for {team_name} is limited, so lean on live phase cues and matchup swings."

    def _build_pressure_points(
        self,
        home_team: str,
        away_team: str,
        weak_points: Dict[str, Any],
    ) -> List[str]:
        """Turn weak-point data into commentary-friendly notes."""
        pressure_points = []
        for note in weak_points.get("home_vulnerabilities", [])[:2]:
            pressure_points.append(f"{home_team}: {note}")
        for note in weak_points.get("away_vulnerabilities", [])[:2]:
            pressure_points.append(f"{away_team}: {note}")
        return pressure_points or ["No clear structural pressure point surfaced from verified lineup data."]

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
        if historical_pattern:
            angles.append(f"Frame the rivalry as a {historical_pattern.lower()} head-to-head pattern.")

        weather_lever = self._first_sentence(weather.get("narrative", ""))
        if weather_lever:
            angles.append(f"Weather cue: {weather_lever}")

        comparative_line = self._first_sentence(comparative)
        if comparative_line:
            angles.append(f"Form cue: {comparative_line}")

        if not angles:
            angles.append(f"Lead with how {home_team} and {away_team} handle the first tactical swing in midfield.")

        return angles[:4]

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
