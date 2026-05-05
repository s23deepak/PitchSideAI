"""
Agent Package — Multi-agent system for PitchSide AI.

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
from agents.base import BaseAgent
from agents.research_agent import ResearchAgent
from agents.vision_agent import VisionAgent
from agents.commentary_agent import CommentaryAgent
from agents.live_agent import LiveAgent
from agents.coordinator import AgentCoordinator, CoordinationContext
from agents.qa_agent import QAAgent, QAPair
from agents.player_id_agent import PlayerIDAgent, PlayerIdentification

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
    "PlayerIDAgent",
    "PlayerIdentification",
]


