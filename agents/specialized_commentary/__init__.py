"""
Specialized Commentary Agents for multi-agent note preparation.

These agents collaborate to produce professional Peter Drury-style
commentary notes through data gathering, analysis, and synthesis.

Agents:
- PlayerResearchAgent: Research 25 players per team
- TeamFormAgent: Analyze team form and tactical patterns
- HistoricalContextAgent: Build historical narratives
- WeatherContextAgent: Contextualize weather impact
- MatchupAnalysisAgent: Analyze 1v1 matchups
- NewsAgent: Get current team news and injuries
- CommentaryNoteOrganizerAgent: Synthesize into final notes
"""

from agents.specialized_commentary.player_research_agent import PlayerResearchAgent
from agents.specialized_commentary.team_form_agent import TeamFormAgent
from agents.specialized_commentary.historical_context_agent import HistoricalContextAgent
from agents.specialized_commentary.weather_context_agent import WeatherContextAgent
from agents.specialized_commentary.matchup_analysis_agent import MatchupAnalysisAgent
from agents.specialized_commentary.news_agent import NewsAgent
from agents.specialized_commentary.note_organizer_agent import CommentaryNoteOrganizerAgent

__all__ = [
    "PlayerResearchAgent",
    "TeamFormAgent",
    "HistoricalContextAgent",
    "WeatherContextAgent",
    "MatchupAnalysisAgent",
    "NewsAgent",
    "CommentaryNoteOrganizerAgent",
]
