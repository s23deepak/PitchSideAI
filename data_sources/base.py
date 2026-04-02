"""
Base Retriever Interface — PitchSide AI
Defines the standard Protocol for all sport-specific data retrievers.
"""
from typing import Dict, List, Any, Protocol

class BaseRetriever(Protocol):

    async def get_match_context(self, team_name: str, sport: str) -> Dict[str, Any]:
        """Fetch exact datetime and venue for the active match."""
        ...

    async def get_team_squad(self, team_name: str, sport: str) -> Dict[str, Any]:
        """Fetch squad roster with key stats."""
        ...

    async def get_recent_form(self, team_name: str, sport: str, num_games: int = 5) -> Dict[str, Any]:
        """Fetch recent W/D/L form and goals/points."""
        ...

    async def get_player_stats(self, player_name: str, team_name: str, sport: str) -> Dict[str, Any]:
        """Fetch individual player statistics."""
        ...

    async def get_head_to_head(self, home_team: str, away_team: str, sport: str) -> Dict[str, Any]:
        """Fetch historical H2H record."""
        ...

    async def get_team_news(self, team_name: str, sport: str) -> List[Dict[str, Any]]:
        """Fetch recent news articles."""
        ...

    async def get_injuries(self, team_name: str, sport: str) -> List[Dict[str, Any]]:
        """Fetch current injury status for players."""
        ...
