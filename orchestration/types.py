"""
Type definitions for agent orchestration.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


class AgentType(str, Enum):
    """Types of agents in the system."""
    RESEARCH = "research"
    VISION = "vision"
    LIVE = "live"
    COMMENTARY = "commentary"
    TACTICAL = "tactical"


class WorkflowState(str, Enum):
    """Workflow execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class AgentMessage:
    """Message structure for inter-agent communication."""
    sender: AgentType
    receiver: Optional[AgentType] = None
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = 0  # Higher = more urgent


@dataclass
class WorkflowContext:
    """Context passed through workflow execution."""
    match_id: str
    home_team: str
    away_team: str
    sport: str = "soccer"
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # State accumulated during workflow
    match_brief: Optional[str] = None
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    tactical_detections: List[Dict[str, Any]] = field(default_factory=list)
    rag_context: Optional[str] = None

    # Execution metadata
    state: WorkflowState = WorkflowState.PENDING
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    agent: AgentType
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    retry_count: int = 0
