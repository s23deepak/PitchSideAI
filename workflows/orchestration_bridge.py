"""
Orchestration Bridge - Connect CrewAI to existing WorkflowOrchestrator.

Provides adapters to submit CrewAI tasks to the existing orchestration system
for concurrency control, rate limiting, and distributed execution.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from orchestration.engine import get_orchestrator
from orchestration.types import WorkflowContext, AgentType
from workflows.commentary_notes_workflow import CommentaryNotesState

logger = logging.getLogger(__name__)


class OrchestratorBridge:
    """Bridge between CrewAI tasks and WorkflowOrchestrator."""

    def __init__(self, orchestrator=None):
        """
        Initialize bridge.

        Args:
            orchestrator: Optional WorkflowOrchestrator instance
        """
        self.orchestrator = orchestrator or get_orchestrator()

    async def submit_agent_task(
        self,
        task_name: str,
        agent_type: str,
        action: str,
        payload: Dict[str, Any],
        priority: int = 0,
        workflow_id: str = "commentary_workflow",
    ) -> str:
        """
        Submit an agent task to orchestrator.

        Args:
            task_name: Name of task
            agent_type: Type of agent (from AgentType enum)
            action: Action to perform
            payload: Task payload
            priority: Priority level (higher = more urgent)
            workflow_id: Registered workflow ID to submit under

        Returns:
            Task ID for tracking
        """
        task_id = await self.orchestrator.submit_task(
            workflow_id=workflow_id,
            agent_type=agent_type,
            action=action,
            payload=payload,
            priority=priority,
        )

        logger.info(f"Task {task_name} ({task_id}) submitted to orchestrator")
        return task_id

    async def wait_for_task(self, task_id: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Wait for task completion and retrieve result.

        Args:
            task_id: Task ID to wait for
            timeout_seconds: Maximum wait time

        Returns:
            Task result
        """
        start_time = datetime.utcnow()
        poll_interval = 0.5  # seconds

        while True:
            result = self.orchestrator.get_task_result(task_id)
            if result:
                return result

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise TimeoutError(f"Task {task_id} timeout after {timeout_seconds}s")

            await asyncio.sleep(poll_interval)

    async def execute_parallel_tasks(
        self,
        tasks: List[Dict[str, Any]],
        max_concurrent: int = 5,
        workflow_id: str = "commentary_workflow",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute multiple tasks in parallel with concurrency limits.

        Args:
            tasks: List of task definitions
            max_concurrent: Max concurrent tasks
            workflow_id: Registered workflow ID to submit tasks under

        Returns:
            Dictionary of task_id -> result
        """
        task_ids = []

        # Submit all tasks
        for task in tasks:
            task_id = await self.submit_agent_task(
                task_name=task.get("name"),
                agent_type=task.get("agent_type"),
                action=task.get("action"),
                payload=task.get("payload"),
                priority=task.get("priority", 0),
                workflow_id=workflow_id,
            )
            task_ids.append(task_id)

        # Wait for all with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_wait(task_id: str) -> tuple:
            async with semaphore:
                result = await self.wait_for_task(task_id)
                return task_id, result

        results = await asyncio.gather(
            *[bounded_wait(task_id) for task_id in task_ids],
            return_exceptions=True,
        )

        # Convert to dictionary
        result_dict = {}
        for task_id, result in results:
            if isinstance(result, Exception):
                logger.error(f"Task {task_id} failed: {result}")
                result_dict[task_id] = {"error": str(result)}
            else:
                result_dict[task_id] = result

        return result_dict

    async def execute_workflow(
        self,
        workflow_state: CommentaryNotesState,
    ) -> CommentaryNotesState:
        """
        Execute full commentary workflow through orchestrator.

        Args:
            workflow_state: Workflow state

        Returns:
            Updated workflow state with results
        """
        logger.info(f"Starting orchestrated workflow for {workflow_state.match_id}")

        # Register the workflow with the orchestrator so task submissions can find it
        context = WorkflowContext(
            match_id=workflow_state.match_id,
            home_team=workflow_state.home_team,
            away_team=workflow_state.away_team,
            sport=workflow_state.sport,
        )
        workflow_id = await self.orchestrator.start_workflow(context)
        workflow_state.workflow_id = workflow_id

        # Phase 1: Parallel initial context gathering
        initial_tasks = [
            {
                "name": "gather_news",
                "agent_type": "commentary",
                "action": "gather_news",
                "payload": {
                    "home_team": workflow_state.home_team,
                    "away_team": workflow_state.away_team,
                },
                "priority": 2,
            },
            {
                "name": "analyze_weather",
                "agent_type": "commentary",
                "action": "analyze_weather",
                "payload": {
                    "venue": workflow_state.venue,
                    "latitude": workflow_state.venue_lat,
                    "longitude": workflow_state.venue_lon,
                    "match_datetime": workflow_state.match_datetime,
                },
                "priority": 2,
            },
            {
                "name": "historical_context",
                "agent_type": "commentary",
                "action": "build_narrative",
                "payload": {
                    "home_team": workflow_state.home_team,
                    "away_team": workflow_state.away_team,
                },
                "priority": 2,
            },
        ]

        initial_results = await self.execute_parallel_tasks(
            initial_tasks, max_concurrent=3, workflow_id=workflow_id
        )

        # Extract results
        if "gather_news" in initial_results:
            workflow_state.team_news = initial_results["gather_news"].get("data", {})
        if "analyze_weather" in initial_results:
            workflow_state.weather_context = initial_results["analyze_weather"].get("data", {})
        if "historical_context" in initial_results:
            workflow_state.historical_context = initial_results["historical_context"].get(
                "data", {}
            )

        logger.info("Initial context gathering complete")

        # Phase 2: Squad research
        squad_tasks = [
            {
                "name": "research_home_squad",
                "agent_type": "research",
                "action": "research_squad",
                "payload": {"team_name": workflow_state.home_team},
                "priority": 1,
            },
            {
                "name": "research_away_squad",
                "agent_type": "research",
                "action": "research_squad",
                "payload": {"team_name": workflow_state.away_team},
                "priority": 1,
            },
        ]

        squad_results = await self.execute_parallel_tasks(
            squad_tasks, max_concurrent=2, workflow_id=workflow_id
        )

        # Extract results
        workflow_state.player_research = {
            "home_team": squad_results.get("research_home_squad", {}).get("data", {}),
            "away_team": squad_results.get("research_away_squad", {}).get("data", {}),
        }

        logger.info("Squad research complete")

        # Phase 3: Form analysis
        form_tasks = [
            {
                "name": "analyze_form_home",
                "agent_type": "research",
                "action": "analyze_form",
                "payload": {"team_name": workflow_state.home_team},
                "priority": 1,
            },
            {
                "name": "analyze_form_away",
                "agent_type": "research",
                "action": "analyze_form",
                "payload": {"team_name": workflow_state.away_team},
                "priority": 1,
            },
        ]

        form_results = await self.execute_parallel_tasks(
            form_tasks, max_concurrent=2, workflow_id=workflow_id
        )

        workflow_state.team_form = {
            "home_team": form_results.get("analyze_form_home", {}).get("data", {}),
            "away_team": form_results.get("analyze_form_away", {}).get("data", {}),
        }

        logger.info("Form analysis complete")

        # Phase 4: Matchup analysis
        matchup_task = {
            "name": "analyze_matchups",
            "agent_type": "vision",
            "action": "analyze_matchups",
            "payload": {
                "home_squad": workflow_state.player_research.get("home_team", {}),
                "away_squad": workflow_state.player_research.get("away_team", {}),
            },
            "priority": 1,
        }

        matchup_result = await self.wait_for_task(
            await self.submit_agent_task(
                task_name="analyze_matchups",
                agent_type="vision",
                action="analyze_matchups",
                payload=matchup_task["payload"],
                workflow_id=workflow_id,
            )
        )

        workflow_state.matchup_analysis = matchup_result.get("data", {})

        logger.info("Matchup analysis complete")

        # Phase 5: Note synthesis (final)
        synthesis_result = await self.wait_for_task(
            await self.submit_agent_task(
                task_name="synthesize_notes",
                agent_type="commentary",
                action="synthesize",
                payload={
                    "all_outputs": {
                        "home_team": workflow_state.home_team,
                        "away_team": workflow_state.away_team,
                        "player_research": workflow_state.player_research,
                        "team_form": workflow_state.team_form,
                        "historical": workflow_state.historical_context,
                        "weather": workflow_state.weather_context,
                        "matchups": workflow_state.matchup_analysis,
                        "news": workflow_state.team_news,
                    }
                },
                workflow_id=workflow_id,
            )
        )

        workflow_state.markdown_notes = synthesis_result.get("markdown", "")
        workflow_state.json_structure = synthesis_result.get("json", {})
        workflow_state.end_time = datetime.utcnow()

        logger.info(f"Workflow complete for {workflow_state.match_id}")

        return workflow_state
