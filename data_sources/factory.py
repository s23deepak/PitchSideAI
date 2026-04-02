"""
Data Retriever Factory — PitchSide AI
Dynamically routes data requests to the most specialized sports API available.
"""
from typing import Optional
import logging
from .cache import DataCache
from .base import BaseRetriever

logger = logging.getLogger(__name__)

def get_retriever(sport: str, cache: Optional[DataCache] = None) -> BaseRetriever:
    """
    Factory to return the optimal data retriever for a given sport.
    """
    sport_key = sport.lower().strip()
    
    if sport_key == "cricket":
        from .cricbuzz_retriever import CricbuzzRetriever
        return CricbuzzRetriever(cache=cache)
        
    elif sport_key == "soccer":
        from .goal_retriever import GoalComRetriever
        # We can implement Goal.com later, but let's fall back to ESPN for now
        # until the GoalComRetriever is fully ready!
        # return GoalComRetriever(cache=cache)
        pass
        
    # Default robust fallback for all sports (incl Soccer until Goal.com is done)
    from .espn_retriever import ESPNDataRetriever
    return ESPNDataRetriever(cache=cache)
