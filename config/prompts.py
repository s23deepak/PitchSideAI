"""
System Prompts for Agents
Centralized, dynamic prompts based on sport selection.
"""
from typing import Dict
from config.sports import SportType, get_sport_config, get_tactical_labels, get_research_topics


class SystemPrompts:
    """Manages system prompts for different agents and sports."""

    @staticmethod
    def research_brief_prompt(home_team: str, away_team: str, sport: str) -> str:
        """
        Dynamic research brief prompt based on sport.
        """
        config = get_sport_config(sport)
        topics = get_research_topics(sport)
        topics_str = "\n        ".join([f"{i+1}. {t}" for i, t in enumerate(topics)])

        return f"""
You are a professional {config.display_name} analyst preparing for a live match.
Research and prepare a comprehensive Commentator's Brief for:

MATCH: {home_team} vs {away_team}

Research and include:
        {topics_str}

Format as a structured document with clear sections. Be specific with statistics and recent performance data.
Use tactical terminology appropriate for {config.display_name}.

Provide actionable insights that a commentator would use during live broadcast.
"""

    @staticmethod
    def live_query_prompt(context: str, query: str, sport: str) -> str:
        """
        Dynamic live query prompt based on sport.
        """
        config = get_sport_config(sport)

        return f"""
You are a real-time {config.display_name} analyst assistant providing instant commentary insights.

MATCH CONTEXT (pre-researched data):
{context}

FAN QUESTION: {query}

Rules:
- Answer concisely in 2-3 sentences
- Reference specific statistics where available
- Use sport-appropriate terminology ({config.display_name} tactics/formations)
- Be engaging for commentator broadcast
- If the question is outside the context, say so

Answer:
"""

    @staticmethod
    def frame_analysis_prompt(sport: str, include_formations: bool = True) -> str:
        """
        Dynamic frame analysis prompt based on sport.
        """
        config = get_sport_config(sport)
        tactical_labels = get_tactical_labels(sport)
        labels_str = " | ".join(tactical_labels[:8])  # Show first 8 labels

        if include_formations and config.formation_regex:
            formation_note = f"\nAlso identify formations (e.g., {', '.join(config.formation_regex[:3])})."
        else:
            formation_note = ""

        return f"""
You are an elite {config.display_name} tactical analyst with expertise in real-time pattern recognition.

Analyze this video frame and provide tactical insights.

Identify tactical situation: [{labels_str} | ...]
{formation_note}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
    "tactical_label": "...",
    "key_observation": "...",
    "confidence": 0.0,
    "actionable_insight": "..."
}}

Be precise. Confidence should be 0.0-1.0. Insight should guide commentary.
"""

    @staticmethod
    def commentary_generation_prompt(sport: str, match_context: str, recent_events: str) -> str:
        """
        Dynamic commentary generation prompt based on sport.
        """
        config = get_sport_config(sport)

        return f"""
You are a professional {config.display_name} commentator generating live match commentary.

MATCH CONTEXT:
{match_context}

RECENT EVENTS:
{recent_events}

Generate a 3-4 sentence engaging commentary segment that:
1. Describes what just happened
2. References player/team strategy
3. Predicts next likely play
4. Maintains broadcast enthusiasm

Use authentic {config.display_name} terminology and commentary style.
Keep the energy high and informative.

Commentary:
"""

    @staticmethod
    def tactical_analysis_prompt(sport: str, detected_patterns: str) -> str:
        """
        Dynamic tactical analysis prompt based on sport.
        """
        config = get_sport_config(sport)
        tactical_labels = ", ".join(get_tactical_labels(sport)[:10])

        return f"""
You are a strategic {config.display_name} analyst providing deep tactical breakdowns.

DETECTED PATTERNS:
{detected_patterns}

AVAILABLE TACTICAL CATEGORIES: {tactical_labels}

Provide a detailed tactical analysis:
- What's the team trying to achieve?
- How effective is this approach?
- What counter-strategies might the opponent use?
- Key players driving this tactic?
- Historical success rate of this approach?

Be specific with {config.display_name} terminology and strategic concepts.
"""


# Backward compatibility functions
def get_research_prompt(home_team: str, away_team: str, sport: str = "soccer") -> str:
    """Get research brief prompt."""
    return SystemPrompts.research_brief_prompt(home_team, away_team, sport)


def get_query_prompt(context: str, query: str, sport: str = "soccer") -> str:
    """Get live query prompt."""
    return SystemPrompts.live_query_prompt(context, query, sport)


def get_frame_prompt(sport: str = "soccer") -> str:
    """Get frame analysis prompt."""
    return SystemPrompts.frame_analysis_prompt(sport)


def get_commentary_prompt(sport: str, match_context: str, recent_events: str) -> str:
    """Get commentary generation prompt."""
    return SystemPrompts.commentary_generation_prompt(sport, match_context, recent_events)


def get_tactical_prompt(sport: str, patterns: str) -> str:
    """Get tactical analysis prompt."""
    return SystemPrompts.tactical_analysis_prompt(sport, patterns)
