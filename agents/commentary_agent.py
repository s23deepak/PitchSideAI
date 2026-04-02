"""
Commentary Agent — Amazon Nova Pro
Generates engaging live match commentary.
"""
from typing import Dict, Any, Optional, List

from agents.base import CommentaryAgent as BaseCommentaryAgent
from config.prompts import get_commentary_prompt, get_tactical_prompt
from tools.dynamodb_tool import write_event


class CommentaryAgent(BaseCommentaryAgent):
    """
    Generates professional live match commentary using Nova Pro.
    Adapts to any sport type with dynamic prompts.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import RESEARCH_MODEL  # Use Pro model for quality
        super().__init__(model_id or RESEARCH_MODEL, sport)

    async def execute(self, match_context: str, recent_events: str) -> str:
        """Execute commentary generation task."""
        return await self.generate_commentary(match_context, recent_events)

    async def generate_commentary(
        self,
        match_context: str,
        recent_events: str
    ) -> str:
        """
        Generate live match commentary using dynamic sport-specific prompts.

        Args:
            match_context: Pre-match brief and context
            recent_events: Recent events in the match

        Returns:
            Engaging commentary segment
        """
        self.log_event("commentary_generation_started", {
            "context_length": len(match_context),
            "events_length": len(recent_events),
            "sport": self.sport
        })

        # Get dynamic prompt based on sport
        prompt = get_commentary_prompt(self.sport, match_context, recent_events)

        # Generate commentary
        commentary = await self.call_bedrock(
            prompt,
            temperature=0.7,  # Higher temp for varied commentary
            max_tokens=500
        )

        self.log_event("commentary_generated", {
            "commentary_length": len(commentary)
        })

        # Log to DynamoDB
        await write_event(
            "commentary",
            commentary[:200],
            {
                "full_commentary": commentary,
                "sport": self.sport
            }
        )

        return commentary

    async def generate_tactical_commentary(
        self,
        tactical_situation: str,
        team_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate tactical analysis commentary using dynamic sport prompts.

        Args:
            tactical_situation: Description of current tactical situation
            team_context: Optional context about teams

        Returns:
            Tactical commentary
        """
        self.log_event("tactical_commentary_requested", {
            "situation": tactical_situation[:100]
        })

        prompt = get_tactical_prompt(self.sport, tactical_situation)

        commentary = await self.call_bedrock(
            prompt,
            temperature=0.5,
            max_tokens=400
        )

        await write_event(
            "tactical_commentary",
            tactical_situation[:100],
            {
                "commentary": commentary,
                "sport": self.sport
            }
        )

        return commentary

    async def generate_player_insight(
        self,
        player_name: str,
        team_name: str,
        recent_performance: str
    ) -> str:
        """
        Generate insight about a specific player.

        Args:
            player_name: Player name
            team_name: Team name
            recent_performance: Recent performance info

        Returns:
            Player insight commentary
        """
        prompt = f"""
You are a professional {self.sport} commentator providing insight on a specific player.

PLAYER: {player_name} ({team_name})

RECENT PERFORMANCE:
{recent_performance}

Generate 2-3 sentences of engaging commentary about this player's performance, highlighting:
- Key strengths shown today
- Decision-making quality
- Impact on team play
- Why this player is crucial right now

Keep it professional yet engaging for broadcast.
"""

        insight = await self.call_bedrock(
            prompt,
            temperature=0.6,
            max_tokens=300
        )

        self.log_event("player_insight_generated", {
            "player": player_name,
            "team": team_name
        })

        await write_event(
            "player_insight",
            f"{player_name} - {team_name}",
            {
                "insight": insight,
                "sport": self.sport
            }
        )

        return insight

    async def generate_match_narrative(
        self,
        periods: List[Dict[str, str]]
    ) -> str:
        """
        Generate narrative summary across match periods.

        Args:
            periods: List of period descriptions

        Returns:
            Match narrative
        """
        periods_str = "\n".join([
            f"Period {i+1}: {p.get('description', '')}"
            for i, p in enumerate(periods)
        ])

        prompt = f"""
You are a professional {self.sport} commentator creating a narrative summary of the match.

MATCH PROGRESSION:
{periods_str}

Generate a engaging 4-5 sentence narrative that:
- Captures the flow of the match
- Highlights key turning points
- Describes tactical evolution
- Sets up the current situation

Write as if describing the match to someone who missed it.
"""

        narrative = await self.call_bedrock(
            prompt,
            temperature=0.6,
            max_tokens=400
        )

        await write_event(
            "match_narrative",
            "Match progression",
            {
                "narrative": narrative,
                "period_count": len(periods),
                "sport": self.sport
            }
        )

        return narrative

    async def generate_prediction(
        self,
        current_state: str,
        remaining_time: Optional[str] = None
    ) -> str:
        """
        Generate prediction for what might happen next.

        Args:
            current_state: Current match state
            remaining_time: Time remaining in match

        Returns:
            Prediction commentary
        """
        time_context = f" with {remaining_time} remaining" if remaining_time else ""

        prompt = f"""
You are a professional {self.sport} commentator predicting likely scenarios.

CURRENT SITUATION:{current_state}{time_context}

What are the likely scenarios that could unfold next? Provide:

1. Most likely outcome
2. Key tactical adjustments expected
3. Players to watch
4. Potential turning points

Be specific and base predictions on current match dynamics.
"""

        prediction = await self.call_bedrock(
            prompt,
            temperature=0.6,
            max_tokens=350
        )

        await write_event(
            "prediction",
            current_state[:100],
            {
                "prediction": prediction,
                "sport": self.sport
            }
        )

        return prediction

    async def generate_match_summary(
        self,
        final_score: str,
        key_moments: str,
        match_stats: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate comprehensive post-match summary.

        Args:
            final_score: Final score line
            key_moments: Key moments during match
            match_stats: Optional match statistics

        Returns:
            Post-match summary
        """
        stats_text = ""
        if match_stats:
            stats_text = "\n\nKEY STATISTICS:\n" + "\n".join([
                f"- {k}: {v}" for k, v in match_stats.items()
            ])

        prompt = f"""
You are a professional {self.sport} analyst providing post-match analysis.

FINAL SCORE: {final_score}

KEY MOMENTS:
{key_moments}{stats_text}

Generate a 4-5 paragraph post-match summary that:
1. Summarizes the match flow and outcome
2. Highlights key tactical decisions and turning points
3. Identifies standout player performances
4. Analyzes what went right/wrong for each team
5. Provides overall verdict and implications

Use authentic {self.sport} analysis terminology.
"""

        summary = await self.call_bedrock(
            prompt,
            temperature=0.6,
            max_tokens=800
        )

        await write_event(
            "match_summary",
            final_score,
            {
                "summary": summary,
                "sport": self.sport
            }
        )

        return summary

