"""
Commentary Notes Workflow - LangGraph state machine for orchestrating agents.

Defines the multi-agent workflow using LangGraph for state management,
parallel execution, and error handling.
"""

from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Type alias for the optional progress callback
ProgressCallback = Optional[Callable[[str, str, Dict[str, Any]], Awaitable[None]]]

# Forward reference for NotesStore (lazy import to avoid circular deps)
NotesStore = Any  # Will be imported when needed


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
    notes_store: Optional[Any] = None  # NotesStore with O(1) lookup

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
        """Initialize workflow state and extract final contextual parameters sequentially."""
        import uuid
        from data_sources.factory import get_retriever
        
        state.workflow_id = str(uuid.uuid4())
        state.phase = WorkflowPhase.INITIAL_CONTEXT
        state.start_time = datetime.utcnow()

        logger.info(
            f"Workflow {state.workflow_id} initialized for {state.home_team} vs {state.away_team}"
        )
        
        # Sequentially populate missing venue and datetime data from ESPN before launching the parallel multi-agents
        if not state.match_datetime or not state.venue:
            logger.info(f"[{state.workflow_id}] Sequentially fetching match location and schedule...")
            retriever = get_retriever(state.sport)
            ctx = await retriever.get_match_context(state.home_team, state.sport) or {}
            state.match_datetime = (
                state.match_datetime
                or ctx.get("date")
                or datetime.utcnow().isoformat()
            )
            state.venue = state.venue or ctx.get("venue") or "Unknown"

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

        Note: TeamForm can run immediately (only needs team names), but MatchupAnalysis
        must wait for player_research to complete (Phase 2).
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
        Phase 4: Synthesize all agent outputs into structured NotesStore.
        - CommentaryNoteOrganizerAgent.synthesize_to_notes_store(all_outputs)
        - NotesStore contains: raw_markdown, beats (List[NarrativeBeat]), lookup (O(1))
        """
        from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent
        from models.notes_store import NotesStore

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
            notes_store = await agent.synthesize_to_notes_store(all_outputs)
            state.notes_store = notes_store
            state.markdown_notes = notes_store.raw_markdown  # Backwards compat
            state.completed_agents.append("note_organizer")
            logger.info(f"[{state.workflow_id}] Notes synthesized ({len(notes_store.raw_markdown)} chars, {len(notes_store.beats)} beats)")
        except Exception as e:
            state.errors.append(f"CommentaryNoteOrganizerAgent: {e}")
            logger.error(f"[{state.workflow_id}] Note synthesis failed: {e}")
            # Best-effort fallback markdown
            state.markdown_notes = (
                f"# Commentary Notes: {state.home_team} vs {state.away_team}\n\n"
                f"Synthesis failed: {e}\n\nRaw data available in all_outputs."
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

    async def run_workflow(
        self,
        state: CommentaryNotesState,
        on_progress: ProgressCallback = None,
        use_langgraph: bool = True,
    ) -> CommentaryNotesState:
        """Execute workflow with maximum parallelization, emitting progress via callback."""
        logger.info("Starting commentary notes workflow (optimized)...")

        if use_langgraph and on_progress is None:
            graph = build_langgraph(self)
            if graph is not None:
                logger.info("Running commentary notes workflow through LangGraph")
                result = await graph.ainvoke(state)
                return _coerce_commentary_state(result)

        async def _emit(phase: str, message: str, **extra):
            if on_progress:
                await on_progress(phase, message, extra)

        # Phase 1: Initialize (must be first - gets venue/datetime)
        await _emit("initialize", "Fetching match schedule and venue...")
        state = await self.initialize_workflow(state)
        await _emit("initialize", "Match context ready", done=True)

        # OPTIMIZATION 1: Run independent research branches together.
        # Team form only needs team names, so it does not need to wait for squad research.
        await _emit("parallel_phase", "Running parallel research phase...",
                    agents=["news", "weather", "historical", "player_research", "team_form"])

        async def _gather_context():
            result = await self.gather_initial_context(state)
            await _emit("initial_context", f"Initial context gathered (3 agents)", done=True)
            return result

        async def _research_squads():
            result = await self.research_squads(state)
            home_count = len(result.player_research.get("home_team", {}).get("players", []))
            away_count = len(result.player_research.get("away_team", {}).get("players", []))
            await _emit("squad_research", f"Squads researched ({home_count} + {away_count} players)", done=True)
            return result

        async def _analyze_team_form():
            from agents.specialized_commentary.team_form_agent import TeamFormAgent

            try:
                state.phase = WorkflowPhase.FORM_ANALYSIS
                cache = getattr(self, "_cache", None)
                agent = TeamFormAgent(sport=state.sport, cache=cache)
                state.team_form = await agent.analyze_both_teams(state.home_team, state.away_team)
                state.completed_agents.append("team_form")
                await _emit("form_analysis", "Team form analyzed", done=True)
            except Exception as e:
                state.errors.append(f"TeamFormAgent: {e}")
                state.warnings.append("Form data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] TeamFormAgent failed: {e}")
            return state

        # Execute independent branches in parallel
        await asyncio.gather(_gather_context(), _research_squads(), _analyze_team_form())
        await _emit("parallel_phase", "Parallel research phase complete", done=True)

        # OPTIMIZATION 2: MatchupAnalysis MUST wait for player_research.
        await _emit("matchup_analysis", "Analyzing key matchups...", agents=["matchup_analysis"])
        from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent
        try:
            state.phase = WorkflowPhase.TACTICAL_PREPARATION
            home_players = state.player_research.get("home_team", {}).get("players", [])
            away_players = state.player_research.get("away_team", {}).get("players", [])
            agent = MatchupAnalysisAgent(sport=state.sport)
            state.matchup_analysis = await agent.analyze_key_matchups(home_players, away_players)
            state.completed_agents.append("matchup_analysis")
            await _emit("matchup_analysis", "Key matchups analyzed", done=True)
        except Exception as e:
            state.errors.append(f"MatchupAnalysisAgent: {e}")
            state.warnings.append("Matchup analysis unavailable — skipping")
            logger.warning(f"[{state.workflow_id}] MatchupAnalysisAgent failed: {e}")

        # Phase 5: Synthesize
        await _emit("synthesis", "Synthesizing commentary notes...")
        state = await self.synthesize_notes(state)
        await _emit("synthesis", "Commentary notes ready", done=True)

        logger.info(f"Workflow complete: {self.get_status(state)}")

        return state


# ===== Workflow Factory =====

def create_workflow() -> CommentaryNotesWorkflow:
    """Create new workflow instance."""
    return CommentaryNotesWorkflow()


def _coerce_commentary_state(result: Any) -> CommentaryNotesState:
    """Convert LangGraph's dict output back into the workflow dataclass."""
    if isinstance(result, CommentaryNotesState):
        return result
    if not isinstance(result, dict):
        raise TypeError(f"Unexpected workflow result type: {type(result)!r}")

    allowed = {field_info.name for field_info in dataclass_fields(CommentaryNotesState)}
    values = {key: value for key, value in result.items() if key in allowed}
    phase = values.get("phase")
    if isinstance(phase, str):
        values["phase"] = WorkflowPhase(phase)
    return CommentaryNotesState(**values)


# ===== Graph Building (LangGraph Integration) =====

def build_langgraph(workflow: Optional[CommentaryNotesWorkflow] = None):
    """
    Build LangGraph state graph for workflow.

    Returns a compiled LangGraph runnable when langgraph is installed. If the
    dependency is unavailable, callers can fall back to run_workflow().
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:
        logger.warning("LangGraph unavailable; using native workflow runner: %s", exc)
        return None

    runner = workflow or CommentaryNotesWorkflow()
    graph = StateGraph(CommentaryNotesState)

    graph.add_node("initialize", runner.initialize_workflow)
    graph.add_node("gather_context", runner.gather_initial_context)
    graph.add_node("research_squads", runner.research_squads)
    graph.add_node("analyze_form", runner.analyze_form)
    graph.add_node("synthesize", runner.synthesize_notes)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "gather_context")
    graph.add_edge("gather_context", "research_squads")
    graph.add_edge("research_squads", "analyze_form")
    graph.add_edge("analyze_form", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
