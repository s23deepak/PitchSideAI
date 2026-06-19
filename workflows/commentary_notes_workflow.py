"""
Commentary Notes Workflow - LangGraph state machine for orchestrating agents.

Defines the multi-agent workflow using LangGraph for state management,
parallel execution, and error handling.
"""

from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime, timezone
import asyncio
import logging
from pathlib import Path
import sys
from enum import Enum
import re

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_project_root_on_path() -> None:
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

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
    competition: str = ""
    match_datetime: str = ""
    venue: str = ""
    venue_lat: float = 0.0
    venue_lon: float = 0.0
    fixture_context: Dict[str, Any] = field(default_factory=dict)

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
    officials_context: Dict[str, Any] = field(default_factory=dict)
    venue_details: Dict[str, Any] = field(default_factory=dict)
    manager_profiles: Dict[str, Any] = field(default_factory=dict)
    club_history: Dict[str, Any] = field(default_factory=dict)
    transfers_context: Dict[str, Any] = field(default_factory=dict)
    pronunciation: Dict[str, Any] = field(default_factory=dict)

    # === Final Outputs ===
    markdown_notes: Optional[str] = None
    json_structure: Optional[Dict[str, Any]] = None
    notes_store: Optional[Any] = None  # NotesStore with O(1) lookup
    source_provenance: Dict[str, Any] = field(default_factory=dict)
    quality_report: Dict[str, Any] = field(default_factory=dict)
    targeted_evidence: Dict[str, Any] = field(default_factory=dict)
    fact_ledger: Dict[str, Any] = field(default_factory=dict)
    notes_evaluation: Dict[str, Any] = field(default_factory=dict)
    vlm_context: Dict[str, Any] = field(default_factory=dict)
    retrieval_summary: Dict[str, Any] = field(default_factory=dict)
    notes_version: int = 0
    vlm_context_version: int = 0
    revision_count: int = 0

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
        self._progress_callback: ProgressCallback = None

    async def _emit(self, phase: str, message: str, **extra: Any) -> None:
        if self._progress_callback:
            await self._progress_callback(phase, message, extra)

    def _ensure_cache(self):
        from data_sources import DataCache

        cache = getattr(self, "_cache", None)
        if cache is None:
            cache = DataCache(ttl_seconds=1800)
            self._cache = cache
        return cache

    async def initialize_workflow(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """Initialize workflow state and extract final contextual parameters sequentially."""
        import uuid
        from data_sources.factory import get_retriever
        from data_sources.fixture_resolver import FixtureResolver
        
        state.workflow_id = str(uuid.uuid4())
        state.phase = WorkflowPhase.INITIAL_CONTEXT
        state.start_time = datetime.utcnow()

        from data_sources.retrieval_audit import set_audit_run_id
        set_audit_run_id(state.workflow_id)

        logger.info(
            f"Workflow {state.workflow_id} initialized for {state.home_team} vs {state.away_team}"
        )
        await self._emit("initialize", "Preparing match context...")
        self._ensure_cache()

        # For custom generated fixtures, resolve facts from fixture-specific evidence first.
        # Do not borrow a team's unrelated next event unless no competition was provided.
        if not state.match_datetime or not state.venue:
            if state.competition:
                resolver = FixtureResolver(cache=self._ensure_cache())
                fixture_context = await resolver.resolve(
                    home_team=state.home_team,
                    away_team=state.away_team,
                    sport=state.sport,
                    competition=state.competition,
                )
                state.fixture_context = fixture_context or {}

                if not state.match_datetime and state.fixture_context.get("match_datetime"):
                    state.match_datetime = state.fixture_context["match_datetime"]
                if not state.venue and state.fixture_context.get("venue"):
                    state.venue = state.fixture_context["venue"]
                if not state.venue_lat and state.fixture_context.get("venue_lat"):
                    state.venue_lat = state.fixture_context["venue_lat"]
                if not state.venue_lon and state.fixture_context.get("venue_lon"):
                    state.venue_lon = state.fixture_context["venue_lon"]

                if not state.match_datetime:
                    state.warnings.append("Kickoff time unverified for custom fixture")
                if not state.venue:
                    state.warnings.append("Venue unverified for custom fixture")
                state.venue = state.venue or "Unknown"
                if state.fixture_context.get("status") == "accepted":
                    state.warnings.append("Fixture context resolved from fixture-specific web evidence")
            else:
                logger.info(f"[{state.workflow_id}] Sequentially fetching match location and schedule...")
                retriever = get_retriever(state.sport)
                ctx = await retriever.get_match_context(state.home_team, state.sport) or {}
                state.match_datetime = state.match_datetime or ctx.get("date") or ""
                state.venue = state.venue or ctx.get("venue") or "Unknown"

        await self._emit("initialize", "Match context ready", done=True)
        return state

    async def gather_initial_context(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 1: Gather initial context in parallel.
        - NewsAgent → team_news
        - WeatherContextAgent → weather_context
        - HistoricalContextAgent → historical_context
        """
        _ensure_project_root_on_path()
        from agents.specialized_commentary.news_agent import NewsAgent
        from agents.specialized_commentary.weather_context_agent import WeatherContextAgent
        from agents.specialized_commentary.historical_context_agent import HistoricalContextAgent
        logger.info(f"[{state.workflow_id}] Phase 1: Gathering initial context...")
        state.phase = WorkflowPhase.INITIAL_CONTEXT
        state.in_progress_agents = ["news", "weather", "historical"]

        cache = self._ensure_cache()

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

    async def parallel_research(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """LangGraph node: run independent notes research branches concurrently."""
        await self._emit(
            "parallel_phase",
            "Running parallel research phase...",
            agents=["news", "weather", "historical", "player_research", "team_form"],
        )

        async def _gather_context():
            result = await self.gather_initial_context(state)
            await self._emit("initial_context", "Initial context gathered (3 agents)", done=True)
            return result

        async def _research_squads():
            result = await self.research_squads(state)
            home_count = len(result.player_research.get("home_team", {}).get("players", []))
            away_count = len(result.player_research.get("away_team", {}).get("players", []))
            await self._emit(
                "squad_research",
                f"Squads researched ({home_count} + {away_count} players)",
                done=True,
            )
            return result

        async def _analyze_team_form():
            _ensure_project_root_on_path()
            from agents.specialized_commentary.team_form_agent import TeamFormAgent

            try:
                state.phase = WorkflowPhase.FORM_ANALYSIS
                agent = TeamFormAgent(sport=state.sport, cache=self._ensure_cache())
                state.team_form = await agent.analyze_both_teams(state.home_team, state.away_team)
                state.completed_agents.append("team_form")
                await self._emit("form_analysis", "Team form analyzed", done=True)
            except Exception as e:
                state.errors.append(f"TeamFormAgent: {e}")
                state.warnings.append("Form data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] TeamFormAgent failed: {e}")
            return state

        await asyncio.gather(_gather_context(), _research_squads(), _analyze_team_form())
        await self._emit("parallel_phase", "Parallel research phase complete", done=True)
        return state

    async def targeted_evidence_search(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """Use Exa as a quota-conscious gap filler when strict evidence is thin."""
        _ensure_project_root_on_path()
        import copy
        from data_sources.factory import get_exa_search_service
        from quality.evidence import (
            build_evidence_quality_report,
            filter_allowed_search_results,
        )

        current_outputs = copy.deepcopy(self._build_all_outputs(state))
        current_report = build_evidence_quality_report(current_outputs, mutate=False)
        accepted_count = int(current_report.get("accepted_evidence_count") or 0)
        exa = get_exa_search_service()
        if accepted_count >= 4 or not exa.is_available:
            state.targeted_evidence = {
                "enabled": exa.is_available,
                "skipped": True,
                "reason": "accepted evidence threshold met" if accepted_count >= 4 else "EXA_API_KEY/EXA_API not configured",
                "accepted_evidence_count": accepted_count,
                "results_by_topic": {},
            }
            return state

        await self._emit("targeted_evidence", "Searching Exa for missing source-backed facts...")
        routes = self._exa_query_routes(state)
        results_by_topic: Dict[str, List[Dict[str, Any]]] = {}
        rejected_by_topic: Dict[str, List[Dict[str, Any]]] = {}
        for topic, route in routes.items():
            search = await exa.search(
                route["query"],
                topic=topic,
                search_type=route.get("search_type", "auto"),
                max_results=route.get("max_results", 4),
                include_domains=route.get("include_domains", []),
                start_published_date=route.get("start_published_date"),
                cache_namespace="exa_commentary_notes",
            )
            accepted, rejected = filter_allowed_search_results(
                search.get("results", []),
                home_team=state.home_team,
                away_team=state.away_team,
                topic="team_news" if topic == "team_news" else ("storylines" if topic in {"fixture", "h2h", "tactical"} else topic),
                max_results=4,
            )
            results_by_topic[topic] = accepted
            rejected_by_topic[topic] = [item.to_dict() for item in rejected]

        self._merge_targeted_evidence(state, results_by_topic)
        state.targeted_evidence = {
            "enabled": True,
            "skipped": False,
            "provider": "exa",
            "accepted_evidence_count_before": accepted_count,
            "results_by_topic": results_by_topic,
            "rejected_by_topic": rejected_by_topic,
        }
        await self._emit("targeted_evidence", "Exa evidence search complete", done=True)
        return state

    async def research_squads(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 2: Research both squads in parallel.
        - PlayerResearchAgent.research_squad_pair(home, away) → player_research
        """
        _ensure_project_root_on_path()
        from agents.specialized_commentary.player_research_agent import PlayerResearchAgent

        logger.info(f"[{state.workflow_id}] Phase 2: Researching squads...")
        state.phase = WorkflowPhase.SQUAD_RESEARCH
        state.in_progress_agents = ["player_research"]

        try:
            cache = getattr(self, "_cache", None)
            agent = PlayerResearchAgent(sport=state.sport, cache=cache)
            result = await agent.research_squad_pair(
                state.home_team,
                state.away_team,
                fixture_context=state.fixture_context,
            )

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
        _ensure_project_root_on_path()
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

    async def analyze_matchups(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """LangGraph node: run matchup analysis after squad research is available."""
        await self._emit("matchup_analysis", "Analyzing key matchups...", agents=["matchup_analysis"])
        _ensure_project_root_on_path()
        from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent

        try:
            state.phase = WorkflowPhase.TACTICAL_PREPARATION
            home_players = state.player_research.get("home_team", {}).get("players", [])
            away_players = state.player_research.get("away_team", {}).get("players", [])
            agent = MatchupAnalysisAgent(sport=state.sport)
            state.matchup_analysis = await agent.analyze_key_matchups(home_players, away_players)
            state.completed_agents.append("matchup_analysis")
            await self._emit("matchup_analysis", "Key matchups analyzed", done=True)
        except Exception as e:
            state.errors.append(f"MatchupAnalysisAgent: {e}")
            state.warnings.append("Matchup analysis unavailable — skipping")
            logger.warning(f"[{state.workflow_id}] MatchupAnalysisAgent failed: {e}")
        return state

    async def enrich_context(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 2b: Deep Enrichment — 6 NEW agents in parallel.
        - OfficialsAgent, VenueDetailsAgent, ManagerProfilesAgent
        - ClubHistoryAgent, TransfersAgent, PronunciationAgent
        All 6 run concurrently via asyncio.gather.
        """
        _ensure_project_root_on_path()
        from agents.specialized_commentary.officials_agent import OfficialsAgent
        from agents.specialized_commentary.venue_details_agent import VenueDetailsAgent
        from agents.specialized_commentary.manager_profiles_agent import ManagerProfilesAgent
        from agents.specialized_commentary.club_history_agent import ClubHistoryAgent
        from agents.specialized_commentary.transfers_agent import TransfersAgent
        from agents.specialized_commentary.pronunciation_agent import PronunciationAgent

        logger.info(f"[{state.workflow_id}] Phase 2b: Deep enrichment (6 agents)...")
        state.in_progress_agents = ["officials", "venue_details", "manager_profiles", "club_history", "transfers", "pronunciation"]

        cache = self._ensure_cache()

        async def _fetch_officials():
            try:
                agent = OfficialsAgent(sport=state.sport, cache=cache)
                result = await agent.execute(
                    home_team=state.home_team,
                    away_team=state.away_team,
                    competition=state.competition,
                    fixture_context=state.fixture_context,
                )
                state.officials_context = result
                state.completed_agents.append("officials")
                logger.info(f"[{state.workflow_id}] Officials context gathered")
            except Exception as e:
                state.errors.append(f"OfficialsAgent: {e}")
                state.warnings.append("Officials data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] OfficialsAgent failed: {e}")

        async def _fetch_venue_details():
            try:
                agent = VenueDetailsAgent(sport=state.sport, cache=cache)
                result = await agent.execute(
                    venue=state.venue,
                    latitude=state.venue_lat,
                    longitude=state.venue_lon,
                )
                state.venue_details = result
                state.completed_agents.append("venue_details")
                logger.info(f"[{state.workflow_id}] Venue details gathered")
            except Exception as e:
                state.errors.append(f"VenueDetailsAgent: {e}")
                state.warnings.append("Venue details unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] VenueDetailsAgent failed: {e}")

        async def _fetch_manager_profiles():
            try:
                agent = ManagerProfilesAgent(sport=state.sport, cache=cache)
                result = await agent.execute(
                    home_team=state.home_team,
                    away_team=state.away_team,
                    players_context=state.player_research,
                )
                state.manager_profiles = result
                state.completed_agents.append("manager_profiles")
                logger.info(f"[{state.workflow_id}] Manager profiles gathered")
            except Exception as e:
                state.errors.append(f"ManagerProfilesAgent: {e}")
                state.warnings.append("Manager profiles unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] ManagerProfilesAgent failed: {e}")

        async def _fetch_club_history():
            try:
                agent = ClubHistoryAgent(sport=state.sport, cache=cache)
                result = await agent.execute(state.home_team, state.away_team)
                state.club_history = result
                state.completed_agents.append("club_history")
                logger.info(f"[{state.workflow_id}] Club history gathered")
            except Exception as e:
                state.errors.append(f"ClubHistoryAgent: {e}")
                state.warnings.append("Club history unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] ClubHistoryAgent failed: {e}")

        async def _fetch_transfers():
            try:
                agent = TransfersAgent(sport=state.sport, cache=cache)
                result = await agent.execute(
                    home_team=state.home_team,
                    away_team=state.away_team,
                    players_context=state.player_research,
                )
                state.transfers_context = result
                state.completed_agents.append("transfers")
                logger.info(f"[{state.workflow_id}] Transfers context gathered")
            except Exception as e:
                state.errors.append(f"TransfersAgent: {e}")
                state.warnings.append("Transfer data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] TransfersAgent failed: {e}")

        async def _fetch_pronunciation():
            try:
                home_players = state.player_research.get("home_team", {}).get("players", [])
                away_players = state.player_research.get("away_team", {}).get("players", [])
                key_players = (home_players if isinstance(home_players, list) else [])[:8] + (
                    away_players if isinstance(away_players, list) else []
                )[:8]
                agent = PronunciationAgent(sport=state.sport, cache=cache)
                result = await agent.execute(key_players)
                state.pronunciation = result
                state.completed_agents.append("pronunciation")
                logger.info(f"[{state.workflow_id}] Pronunciation data gathered")
            except Exception as e:
                state.errors.append(f"PronunciationAgent: {e}")
                state.warnings.append("Pronunciation data unavailable — skipping")
                logger.warning(f"[{state.workflow_id}] PronunciationAgent failed: {e}")

        await asyncio.gather(
            _fetch_officials(),
            _fetch_venue_details(),
            _fetch_manager_profiles(),
            _fetch_club_history(),
            _fetch_transfers(),
            _fetch_pronunciation(),
        )
        state.in_progress_agents = []
        logger.info(f"[{state.workflow_id}] Phase 2b enrichment complete")
        return state

    async def synthesize_notes(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """
        Phase 4: Synthesize all agent outputs into structured NotesStore.
        - CommentaryNoteOrganizerAgent.synthesize_to_notes_store(all_outputs)
        - NotesStore contains: raw_markdown, beats (List[NarrativeBeat]), lookup (O(1))
        """
        _ensure_project_root_on_path()
        from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent
        from quality.evidence import build_evidence_quality_report

        logger.info(f"[{state.workflow_id}] Phase 4: Synthesizing notes...")
        await self._emit("synthesis", "Synthesizing commentary notes...")
        state.phase = WorkflowPhase.SYNTHESIS
        state.in_progress_agents = ["note_organizer"]

        all_outputs = self._build_all_outputs(state)
        if isinstance(state.team_news, dict) and state.team_news.get("possible_lineups"):
            all_outputs["possible_lineups"] = state.team_news["possible_lineups"]

        try:
            evidence_report = build_evidence_quality_report(all_outputs, mutate=True)
            state.quality_report = evidence_report
            from quality.fact_ledger import build_fact_ledger
            from agents.deep_notes_agent import DeepNotesResearchAgent
            from workflows.broadcast_dossier import build_broadcast_dossier

            all_outputs["fact_ledger"] = build_fact_ledger(all_outputs)
            state.fact_ledger = all_outputs["fact_ledger"]
            all_outputs["broadcast_dossier"] = build_broadcast_dossier(all_outputs)
            all_outputs.setdefault(
                "plausible_lineups",
                all_outputs["broadcast_dossier"].get("lineups", {}).get("plausible", {}),
            )
            deep_notes = await DeepNotesResearchAgent().enrich(all_outputs)
            all_outputs["deep_notes"] = deep_notes
            if not deep_notes.get("enabled") and "package unavailable" in str(deep_notes.get("reason", "")):
                state.warnings.append(f"Deep notes disabled: {deep_notes.get('reason', 'not configured')}")
            agent = CommentaryNoteOrganizerAgent(sport=state.sport)
            notes_store = await agent.synthesize_to_notes_store(all_outputs)
            state.notes_store = notes_store
            state.markdown_notes = notes_store.raw_markdown  # Backwards compat
            state.source_provenance = self._build_source_provenance(all_outputs)
            state.quality_report = {
                **evidence_report,
                "fact_ledger": state.fact_ledger,
                "notes_metrics": self._build_quality_report(state, notes_store),
            }
            state.vlm_context = self._build_vlm_context(notes_store)

            from workflows.retrieval_summary import build_retrieval_summary
            state.retrieval_summary = build_retrieval_summary(state.workflow_id)

            state.completed_agents.append("note_organizer")
            logger.info(f"[{state.workflow_id}] Notes synthesized ({len(notes_store.raw_markdown)} chars, {len(notes_store.beats)} beats)")
        except Exception as e:
            state.errors.append(f"CommentaryNoteOrganizerAgent: {e}")
            logger.error(f"[{state.workflow_id}] Note synthesis failed: {e}")
            state.json_structure = all_outputs
            state.in_progress_agents = []
            state.end_time = datetime.utcnow()
            await self._emit("error", f"Note synthesis failed: {e}", done=True)
            raise RuntimeError(f"Note synthesis failed: {e}") from e

        state.in_progress_agents = []
        state.phase = WorkflowPhase.COMPLETE
        state.end_time = datetime.utcnow()
        await self._emit("synthesis", "Commentary notes ready", done=True)
        logger.info(f"[{state.workflow_id}] Workflow complete")
        return state

    async def evaluate_notes(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """Evaluate the whole markdown artifact against format and fact-ledger rules."""
        _ensure_project_root_on_path()
        from quality.notes_refinement import evaluate_notes_document

        notes_store = state.notes_store
        if not notes_store:
            state.notes_evaluation = {
                "needs_revision": False,
                "missing_sections": [],
                "unsupported_claims": [],
                "error": "notes_store unavailable",
            }
            return state
        beats_payload = self._beats_payload(notes_store)
        state.notes_evaluation = evaluate_notes_document(
            getattr(notes_store, "raw_markdown", "") or "",
            fact_ledger=state.fact_ledger,
            quality_report=state.quality_report,
            beats=beats_payload,
        )
        state.quality_report = {
            **state.quality_report,
            "notes_evaluation": state.notes_evaluation,
        }
        return state

    async def revise_notes(self, state: CommentaryNotesState) -> CommentaryNotesState:
        """Revise the whole markdown block using the latest evaluation."""
        _ensure_project_root_on_path()
        from models.notes_store import NotesStore
        from quality.notes_refinement import refine_notes_document

        if not state.notes_store:
            return state
        refined = refine_notes_document(
            getattr(state.notes_store, "raw_markdown", "") or "",
            evaluation=state.notes_evaluation,
            fact_ledger=state.fact_ledger,
            home_team=state.home_team,
            away_team=state.away_team,
        )
        state.revision_count += 1
        state.notes_store = NotesStore(raw_markdown=refined, beats=getattr(state.notes_store, "beats", []) or [])
        state.markdown_notes = refined
        state.quality_report = {
            **state.quality_report,
            "notes_metrics": self._build_quality_report(state, state.notes_store),
            "revision_count": state.revision_count,
        }
        state.vlm_context = self._build_vlm_context(state.notes_store)
        return state

    def _build_source_provenance(self, all_outputs: Dict[str, Any]) -> Dict[str, Any]:
        provenance: Dict[str, Any] = {}
        for key, value in all_outputs.items():
            if isinstance(value, dict):
                source = value.get("data_source") or value.get("source")
                if source:
                    provenance[key] = {"source": source}
        quality_report = all_outputs.get("quality_report")
        if isinstance(quality_report, dict):
            provenance["evidence"] = {
                "accepted_count": quality_report.get("accepted_evidence_count", 0),
                "rejected_count": quality_report.get("rejected_evidence_count", 0),
                "accepted_evidence": quality_report.get("accepted_evidence", [])[:20],
            }
        return provenance

    def _build_all_outputs(self, state: CommentaryNotesState) -> Dict[str, Any]:
        return {
            "home_team": state.home_team,
            "away_team": state.away_team,
            "sport": state.sport,
            "competition": state.competition,
            "match_datetime": state.match_datetime,
            "venue": state.venue,
            "fixture_context": state.fixture_context,
            "player_research": state.player_research,
            "team_form": state.team_form,
            "historical": state.historical_context,
            "weather": state.weather_context,
            "matchups": state.matchup_analysis,
            "news": state.team_news,
            "officials": state.officials_context,
            "venue_details": state.venue_details,
            "manager_profiles": state.manager_profiles,
            "club_history": state.club_history,
            "transfers": state.transfers_context,
            "pronunciation": state.pronunciation,
            "targeted_evidence": state.targeted_evidence,
        }

    def _exa_query_routes(self, state: CommentaryNotesState) -> Dict[str, Dict[str, Any]]:
        fixture_domains = ["fifa.com", "espn.com", "bbc.co.uk", "skysports.com"]
        preferred_news_domains = [
            "fifa.com",
            "espn.com",
            "reuters.com",
            "apnews.com",
            "bbc.co.uk",
            "bbc.com",
            "skysports.com",
            "theathletic.com",
            "sportsmole.co.uk",
        ]
        h2h_domains = ["fifa.com", "espn.com", "11v11.com", "eu-football.info", "worldfootball.net"]
        tactical_domains = ["espn.com", "theanalyst.com", "skysports.com", "sportsmole.co.uk", "nbcsports.com"]
        match = f"{state.home_team} vs {state.away_team}"
        competition = state.competition or "football"
        venue = state.venue or ""
        return {
            "fixture": {
                "query": f"{match} {competition} kickoff venue date official referee",
                "include_domains": fixture_domains,
                "max_results": 3,
            },
            "team_news": {
                "query": f"{match} {competition} team news injuries predicted lineups latest",
                "include_domains": preferred_news_domains,
                "max_results": 4,
            },
            "h2h": {
                "query": f"{match} head to head record previous meetings football",
                "include_domains": h2h_domains,
                "max_results": 4,
            },
            "tactical": {
                "query": f"{match} {competition} tactical preview set pieces key battles",
                "include_domains": tactical_domains,
                "max_results": 4,
            },
            "officials": {
                "query": f"{match} {competition} referee VAR officials appointments",
                "include_domains": ["fifa.com", "espn.com", "bbc.co.uk", "skysports.com", "uefa.com"],
                "max_results": 3,
            },
            "venue_history": {
                "query": f"{venue} stadium history capacity notable events matches",
                "include_domains": ["wikipedia.org", "stadiumguide.com", "espn.com", "bbc.co.uk"],
                "max_results": 3,
            },
            "manager_context": {
                "query": f"{match} managers pre-match press conference tactical preview",
                "include_domains": ["skysports.com", "bbc.co.uk", "goal.com", "theathletic.com"],
                "max_results": 3,
            },
            "transfer_context": {
                "query": f"{match} transfer news latest signings contract situations 2026",
                "include_domains": ["goal.com", "transfermarkt.com", "skysports.com", "bbc.co.uk", "theathletic.com"],
                "max_results": 3,
            },
        }

    def _merge_targeted_evidence(
        self,
        state: CommentaryNotesState,
        results_by_topic: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        if results_by_topic.get("team_news"):
            state.team_news = state.team_news if isinstance(state.team_news, dict) else {}
            for side, team in (("home_team", state.home_team), ("away_team", state.away_team)):
                team_news = state.team_news.setdefault(side, {"team_name": team, "news_items": []})
                team_news.setdefault("team_name", team)
                team_news.setdefault("news_items", [])
                existing_urls = {str(item.get("url") or "") for item in team_news["news_items"] if isinstance(item, dict)}
                for item in results_by_topic["team_news"]:
                    if item.get("url") not in existing_urls:
                        team_news["news_items"].append({**item, "source": item.get("source") or "exa"})

        historical_targets = []
        for topic in ("fixture", "h2h", "tactical", "officials", "venue_history", "manager_context", "transfer_context"):
            historical_targets.extend(results_by_topic.get(topic, []))
        if historical_targets:
            state.historical_context = state.historical_context if isinstance(state.historical_context, dict) else {}
            storylines = state.historical_context.setdefault("storylines", [])
            existing_urls = {str(item.get("url") or "") for item in storylines if isinstance(item, dict)}
            for item in historical_targets:
                if item.get("url") in existing_urls:
                    continue
                storylines.append({
                    "title": item.get("title") or "Targeted evidence",
                    "description": item.get("content") or "",
                    "url": item.get("url") or "",
                    "source": item.get("source") or "exa",
                    "topic": item.get("topic") or "targeted_evidence",
                })

        if results_by_topic.get("officials"):
            state.officials_context = state.officials_context if isinstance(state.officials_context, dict) else {}
            state.officials_context.setdefault("exa_sources", [])
            for item in results_by_topic["officials"]:
                state.officials_context["exa_sources"].append({
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "source": "exa",
                })

        if results_by_topic.get("venue_history"):
            state.venue_details = state.venue_details if isinstance(state.venue_details, dict) else {}
            state.venue_details.setdefault("exa_sources", [])
            for item in results_by_topic["venue_history"]:
                state.venue_details["exa_sources"].append({
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "source": "exa",
                })

        if results_by_topic.get("manager_context"):
            state.manager_profiles = state.manager_profiles if isinstance(state.manager_profiles, dict) else {}
            state.manager_profiles.setdefault("exa_sources", [])
            for item in results_by_topic["manager_context"]:
                state.manager_profiles["exa_sources"].append({
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "source": "exa",
                })

        if results_by_topic.get("transfer_context"):
            state.transfers_context = state.transfers_context if isinstance(state.transfers_context, dict) else {}
            state.transfers_context.setdefault("exa_sources", [])
            for item in results_by_topic["transfer_context"]:
                state.transfers_context["exa_sources"].append({
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "source": "exa",
                })

        if results_by_topic.get("h2h"):
            state.historical_context = state.historical_context if isinstance(state.historical_context, dict) else {}
            h2h = state.historical_context.setdefault("h2h_history", {})
            if isinstance(h2h, dict):
                h2h.update({
                    "status": "source_available",
                    "source_urls": [
                        item.get("url")
                        for item in results_by_topic["h2h"]
                        if item.get("url")
                    ],
                    "note": "Trusted H2H sources were found; use exact counts only when parsed from structured data.",
                })
        fixture_updates = self._extract_fixture_updates(results_by_topic.get("fixture", []))
        if fixture_updates:
            state.fixture_context = state.fixture_context if isinstance(state.fixture_context, dict) else {}
            state.fixture_context.update(fixture_updates)
            if not state.match_datetime and fixture_updates.get("match_datetime"):
                state.match_datetime = fixture_updates["match_datetime"]
            if not state.venue and fixture_updates.get("venue"):
                state.venue = fixture_updates["venue"]
            if fixture_updates.get("source_url"):
                state.fixture_context["source_url"] = fixture_updates["source_url"]

    def _extract_fixture_updates(self, fixture_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        updates: Dict[str, Any] = {}
        for item in fixture_results or []:
            text = " ".join(
                str(item.get(key) or "")
                for key in ("title", "content", "url")
            )
            if not updates.get("venue"):
                venue = self._extract_venue_from_text(text)
                if venue:
                    updates["venue"] = venue
            if not updates.get("match_datetime"):
                match_datetime = self._extract_datetime_from_text(text)
                if match_datetime:
                    updates["match_datetime"] = match_datetime
            if not updates.get("source_url") and item.get("url"):
                updates["source_url"] = item["url"]
            if updates.get("venue") and updates.get("match_datetime"):
                break
        if updates:
            updates["status"] = "accepted"
            updates["source"] = "exa"
        return updates

    def _extract_venue_from_text(self, text: str) -> str:
        known_venues = (
            "Los Angeles Stadium",
            "Guadalajara Stadium",
            "Estadio Akron",
            "Akron Stadium",
            "Puskas Arena",
            "Stadium of Light",
        )
        lower = text.lower()
        for venue in known_venues:
            if venue.lower() in lower:
                return venue
        match = re.search(r"\b([A-Z][A-Za-z .'-]{2,50}\s(?:Stadium|Arena))\b", text)
        return match.group(1).strip() if match else ""

    def _extract_datetime_from_text(self, text: str) -> str:
        month_lookup = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }
        utc_match = re.search(
            r"\b(\d{1,2}):(\d{2})\s+(?:UTC\s*)?(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b",
            text,
            flags=re.I,
        )
        if utc_match:
            hour, minute, day, month_name, year = utc_match.groups()
            month = month_lookup.get(month_name.lower())
            if month:
                return datetime(
                    int(year),
                    month,
                    int(day),
                    int(hour),
                    int(minute),
                    tzinfo=timezone.utc,
                ).isoformat()
        local_match = re.search(
            r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*(AM|PM)\b",
            text,
            flags=re.I,
        )
        if local_match:
            month_name, day, year, hour, minute, meridiem = local_match.groups()
            month = month_lookup.get(month_name.lower())
            if month:
                hour_int = int(hour)
                if meridiem.lower() == "pm" and hour_int != 12:
                    hour_int += 12
                if meridiem.lower() == "am" and hour_int == 12:
                    hour_int = 0
                return datetime(int(year), month, int(day), hour_int, int(minute)).isoformat()
        return ""

    def _beats_payload(self, notes_store: Any) -> List[Dict[str, Any]]:
        beats_payload = []
        for beat in getattr(notes_store, "beats", []) or []:
            if hasattr(beat, "to_dict"):
                beats_payload.append(beat.to_dict())
            else:
                beats_payload.append({
                    "source": getattr(beat, "source", ""),
                    "source_urls": getattr(beat, "source_urls", []),
                    "source_attribution": getattr(beat, "source_attribution", []),
                })
        return beats_payload

    def _build_quality_report(self, state: CommentaryNotesState, notes_store: Any) -> Dict[str, Any]:
        from quality.notes_quality import score_notes

        beats_payload = self._beats_payload(notes_store)
        quality_score = score_notes(
            getattr(notes_store, "raw_markdown", "") or "",
            {"beats": beats_payload, "quality_report": state.quality_report},
        ).to_dict()
        return {
            "warnings_count": len(state.warnings),
            "errors_count": len(state.errors),
            "beat_count": len(getattr(notes_store, "beats", []) or []),
            "markdown_chars": len(getattr(notes_store, "raw_markdown", "") or ""),
            "has_structured_lookup": bool(getattr(notes_store, "lookup", None)),
            "professional_score": quality_score,
        }

    def _build_vlm_context(self, notes_store: Any, max_chars: int = 12000) -> Dict[str, Any]:
        return {
            "notes_version": 0,
            "vlm_context_version": 0,
            "markdown_context": getattr(notes_store, "raw_markdown", "")[:max_chars],
            "beat_count": len(getattr(notes_store, "beats", []) or []),
            "lookup_tags": sorted((getattr(notes_store, "lookup", {}) or {}).keys()),
        }

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
            "competition": state.competition,
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
        """Execute the production notes workflow through LangGraph."""
        if not use_langgraph:
            raise ValueError("Commentary notes generation is LangGraph-only in production.")

        logger.info("Starting commentary notes workflow through LangGraph...")
        self._progress_callback = on_progress
        graph = build_langgraph(self)
        if graph is None:
            raise RuntimeError("LangGraph is required for commentary notes generation.")
        result = await graph.ainvoke(state)
        completed = _coerce_commentary_state(result)
        await self._emit("complete", "LangGraph notes workflow complete", done=True)
        logger.info(f"Workflow complete: {self.get_status(completed)}")
        return completed


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
    graph.add_node("parallel_research", runner.parallel_research)
    graph.add_node("targeted_evidence_search", runner.targeted_evidence_search)
    graph.add_node("matchup_analysis", runner.analyze_matchups)
    graph.add_node("enrich_context", runner.enrich_context)
    graph.add_node("synthesize", runner.synthesize_notes)
    graph.add_node("evaluate_notes", runner.evaluate_notes)
    graph.add_node("revise_notes", runner.revise_notes)

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "parallel_research")
    graph.add_edge("parallel_research", "targeted_evidence_search")
    graph.add_edge("targeted_evidence_search", "matchup_analysis")
    graph.add_edge("matchup_analysis", "enrich_context")
    graph.add_edge("enrich_context", "synthesize")
    graph.add_edge("synthesize", "evaluate_notes")
    graph.add_conditional_edges(
        "evaluate_notes",
        _route_notes_revision,
        {
            "revise_notes": "revise_notes",
            "end": END,
        },
    )
    graph.add_edge("revise_notes", "evaluate_notes")

    return graph.compile()


def _route_notes_revision(state: Any) -> str:
    if isinstance(state, dict):
        evaluation = state.get("notes_evaluation") or {}
        revision_count = int(state.get("revision_count") or 0)
    else:
        evaluation = getattr(state, "notes_evaluation", {}) or {}
        revision_count = int(getattr(state, "revision_count", 0) or 0)
    if evaluation.get("needs_revision") and revision_count < 2:
        return "revise_notes"
    return "end"
