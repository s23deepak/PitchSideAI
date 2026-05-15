"""
Workflows module - production notes workflow orchestration.

Provides:
- LangGraph state machine for workflow orchestration
- Bridge to existing WorkflowOrchestrator for concurrency control
- Configuration for commentary notes generation
"""

from workflows.commentary_notes_workflow import (
    CommentaryNotesWorkflow,
    CommentaryNotesState,
    WorkflowPhase,
    build_langgraph,
    create_workflow,
)
from workflows.orchestration_bridge import OrchestratorBridge

__all__ = [
    # Workflow
    "CommentaryNotesWorkflow",
    "CommentaryNotesState",
    "WorkflowPhase",
    "build_langgraph",
    "create_workflow",
    # Bridge
    "OrchestratorBridge",
]
