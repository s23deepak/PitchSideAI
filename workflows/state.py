"""Canonical workflow state dataclass — re-exports from the workflow module."""

from workflows.commentary_notes_workflow import CommentaryNotesState, WorkflowPhase

__all__ = ["CommentaryNotesState", "WorkflowPhase"]