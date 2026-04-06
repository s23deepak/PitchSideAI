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

=== STRICT GROUNDING RULES (apply before answering) ===
1. You may ONLY use facts that appear verbatim or nearly verbatim in the MATCH CONTEXT above.
2. If the MATCH CONTEXT does not contain the answer, you MUST reply:
   "I don't have grounded context for that — the match data I was given doesn't cover this."
3. NEVER guess, infer, or recall facts from your training data. A wrong answer is worse than no answer.
4. Do not speculate about scores, opponents, dates, or results unless they are explicitly stated above.
=====================================================

FAN QUESTION: {query}

Answer concisely in 2-3 sentences using ONLY the context above. If unsure, say so.

Answer:
"""

    @staticmethod
    def frame_analysis_prompt(sport: str, include_formations: bool = True, temporal_context: dict | None = None) -> str:
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

        definitions_str = ""
        if hasattr(config, "tactical_definitions") and config.tactical_definitions:
            definitions_str = "\nCRITICAL VISUAL DEFINITIONS:\n"
            for label, definition in config.tactical_definitions.items():
                definitions_str += f'- "{label}": {definition}\n'

        temporal_note = ""
        if temporal_context:
            fi = temporal_context.get("frame_index", 0)
            total = temporal_context.get("total_frames", 1)
            ts_ms = temporal_context.get("timestamp_ms", 0)
            total_sec = int(ts_ms // 1000)
            mins, secs = divmod(total_sec, 60)
            temporal_note = (
                f"\nThis is frame {fi + 1} of {total} from a video clip "
                f"(timestamp {mins:02d}:{secs:02d}). "
                f"Consider what tactical phase is developing at this point in the sequence."
            )

        return f"""
You are an elite {config.display_name} tactical analyst with expertise in real-time pattern recognition.

Analyze this video frame and provide tactical insights.{temporal_note}

Identify tactical situation from options: {labels_str} ...
{definitions_str}
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

    @staticmethod
    def video_sequence_prompt(sport: str, sequence_summary: str) -> str:
        """Prompt for summarizing tactical evolution across frame or window detections."""
        config = get_sport_config(sport)

        return f"""
    You are an elite {config.display_name} tactical analyst reviewing a sequence of timestamped detections from the same video clip.

    Each timestamped entry may represent either a sampled frame or a short native-video window.

SEQUENCE SUMMARY:
{sequence_summary}

Produce valid JSON only:
{{
    "temporal_change": "...",
    "primary_tactical_label": "...",
    "primary_timestamp_ms": 0,
    "confidence": 0.0,
    "commentary_cue": "..."
}}

Rules:
- Synthesize a coherent tactical narrative across the full clip duration.
- Adjacent windows or frames may overlap in time — deduplicate observations that describe the same event or phase rather than counting them twice.
- Explain how the tactic evolves, transitions, or escalates over time.
- If the same tactical label appears across multiple timestamps, describe whether it was sustained, intensified, or shifted.
- Use only evidence from the sequence summary.
- `temporal_change` should read like a single analyst's continuous account of the clip, not a list of individual frames.
- `primary_timestamp_ms` must be one timestamp from the summary — pick the tactically decisive moment.
- `confidence` must be between 0.0 and 1.0 — reflect certainty about the overall tactical read, not a single frame.
- `commentary_cue` should be a broadcast-ready sentence a commentator could use on air.
"""

    @staticmethod
    def video_clip_prompt(sport: str) -> str:
        """Prompt for native video understanding over an entire clip."""
        config = get_sport_config(sport)
        tactical_labels = ", ".join(get_tactical_labels(sport)[:10])

        return f"""
You are an elite {config.display_name} tactical analyst watching a short video clip.

Available tactical categories: {tactical_labels}

Analyze the clip as a continuous sequence, not as a still image. Focus on tactical changes, transitions, player spacing, and how the pattern evolves over time.

Respond ONLY with valid JSON:
{{
    "temporal_change": "...",
    "primary_tactical_label": "...",
    "primary_timestamp_ms": 0,
    "confidence": 0.0,
    "commentary_cue": "..."
}}

Rules:
- `primary_timestamp_ms` should identify the most important moment in the clip.
- `temporal_change` must describe how the tactic develops across time.
- `commentary_cue` should be ready for live broadcast.
- Use only what is visible in the clip.
"""


# Backward compatibility functions
def get_research_prompt(home_team: str, away_team: str, sport: str = "soccer") -> str:
    """Get research brief prompt."""
    return SystemPrompts.research_brief_prompt(home_team, away_team, sport)


def get_query_prompt(context: str, query: str, sport: str = "soccer") -> str:
    """Get live query prompt."""
    return SystemPrompts.live_query_prompt(context, query, sport)


def get_frame_prompt(sport: str = "soccer", temporal_context: dict | None = None) -> str:
    """Get frame analysis prompt."""
    return SystemPrompts.frame_analysis_prompt(sport, temporal_context=temporal_context)


def get_commentary_prompt(sport: str, match_context: str, recent_events: str) -> str:
    """Get commentary generation prompt."""
    return SystemPrompts.commentary_generation_prompt(sport, match_context, recent_events)


def get_tactical_prompt(sport: str, patterns: str) -> str:
    """Get tactical analysis prompt."""
    return SystemPrompts.tactical_analysis_prompt(sport, patterns)


def get_video_sequence_prompt(sport: str, sequence_summary: str) -> str:
    """Get video sequence tactical summary prompt."""
    return SystemPrompts.video_sequence_prompt(sport, sequence_summary)


def get_video_clip_prompt(sport: str) -> str:
    """Get native video clip tactical prompt."""
    return SystemPrompts.video_clip_prompt(sport)
