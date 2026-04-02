"""
Agent Package — Multi-agent system for PitchSide AI.

Provides specialized agents for sports analysis:
- ResearchAgent: Pre-match research and live Q&A
- VisionAgent: Real-time frame analysis and tactical recognition
- LiveAgent: Live match interaction and commentary
- CommentaryAgent: Match commentary and analysis

All agents support dynamic sport types (Soccer, Cricket, Basketball, etc.)
"""
from agents.base import BaseAgent
from agents.research_agent import ResearchAgent
from agents.vision_agent import VisionAgent
from agents.commentary_agent import CommentaryAgent
from agents.live_agent import LiveAgent

__all__ = [
    "BaseAgent",
    "ResearchAgent",
    "VisionAgent",
    "CommentaryAgent",
    "LiveAgent",
]


