"""
Workflows module - production notes workflow orchestration.

Provides:
- LangGraph state machine for workflow orchestration
- Bridge to existing WorkflowOrchestrator for concurrency control
- Configuration for commentary notes generation
- Retrieval audit summary builder
"""

from workflows.commentary_notes_workflow import (
    CommentaryNotesWorkflow,
    CommentaryNotesState,
    WorkflowPhase,
    build_langgraph,
    create_workflow,
)
from workflows.live_notes_patch_workflow import LiveNotesPatchState, LiveNotesPatchWorkflow
from workflows.orchestration_bridge import OrchestratorBridge
from workflows.retrieval_summary import build_retrieval_summary
from workflows.state import CommentaryNotesState as StateCommentaryNotesState

__all__ = [
    # Workflow
    "CommentaryNotesWorkflow",
    "CommentaryNotesState",
    "WorkflowPhase",
    "build_langgraph",
    "create_workflow",
    "LiveNotesPatchState",
    "LiveNotesPatchWorkflow",
    # Bridge
    "OrchestratorBridge",
    # Retrieval
    "build_retrieval_summary",
    # State (standalone re-export)
    "StateCommentaryNotesState",
]
