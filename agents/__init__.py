"""
Agent Package — Multi-agent system for PitchSideAI.

Provides specialized agents for sports analysis:
- ResearchAgent: Pre-match research and live Q&A
- VisionAgent: Real-time frame analysis and tactical recognition
- LiveAgent: Live match interaction and commentary
- CommentaryAgent: Match commentary and analysis
- AgentCoordinator: Multi-agent orchestration for Track 1 hackathon
- QAAgent: Story 2.2 Q&A Backend Answer Generation
- PlayerIDAgent: Story 2.4 Player Identification for Q&A

All agents support dynamic sport types (Soccer, Cricket, Basketball, etc.)
"""
from .base import BaseAgent
from .research_agent import ResearchAgent
from .vision_agent import VisionAgent
from .commentary_agent import CommentaryAgent
from .live_agent import LiveAgent
from .coordinator import AgentCoordinator, CoordinationContext
from .qa_agent import QAAgent, QAPair, VisionTacticalContext
from .player_id_agent import PlayerIDAgent, PlayerIdentification

__all__ = [
    "BaseAgent",
    "ResearchAgent",
    "VisionAgent",
    "CommentaryAgent",
    "LiveAgent",
    "AgentCoordinator",
    "CoordinationContext",
    "QAAgent",
    "QAPair",
    "VisionTacticalContext",
    "PlayerIDAgent",
    "PlayerIdentification",
]

