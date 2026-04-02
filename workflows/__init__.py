"""
Workflows module - LangGraph + CrewAI orchestration for commentary notes preparation.

Provides:
- LangGraph state machine for workflow orchestration
- CrewAI task definitions and agent roles
- Bridge to existing WorkflowOrchestrator for concurrency control
- Configuration for commentary notes generation
"""

from workflows.commentary_notes_workflow import (
    CommentaryNotesWorkflow,
    CommentaryNotesState,
    WorkflowPhase,
    create_workflow,
)
from workflows.crewai_config import (
    CREW_CONFIG,
    TASKS,
    PLAYER_RESEARCH_AGENT,
    TEAM_FORM_AGENT,
    HISTORICAL_CONTEXT_AGENT,
    WEATHER_CONTEXT_AGENT,
    MATCHUP_ANALYSIS_AGENT,
    NEWS_AGENT,
    NOTE_ORGANIZER_AGENT,
)
from workflows.orchestration_bridge import OrchestratorBridge

__all__ = [
    # Workflow
    "CommentaryNotesWorkflow",
    "CommentaryNotesState",
    "WorkflowPhase",
    "create_workflow",
    # CrewAI
    "CREW_CONFIG",
    "TASKS",
    "PLAYER_RESEARCH_AGENT",
    "TEAM_FORM_AGENT",
    "HISTORICAL_CONTEXT_AGENT",
    "WEATHER_CONTEXT_AGENT",
    "MATCHUP_ANALYSIS_AGENT",
    "NEWS_AGENT",
    "NOTE_ORGANIZER_AGENT",
    # Bridge
    "OrchestratorBridge",
]
