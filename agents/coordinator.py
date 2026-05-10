"""
Agent Coordinator for Track 1: AI Agents & Agentic Workflows.

Orchestrates the 7 specialized commentary agents with:
- Parallel agent execution for independent research
- Sequential synthesis for commentary generation
- Streaming-aware context injection
- Agent-to-agent handoff protocols
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import asyncio
import logging
import time

logger = logging.getLogger("pitchsideai.agents.coordinator")


# ── Agent Coordination Types ─────────────────────────────────────────────────

@dataclass
class AgentTask:
    """A unit of work for a single agent."""
    agent_name: str
    task_description: str
    dependencies: List[str] = field(default_factory=list)
    priority: int = 5  # 1-10, lower = higher priority
    timeout_seconds: float = 30.0


@dataclass
class AgentResult:
    """Result from an agent task execution."""
    agent_name: str
    output: Dict[str, Any]
    latency_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class CoordinationContext:
    """Shared context passed between agents during coordination."""
    home_team: str
    away_team: str
    sport: str
    match_session: str
    venue: Optional[str] = None
    game_state: Optional[Dict[str, Any]] = None
    streaming_context: Optional[str] = None  # Latest streaming vision output
    previous_commentary: List[str] = field(default_factory=list)
    research_cache: Dict[str, Any] = field(default_factory=dict)


# ── Agent Coordinator ────────────────────────────────────────────────────────

class AgentCoordinator:
    """
    Coordinates the 7-agent commentary system with streaming awareness.

    Agents:
    1. PlayerResearch - squad info, key players, stats
    2. TeamForm - recent form, results, momentum
    3. HistoricalContext - rivalry history, past meetings
    4. WeatherContext - weather impact on play
    5. MatchupAnalysis - tactical comparison, formations
    6. NewsAgent - latest team news, injuries, transfers
    7. NoteOrganizer - synthesize all research into commentary brief

    The coordinator handles:
    - Agent-to-agent communication
    - Parallel execution of independent agents
    - Streaming context injection
    - Fallback and retry logic
    """

    def __init__(self, sport: str = "football", use_remote_agents: bool = False):
        self.sport = sport
        self.use_remote_agents = use_remote_agents
        self._agents: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Lazy-load all agents."""
        if self._initialized:
            return

        from agents.specialized_commentary.player_research_agent import PlayerResearchAgent
        from agents.specialized_commentary.team_form_agent import TeamFormAgent
        from agents.specialized_commentary.historical_context_agent import HistoricalContextAgent
        from agents.specialized_commentary.weather_context_agent import WeatherContextAgent
        from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent
        from agents.specialized_commentary.news_agent import NewsAgent
        from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent

        self._agents = {
            "player_research": PlayerResearchAgent(sport=self.sport),
            "team_form": TeamFormAgent(sport=self.sport),
            "historical_context": HistoricalContextAgent(sport=self.sport),
            "weather": WeatherContextAgent(sport=self.sport),
            "matchup": MatchupAnalysisAgent(sport=self.sport),
            "news": NewsAgent(sport=self.sport),
            "organizer": CommentaryNoteOrganizerAgent(sport=self.sport),
        }
        self._initialized = True
        logger.info(f"AgentCoordinator initialized with {len(self._agents)} agents")

    async def run_parallel_phase(
        self,
        phase_name: str,
        tasks: List[AgentTask],
        context: CoordinationContext,
    ) -> Dict[str, AgentResult]:
        """Run multiple agents in parallel with dependency ordering."""
        await self.initialize()

        # Group by dependency level
        results: Dict[str, AgentResult] = {}
        pending = list(tasks)

        while pending:
            ready = [
                t for t in pending
                if all(dep in results for dep in t.dependencies)
            ]
            if not ready:
                if pending:
                    logger.warning(f"Deadlock detected in {phase_name}, running all")
                    ready = pending
                else:
                    break

            batch_tasks = [self._run_single_agent(t, context) for t in ready]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for task, result in zip(ready, batch_results):
                if isinstance(result, Exception):
                    results[task.agent_name] = AgentResult(
                        agent_name=task.agent_name,
                        output={},
                        latency_ms=0,
                        success=False,
                        error=str(result),
                    )
                else:
                    results[task.agent_name] = result
                    if result.success and result.output:
                        context.research_cache[task.agent_name] = result.output

            pending = [t for t in pending if t.agent_name not in results]

        return results

    async def _run_single_agent(self, task: AgentTask, context: CoordinationContext) -> AgentResult:
        """Execute a single agent task with timeout."""
        agent = self._agents.get(task.agent_name)
        if not agent:
            return AgentResult(
                agent_name=task.agent_name, output={},
                latency_ms=0, success=False,
                error=f"Agent {task.agent_name} not found",
            )

        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                agent.execute(task.task_description),
                timeout=task.timeout_seconds,
            )
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"{task.agent_name} completed in {elapsed:.0f}ms")
            return AgentResult(
                agent_name=task.agent_name,
                output=result if isinstance(result, dict) else {"result": result},
                latency_ms=elapsed,
                success=True,
            )
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            return AgentResult(
                agent_name=task.agent_name, output={},
                latency_ms=elapsed, success=False,
                error=f"Timeout after {task.timeout_seconds}s",
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return AgentResult(
                agent_name=task.agent_name, output={},
                latency_ms=elapsed, success=False,
                error=str(exc),
            )

    async def build_match_brief(
        self,
        home_team: str,
        away_team: str,
        venue: Optional[str] = None,
        streaming_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a complete match research brief using all agents.

        Phase 1 (Parallel): PlayerResearch, TeamForm, Weather, News
        Phase 2 (Sequential): HistoricalContext, MatchupAnalysis
        Phase 3 (Synthesis): NoteOrganizer
        """
        context = CoordinationContext(
            home_team=home_team,
            away_team=away_team,
            sport=self.sport,
            match_session=f"{home_team}_{away_team}",
            venue=venue,
            streaming_context=streaming_context,
        )

        # Phase 1: Parallel research
        phase1_tasks = [
            AgentTask("player_research", f"Research key players for {home_team} vs {away_team}"),
            AgentTask("team_form", f"Analyze recent form for {home_team} and {away_team}"),
        ]
        if venue:
            phase1_tasks.append(
                AgentTask("weather", f"Get weather conditions at {venue}"),
            )
        phase1_tasks.append(
            AgentTask("news", f"Get latest team news for {home_team} and {away_team}"),
        )

        phase1_results = await self.run_parallel_phase("phase1_research", phase1_tasks, context)

        # Phase 2: Contextual analysis (depends on phase 1)
        phase2_tasks = [
            AgentTask(
                "historical_context",
                f"Analyze historical rivalry between {home_team} and {away_team}",
                dependencies=["player_research"],
            ),
            AgentTask(
                "matchup",
                f"Tactical comparison: {home_team} vs {away_team}",
                dependencies=["player_research", "team_form"],
            ),
        ]
        phase2_results = await self.run_parallel_phase("phase2_analysis", phase2_tasks, context)

        # Phase 3: Synthesis
        organizer = self._agents.get("organizer")
        synthesis_input = {
            "home_team": home_team,
            "away_team": away_team,
            "sport": self.sport,
            "venue": venue,
            "player_research": context.research_cache.get("player_research"),
            "team_form": context.research_cache.get("team_form"),
            "historical_context": context.research_cache.get("historical_context"),
            "weather": context.research_cache.get("weather"),
            "matchup": context.research_cache.get("matchup"),
            "news": context.research_cache.get("news"),
            "streaming_context": streaming_context,
        }

        notes = {}
        if organizer:
            try:
                notes = await organizer.execute(synthesis_input)
            except Exception as exc:
                logger.error("organizer_failed", error=str(exc))

        # Collect timings
        all_results = {**phase1_results, **phase2_results}
        timings = {
            name: r.latency_ms for name, r in all_results.items()
        }
        errors = [r.error for r in all_results.values() if not r.success]

        return {
            "match_brief": notes.get("markdown_notes", notes.get("result", "")),
            "agent_timings": timings,
            "errors": errors,
            "agents_succeeded": len([r for r in all_results.values() if r.success]),
            "agents_total": len(all_results),
            "streaming_context_included": streaming_context is not None,
        }

    async def generate_streaming_commentary(
        self,
        streaming_result: Dict[str, Any],
        context: CoordinationContext,
    ) -> str:
        """
        Generate enhanced commentary by combining streaming vision output
        with agent research context.

        This is the key Track 1 innovation: multi-agent commentary that
        incorporates real-time streaming video understanding.
        """
        await self.initialize()

        organizer = self._agents.get("organizer")
        if not organizer:
            return streaming_result.get("commentary", "")

        tactical_label = streaming_result.get("tactical_label", "Open Play")
        key_obs = streaming_result.get("key_observation", "")

        # Inject research context into commentary
        research_highlights = []
        if context.research_cache.get("player_research"):
            research_highlights.append("Player data available")
        if context.research_cache.get("team_form"):
            research_highlights.append("Form data available")
        if context.research_cache.get("historical_context"):
            research_highlights.append("Historical context available")

        prompt = {
            "task": "enhance_commentary",
            "base_commentary": streaming_result.get("commentary", ""),
            "tactical_label": tactical_label,
            "key_observation": key_obs,
            "research_context": "\n".join(research_highlights),
            "home_team": context.home_team,
            "away_team": context.away_team,
            "previous_commentary": context.previous_commentary[-3:],
        }

        try:
            result = await organizer.execute(prompt)
            enhanced = result.get("commentary") or result.get("result") or streaming_result.get("commentary", "")
            return enhanced
        except Exception as exc:
            logger.error("enhance_commentary_failed", error=str(exc))
            return streaming_result.get("commentary", "")

    async def handle_agent_handoff(
        self,
        from_agent: str,
        to_agent: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Agent-to-agent handoff protocol. Allows agents to delegate sub-tasks
        to each other, demonstrating agentic workflow coordination.
        """
        target = self._agents.get(to_agent)
        if not target:
            return {"error": f"Agent {to_agent} not found", "success": False}

        handoff_prompt = f"[Handoff from {from_agent}] {payload}"
        try:
            result = await target.execute(handoff_prompt)
            return {"result": result, "success": True}
        except Exception as exc:
            return {"error": str(exc), "success": False}

    def get_registered_agents(self) -> List[str]:
        return list(self._agents.keys()) if self._initialized else []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "agents_registered": self.get_registered_agents(),
            "initialized": self._initialized,
            "use_remote_agents": self.use_remote_agents,
        }