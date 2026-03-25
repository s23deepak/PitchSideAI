"""
Search Tool — Google Search Grounding via Gemini API
Wraps Google Search for use as an ADK tool in the research agent.
Also provides a standalone async search helper for direct use.
"""
import asyncio
import logging

import httpx
import google.generativeai as genai

from config import GOOGLE_API_KEY, RESEARCH_MODEL

logger = logging.getLogger(__name__)
genai.configure(api_key=GOOGLE_API_KEY)


async def google_search_grounded(query: str, context: str = "") -> str:
    """
    ADK Tool: Run a Google Search-grounded Gemini query.
    Uses Gemini's native Google Search grounding tool to retrieve
    up-to-date sports news, player stats, and match data.

    Args:
        query: The search/research question.
        context: Optional additional context to include in the prompt.

    Returns:
        Grounded answer string with citations where available.
    """
    model = genai.GenerativeModel(
        model_name=RESEARCH_MODEL,
        tools=["google_search_retrieval"],
    )

    prompt = query if not context else f"{context}\n\nSearch for: {query}"

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text
    except Exception as e:
        logger.warning(f"[SearchTool] Grounded search failed: {e}. Falling back.")
        return await _fallback_search(query)


async def fetch_player_stats(player_name: str, season: str = "2025-26") -> str:
    """
    ADK Tool: Fetch current season stats for a specific player.

    Args:
        player_name: Full name of the player.
        season: Season string (e.g., '2025-26').

    Returns:
        String summary of player stats.
    """
    query = f"{player_name} {season} season statistics goals assists form"
    return await google_search_grounded(query)


async def fetch_head_to_head(home_team: str, away_team: str) -> str:
    """
    ADK Tool: Fetch head-to-head record between two teams.

    Args:
        home_team: Name of the home team.
        away_team: Name of the away team.

    Returns:
        String summary of recent H2H record.
    """
    query = f"{home_team} vs {away_team} head to head record last 5 matches 2025 2026"
    return await google_search_grounded(query)


async def fetch_injury_news(team: str) -> str:
    """
    ADK Tool: Fetch latest injury and suspension news for a team.

    Args:
        team: Team name.

    Returns:
        String with current injury/suspension report.
    """
    query = f"{team} injury news latest team news suspension 2026"
    return await google_search_grounded(query)


async def _fallback_search(query: str) -> str:
    """Simple fallback: returns a polite failure message."""
    return f"[Search unavailable] Could not retrieve live data for: '{query}'. Please check manually."


# ── CLI self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def _test():
        print("Testing Google Search grounding tool...")
        result = await fetch_head_to_head("Manchester City", "Arsenal")
        print(f"\nH2H Result:\n{result[:500]}")
    asyncio.run(_test())
