"""
Orchestration layer for multi-agent workflows.

Entry point for running commentary notes workflows with:
- WorkflowOrchestrator (engine.py) — primary orchestrator
- OrchestratorBridge (workflows/) — bridge to LangGraph workflows
- AgentType / WorkflowContext / TaskResult (types.py) — shared types
"""

from orchestration.engine import WorkflowOrchestrator, get_orchestrator
from orchestration.types import AgentType, WorkflowContext, WorkflowState, TaskResult, AgentMessage

__all__ = [
    "WorkflowOrchestrator",
    "get_orchestrator",
    "AgentType",
    "WorkflowContext",
    "WorkflowState",
    "TaskResult",
    "AgentMessage",
]