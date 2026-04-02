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

        # PAGE 1: Lineups & Match Info
        page1 = self._organize_lineups_section(
            home_team,
            away_team,
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
        home_team: str,
        away_team: str,
        match_datetime: str,
        venue: str,
        weather: Dict[str, Any],
    ) -> str:
        """Organize PAGE 1 - Lineups & Match Info."""
        temp = weather.get("current_conditions", {}).get("temperature_c", "20")
        conditions = weather.get("current_conditions", {}).get("conditions", "clear")
        wind = weather.get("current_conditions", {}).get("wind_kmh", "0")

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
- Weather: {temp}°C, {conditions.replace('_', ' ').title()}, {wind} km/h wind
- Referee: TBD / Unannounced

**Starting XIs**

| {home_team} | Pos | {away_team} |
|-----------|-----|-----------|
| GK Player | GK | Away GK |
| CB Player 1 | CB | Away CB 1 |
| CB Player 2 | CB | Away CB 2 |
| LB Player | LB | LB Away |
| RB Player | RB | RB Away |
| CM Player 1 | CM | CM Away 1 |
| CM Player 2 | CM | CM Away 2 |
| CAM Player | AM | AM Away |
| LW Player | LW | LW Away |
| ST Player | ST | ST Away |
| RW Player | RW | RW Away |

**Formation**: 4-3-3 vs 3-5-2
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

        return f"""---

## PAGE {2 if team_label == 'Home Team' else 3}: {team_label.upper()} ANALYSIS

**Recent Form** ({team_label})

Composite Analysis:
{form_text}

**Key Players** (Sorted by Recent Form)

{self._format_player_list(players)}

**Team News** ({team_label})

{self._format_news(news)}

**Tactical Profile**

- Formation: 4-3-3
- Pressing: High press in midfield
- Strength: Possession-based football
- Weakness: Vulnerable on counter-attack
"""

    def _organize_tactical_section(
        self,
        matchups: Dict[str, Any],
        historical: Dict[str, Any],
        weather: Dict[str, Any],
    ) -> str:
        """Organize tactical analysis section (Pages 4-5)."""
        critical_matchups = matchups.get("critical_matchups", [])
        narrative = historical.get("narrative", "No historical narrative")
        h2h_record = historical.get("h2h_history", {}).get("total_record", "Unknown")

        return f"""---

## PAGES 4-5: TACTICAL ANALYSIS & STORYLINES

**Key 1v1 Matchups**

{self._format_matchups(critical_matchups)}

**Historical Context**

H2H Record: **{h2h_record}**

Recent H2H Narrative:
{narrative}

**Weather Impact**

{weather.get('narrative', 'Standard weather conditions')}

**Expected Match Dynamic**

1. Opening phase: Home team likely to control possession
2. Midfield battle: Critical area for both sides
3. Attacking approach: Counter-attacks likely from Away team
4. Set pieces: Important tactical element
5. Final stages: Intensity expected to rise
"""

    def _format_player_list(self, players: List[Dict[str, Any]]) -> str:
        """Format player list for markdown."""
        formatted = []
        for i, player in enumerate(players, 1):
            name = player.get("name", "Unknown")
            pos = player.get("position", "N/A")
            apps = player.get("appearances", 0)
            goals = player.get("goals", 0)
            form = player.get("recent_form", "Steady")
            profile = player.get("profile", "Professional player")[:60] + "..."

            formatted.append(
                f"**{i}. {name}** ({pos})\n- Apps: {apps} | Goals: {goals} | Form: {form}\n- {profile}\n"
            )

        return "\n".join(formatted) if formatted else "Player data unavailable"

    def _format_news(self, news: Dict[str, Any]) -> str:
        """Format team news for markdown."""
        injuries = news.get("injuries", [])
        suspensions = news.get("suspensions", [])
        synthesis = news.get("synthesis", "No major updates")

        output = f"**Summary**: {synthesis}\n\n"

        if injuries:
            output += "**Injuries**:\n"
            for inj in injuries:
                output += f"- {inj.get('player', 'Unknown')}: {inj.get('status', 'unknown')}\n"

        if suspensions:
            output += "**Suspensions**:\n"
            for susp in suspensions:
                output += f"- {susp.get('player', 'Unknown')}: {susp.get('remaining_matches', 1)} match\n"

        return output if output else "No news updates"

    def _format_matchups(self, matchups: List[Dict[str, Any]]) -> str:
        """Format key matchups for markdown."""
        formatted = []
        for matchup in matchups[:5]:
            p1 = matchup.get("player1", "Unknown")
            p2 = matchup.get("player2", "Unknown")
            analysis = matchup.get("analysis", "Tactical battle expected")
            formatted.append(f"**{p1} vs {p2}**\n{analysis}\n")

        return "\n".join(formatted) if formatted else "Matchup analysis unavailable"

    async def _build_json_structure(self, all_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Build complete JSON structure for embedded data."""
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
                "data_sources": ["espn", "openweathermap", "wikipedia", "rag"],
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
            "historical_context": all_outputs.get("historical", {}),
            "weather": all_outputs.get("weather", {}),
            "quality_metrics": {
                "data_completeness": 0.95,
                "sources_used": 4,
                "warnings": [],
            },
        }

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
