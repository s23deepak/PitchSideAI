"""
Agent Package — Multi-agent system for PitchSideAI.

Provides specialized agents for sports analysis:
- ResearchAgent: Pre-match research and live Q&A
- VisionAgent: Real-time frame analysis and tactical recognition
- LiveAgent: Live match interaction and commentary
- CommentaryAgent: Match commentary and analysis
- AgentCoordinator: Multi-agent orchestration
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
    "PlayerResearchAgent": (".specialized_commentary.player_research_agent", "PlayerResearchAgent"),
    "TeamFormAgent": (".specialized_commentary.team_form_agent", "TeamFormAgent"),
    "HistoricalContextAgent": (".specialized_commentary.historical_context_agent", "HistoricalContextAgent"),
    "WeatherContextAgent": (".specialized_commentary.weather_context_agent", "WeatherContextAgent"),
    "MatchupAnalysisAgent": (".specialized_commentary.matchup_analysis_agent", "MatchupAnalysisAgent"),
    "NewsAgent": (".specialized_commentary.news_agent", "NewsAgent"),
    "CommentaryNoteOrganizerAgent": (".specialized_commentary.note_organizer_agent", "CommentaryNoteOrganizerAgent"),
    "OfficialsAgent": (".specialized_commentary.officials_agent", "OfficialsAgent"),
    "VenueDetailsAgent": (".specialized_commentary.venue_details_agent", "VenueDetailsAgent"),
    "ManagerProfilesAgent": (".specialized_commentary.manager_profiles_agent", "ManagerProfilesAgent"),
    "ClubHistoryAgent": (".specialized_commentary.club_history_agent", "ClubHistoryAgent"),
    "TransfersAgent": (".specialized_commentary.transfers_agent", "TransfersAgent"),
    "PronunciationAgent": (".specialized_commentary.pronunciation_agent", "PronunciationAgent"),
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
    "PlayerResearchAgent",
    "TeamFormAgent",
    "HistoricalContextAgent",
    "WeatherContextAgent",
    "MatchupAnalysisAgent",
    "NewsAgent",
    "CommentaryNoteOrganizerAgent",
    "OfficialsAgent",
    "VenueDetailsAgent",
    "ManagerProfilesAgent",
    "ClubHistoryAgent",
    "TransfersAgent",
    "PronunciationAgent",
]

