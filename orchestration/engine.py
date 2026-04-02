"""
Main orchestration engine for managing multi-agent workflows.
Implements state management, routing, and concurrency control.
"""
import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict

from orchestration.types import (
    WorkflowContext,
    AgentType,
    WorkflowState,
    TaskResult,
    AgentMessage
)

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Manages multi-agent workflows with:
    - State management
    - Agent routing
    - Concurrency control
    - Error handling and retries
    """

    def __init__(self, max_concurrent_tasks: int = 10, request_timeout: int = 300):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.request_timeout = request_timeout

        # Workflow tracking
        self.workflows: Dict[str, WorkflowContext] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.results: Dict[str, TaskResult] = {}

        # Agent handlers registry
        self.agent_handlers: Dict[AgentType, Callable] = {}

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.active_tasks: Dict[str, asyncio.Task] = {}

        # Message routing
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.message_handlers: Dict[str, List[Callable]] = defaultdict(list)

    def register_agent_handler(self, agent_type: AgentType, handler: Callable) -> None:
        """Register a handler function for an agent type."""
        self.agent_handlers[agent_type] = handler
        logger.info(f"Registered handler for {agent_type.value}")

    def register_message_handler(self, message_type: str, handler: Callable) -> None:
        """Register a handler for a specific message type."""
        self.message_handlers[message_type].append(handler)

    async def start_workflow(self, context: WorkflowContext) -> str:
        """
        Start a new workflow for a match session.
        Returns workflow ID.
        """
        workflow_id = str(uuid.uuid4())
        context.state = WorkflowState.RUNNING
        context.start_time = datetime.utcnow()

        self.workflows[workflow_id] = context
        logger.info(f"Started workflow {workflow_id} for {context.home_team} vs {context.away_team}")

        return workflow_id

    async def submit_task(
        self,
        workflow_id: str,
        agent_type,
        action: str,
        payload: Dict[str, Any],
        priority: int = 0
    ) -> str:
        """Submit a task to be executed by an agent."""
        task_id = str(uuid.uuid4())

        # Accept strings as well as AgentType enum values
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)

        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        message = AgentMessage(
            sender=AgentType.LIVE,  # System as sender
            receiver=agent_type,
            action=action,
            payload={**payload, "workflow_id": workflow_id, "task_id": task_id},
            priority=priority
        )

        # Add to priority queue (simulated via list)
        await self.task_queue.put((priority, task_id, message))
        logger.debug(f"Submitted task {task_id} to agent {agent_type.value}")

        return task_id

    async def execute_task(self, task_id: str, message: AgentMessage) -> TaskResult:
        """Execute a single task with proper concurrency control."""
        async with self.semaphore:  # Limit concurrent execution
            workflow_id = message.payload.get("workflow_id")
            workflow = self.workflows.get(workflow_id)

            if not workflow:
                return TaskResult(
                    task_id=task_id,
                    agent=message.receiver,
                    success=False,
                    error="Workflow not found"
                )

            start_time = datetime.utcnow()
            result = TaskResult(task_id=task_id, agent=message.receiver, success=False)

            try:
                # Get handler for agent
                handler = self.agent_handlers.get(message.receiver)
                if not handler:
                    raise ValueError(f"No handler for agent {message.receiver.value}")

                # Execute with timeout
                task_coro = handler(workflow, message.action, message.payload)
                data = await asyncio.wait_for(task_coro, timeout=self.request_timeout)

                result.success = True
                result.data = data

            except asyncio.TimeoutError:
                workflow.state = WorkflowState.TIMEOUT
                result.error = f"Task timeout after {self.request_timeout}s"
                logger.warning(f"Task {task_id} timed out")

            except Exception as exc:
                result.error = str(exc)
                workflow.errors.append(str(exc))
                logger.error(f"Task {task_id} failed: {exc}")

            finally:
                result.execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self.results[task_id] = result

            return result

    async def process_task_queue(self) -> None:
        """Worker that processes tasks from the queue."""
        while True:
            try:
                priority, task_id, message = await self.task_queue.get()
                task = asyncio.create_task(self.execute_task(task_id, message))
                self.active_tasks[task_id] = task
                task.add_done_callback(lambda t: self.active_tasks.pop(task_id, None))

            except Exception as exc:
                logger.error(f"Error processing task: {exc}")

    async def route_message(self, message: AgentMessage) -> None:
        """Route a message to registered handlers."""
        handlers = self.message_handlers.get(message.action, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as exc:
                logger.error(f"Message handler error: {exc}")

    def get_workflow_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """Get the context of a workflow."""
        return self.workflows.get(workflow_id)

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a task."""
        return self.results.get(task_id)

    async def finalize_workflow(self, workflow_id: str, success: bool = True) -> None:
        """Mark workflow as completed."""
        workflow = self.workflows.get(workflow_id)
        if workflow:
            workflow.state = WorkflowState.COMPLETED if success else WorkflowState.FAILED
            workflow.end_time = datetime.utcnow()
            logger.info(f"Workflow {workflow_id} finalized with state {workflow.state}")

    async def get_active_tasks_count(self) -> int:
        """Get count of currently active tasks."""
        return len(self.active_tasks)


# Global orchestrator instance
_orchestrator: Optional[WorkflowOrchestrator] = None


def get_orchestrator(max_concurrent: int = 10) -> WorkflowOrchestrator:
    """Get or create the global orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator(max_concurrent_tasks=max_concurrent)
    return _orchestrator
