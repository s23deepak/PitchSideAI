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

_LAZY_EXPORTS = {
    "ResearchAgent": (".research_agent", "ResearchAgent"),
    "VisionAgent": (".vision_agent", "VisionAgent"),
    "CommentaryAgent": (".commentary_agent", "CommentaryAgent"),
    "LiveAgent": (".live_agent", "LiveAgent"),
    "AgentCoordinator": (".coordinator", "AgentCoordinator"),
    "CoordinationContext": (".coordinator", "CoordinationContext"),
    "QAAgent": (".qa_agent", "QAAgent"),
    "QAPair": (".qa_agent", "QAPair"),
    "VisionTacticalContext": (".qa_agent", "VisionTacticalContext"),
    "PlayerIDAgent": (".player_id_agent", "PlayerIDAgent"),
    "PlayerIdentification": (".player_id_agent", "PlayerIdentification"),
}


def __getattr__(name):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'agents' has no attribute {name!r}")
    from importlib import import_module

    module_name, attr_name = _LAZY_EXPORTS[name]
    attr = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = attr
    return attr

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

