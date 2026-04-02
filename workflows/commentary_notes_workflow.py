"""
Commentary Notes Workflow - LangGraph state machine for orchestrating agents.

Defines the multi-agent workflow using LangGraph for state management,
parallel execution, and error handling.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)


# ===== Workflow State Definition =====

class WorkflowPhase(str, Enum):
    """Phases of the commentary notes workflow."""

    INITIAL_CONTEXT = "initial_context"
    SQUAD_RESEARCH = "squad_research"
    FORM_ANALYSIS = "form_analysis"
    TACTICAL_PREPARATION = "tactical_preparation"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"


@dataclass
class CommentaryNotesState:
    """Complete state for commentary notes preparation workflow."""

    # === Match Information ===
    match_id: str
    home_team: str
    away_team: str
    sport: str = "soccer"
    match_datetime: str = ""
    venue: str = ""
    venue_lat: float = 0.0
    venue_lon: float = 0.0

    # === Workflow Metadata ===
    workflow_id: str = ""
    phase: WorkflowPhase = WorkflowPhase.INITIAL_CONTEXT
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    # === Agent Outputs (Accumulated) ===
    player_research: Dict[str, Any] = field(default_factory=dict)
    team_form: Dict[str, Any] = field(default_factory=dict)
    historical_context: Dict[str, Any] = field(default_factory=dict)
    weather_context: Dict[str, Any] = field(default_factory=dict)
    matchup_analysis: Dict[str, Any] = field(default_factory=dict)
    team_news: Dict[str, Any] = field(default_factory=dict)

    # === Final Outputs ===
    markdown_notes: Optional[str] = None
    json_structure: Optional[Dict[str, Any]] = None

    # === Error Tracking ===
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    agent_timings: Dict[str, float] = field(default_factory=dict)

    # === Progress Tracking ===
    completed_agents: List[str] = field(default_factory=list)
    in_progress_agents: List[str] = field(default_factory=list)


# ===== Workflow Node Definitions =====

class CommentaryNotesWorkflow:
    """LangGraph-based workflow for commentary notes preparation."""

    def __init__(self):
        """Initialize workflow."""
        self.state: Optional[CommentaryNotesState] = None

    async def initialize_workflow(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """Initialize workflow state."""
        import uuid

        state.workflow_id = str(uuid.uuid4())
        state.phase = WorkflowPhase.INITIAL_CONTEXT
        state.start_time = datetime.utcnow()

        logger.info(
            f"Workflow {state.workflow_id} initialized for {state.home_team} vs {state.away_team}"
        )

        return state

    async def gather_initial_context(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 1: Gather initial context in parallel.
        - NewsAgent → team_news
        - WeatherContextAgent → weather_context
        - HistoricalContextAgent → historical_context
        """
        from agents.specialized_commentary.news_agent import NewsAgent
        from agents.specialized_commentary.weather_context_agent import WeatherContextAgent
        from agents.specialized_commentary.historical_context_agent import HistoricalContextAgent
        from data_sources import DataCache

        logger.info(f"[{state.workflow_id}] Phase 1: Gathering initial context...")
        state.phase = WorkflowPhase.INITIAL_CONTEXT
        state.in_progress_agents = ["news", "weather", "historical"]

        cache = DataCache(ttl_seconds=1800)
        self._cache = cache  # share cache across phases

        async def _fetch_news():
            try:
                agent = NewsAgent(sport=state.sport, cache=cache)
                result = await agent.gather_match_news(state.home_team, state.away_team)
                state.team_news = result
                state.completed_agents.append("news")
                logger.info(f"[{state.workflow_id}] News gathered")
            except Exception as e:
                state.errors.append(f"NewsAgent: {e}")
                state.warnings.append("Team news unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] NewsAgent failed: {e}")

        async def _fetch_weather():
            try:
                agent = WeatherContextAgent(sport=state.sport, cache=cache)
                result = await agent.analyze_match_weather(
                    state.venue, state.venue_lat, state.venue_lon, state.match_datetime
                )
                state.weather_context = result
                state.completed_agents.append("weather")
                logger.info(f"[{state.workflow_id}] Weather gathered")
            except Exception as e:
                state.errors.append(f"WeatherContextAgent: {e}")
                state.warnings.append("Weather data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] WeatherContextAgent failed: {e}")

        async def _fetch_historical():
            try:
                agent = HistoricalContextAgent(sport=state.sport, cache=cache)
                result = await agent.build_match_narrative(state.home_team, state.away_team)
                state.historical_context = result
                state.completed_agents.append("historical")
                logger.info(f"[{state.workflow_id}] Historical context gathered")
            except Exception as e:
                state.errors.append(f"HistoricalContextAgent: {e}")
                state.warnings.append("Historical context unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] HistoricalContextAgent failed: {e}")

        await asyncio.gather(_fetch_news(), _fetch_weather(), _fetch_historical())
        state.in_progress_agents = []
        logger.info(f"[{state.workflow_id}] Phase 1 complete")
        return state

    async def research_squads(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 2: Research both squads in parallel.
        - PlayerResearchAgent.research_squad_pair(home, away) → player_research
        """
        from agents.specialized_commentary.player_research_agent import PlayerResearchAgent

        logger.info(f"[{state.workflow_id}] Phase 2: Researching squads...")
        state.phase = WorkflowPhase.SQUAD_RESEARCH
        state.in_progress_agents = ["player_research"]

        try:
            cache = getattr(self, "_cache", None)
            agent = PlayerResearchAgent(sport=state.sport, cache=cache)
            result = await agent.research_squad_pair(state.home_team, state.away_team)
            state.player_research = result
            state.completed_agents.append("player_research")
            logger.info(
                f"[{state.workflow_id}] Squad research complete: "
                f"{len(result.get('home_team', {}).get('players', []))} home / "
                f"{len(result.get('away_team', {}).get('players', []))} away players"
            )
        except Exception as e:
            state.errors.append(f"PlayerResearchAgent: {e}")
            state.warnings.append("Squad data unavailable — using minimal fallback")
            state.player_research = {
                "home_team": {"team_name": state.home_team, "players": []},
                "away_team": {"team_name": state.away_team, "players": []},
            }
            logger.warning(f"[{state.workflow_id}] PlayerResearchAgent failed: {e}")

        state.in_progress_agents = []
        return state

    async def analyze_form(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 3: Analyze form for both teams and key matchups in parallel.
        - TeamFormAgent.analyze_both_teams(home, away) → team_form
        - MatchupAnalysisAgent.analyze_key_matchups(lineups) → matchup_analysis
        """
        from agents.specialized_commentary.team_form_agent import TeamFormAgent
        from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent

        logger.info(f"[{state.workflow_id}] Phase 3: Form analysis & matchups...")
        state.phase = WorkflowPhase.FORM_ANALYSIS
        state.in_progress_agents = ["team_form", "matchup_analysis"]

        async def _analyze_form():
            try:
                cache = getattr(self, "_cache", None)
                agent = TeamFormAgent(sport=state.sport, cache=cache)
                result = await agent.analyze_both_teams(state.home_team, state.away_team)
                state.team_form = result
                state.completed_agents.append("team_form")
                logger.info(f"[{state.workflow_id}] Form analysis complete")
            except Exception as e:
                state.errors.append(f"TeamFormAgent: {e}")
                state.warnings.append("Form data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] TeamFormAgent failed: {e}")

        async def _analyze_matchups():
            try:
                home_players = state.player_research.get("home_team", {}).get("players", [])
                away_players = state.player_research.get("away_team", {}).get("players", [])
                agent = MatchupAnalysisAgent(sport=state.sport)
                result = await agent.analyze_key_matchups(home_players, away_players)
                state.matchup_analysis = result
                state.completed_agents.append("matchup_analysis")
                logger.info(f"[{state.workflow_id}] Matchup analysis complete")
            except Exception as e:
                state.errors.append(f"MatchupAnalysisAgent: {e}")
                state.warnings.append("Matchup analysis unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] MatchupAnalysisAgent failed: {e}")

        await asyncio.gather(_analyze_form(), _analyze_matchups())
        state.in_progress_agents = []
        return state

    async def synthesize_notes(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 4: Synthesize all agent outputs into final Markdown + JSON notes.
        - CommentaryNoteOrganizerAgent.synthesize_to_markdown_json(all_outputs)
        """
        from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent

        logger.info(f"[{state.workflow_id}] Phase 4: Synthesizing notes...")
        state.phase = WorkflowPhase.SYNTHESIS
        state.in_progress_agents = ["note_organizer"]

        all_outputs = {
            "home_team": state.home_team,
            "away_team": state.away_team,
            "sport": state.sport,
            "match_datetime": state.match_datetime,
            "venue": state.venue,
            "player_research": state.player_research,
            "team_form": state.team_form,
            "historical": state.historical_context,
            "weather": state.weather_context,
            "matchups": state.matchup_analysis,
            "news": state.team_news,
        }

        try:
            agent = CommentaryNoteOrganizerAgent(sport=state.sport)
            markdown_notes, json_structure = await agent.synthesize_to_markdown_json(all_outputs)
            state.markdown_notes = markdown_notes
            state.json_structure = json_structure
            state.completed_agents.append("note_organizer")
            logger.info(f"[{state.workflow_id}] Notes synthesized ({len(markdown_notes)} chars)")
        except Exception as e:
            state.errors.append(f"CommentaryNoteOrganizerAgent: {e}")
            logger.error(f"[{state.workflow_id}] Note synthesis failed: {e}")
            # Best-effort fallback markdown
            state.markdown_notes = (
                f"# Commentary Notes: {state.home_team} vs {state.away_team}\n\n"
                f"Synthesis failed: {e}\n\nRaw data available in json_structure."
            )
            state.json_structure = all_outputs

        state.in_progress_agents = []
        state.phase = WorkflowPhase.COMPLETE
        state.end_time = datetime.utcnow()
        logger.info(f"[{state.workflow_id}] Workflow complete")
        return state

    def get_duration_ms(self, state: CommentaryNotesState) -> float:
        """Calculate workflow duration."""
        if state.end_time:
            return (state.end_time - state.start_time).total_seconds() * 1000
        return (datetime.utcnow() - state.start_time).total_seconds() * 1000

    def get_status(self, state: CommentaryNotesState) -> Dict[str, Any]:
        """Get current workflow status."""
        return {
            "workflow_id": state.workflow_id,
            "phase": state.phase.value,
            "match": f"{state.home_team} vs {state.away_team}",
            "completed_agents": len(state.completed_agents),
            "in_progress": len(state.in_progress_agents),
            "errors": state.errors,
            "duration_ms": self.get_duration_ms(state),
        }

    async def run_workflow(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """Execute full workflow sequentially."""
        logger.info("Starting commentary notes workflow...")

        # Phase 1: Initialize
        state = await self.initialize_workflow(state)

        # Phase 2: Gather initial context
        state = await self.gather_initial_context(state)

        # Phase 3: Research squads
        state = await self.research_squads(state)

        # Phase 4: Analyze form
        state = await self.analyze_form(state)

        # Phase 5: Synthesize
        state = await self.synthesize_notes(state)

        logger.info(f"Workflow complete: {self.get_status(state)}")

        return state


# ===== Workflow Factory =====

def create_workflow() -> CommentaryNotesWorkflow:
    """Create new workflow instance."""
    return CommentaryNotesWorkflow()


# ===== Graph Building (LangGraph Integration) =====

def build_langgraph():
    """
    Build LangGraph state graph for workflow.

    This would integrate with actual LangGraph library in production.
    """
    # from langgraph.graph import StateGraph, END

    # workflow = StateGraph(CommentaryNotesState)

    # # Add nodes
    # workflow.add_node("initialize", initialize_workflow_node)
    # workflow.add_node("gather_context", gather_initial_context_node)
    # workflow.add_node("research_squads", research_squads_node)
    # workflow.add_node("analyze_form", analyze_form_node)
    # workflow.add_node("synthesize", synthesize_notes_node)

    # # Add edges
    # workflow.add_edge("START", "initialize")
    # workflow.add_edge("initialize", "gather_context")
    # workflow.add_edge("gather_context", "research_squads")
    # workflow.add_edge("research_squads", "analyze_form")
    # workflow.add_edge("analyze_form", "synthesize")
    # workflow.add_edge("synthesize", END)

    # return workflow.compile()

    logger.info("LangGraph integration pending (using sequential execution for now)")
    return None
