"""
Team Form Agent - Analyze team form, tactics, and performance patterns.

Synthesizes recent match results, tactical evolution, and performance trends
into actionable intelligence for commentary preparation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from agents.base import BaseAgent
from data_sources import DataCache
from data_sources.factory import get_football_data_retriever, get_retriever

logger = logging.getLogger(__name__)


class TeamFormAgent(BaseAgent):
    """Analyze team form and tactical patterns."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
        football_data_retriever: Optional[Any] = None,
    ):
        """
        Initialize team form agent.

        Args:
            model_id: Bedrock model ID (Nova Pro for quality analysis)
            sport: Sport type
            cache: Optional shared cache
        """
        super().__init__(model_id=model_id, sport=sport, agent_type="team_form")
        self.cache = cache or DataCache(ttl_seconds=3600)
        self.retriever = get_retriever(self.sport, cache=self.cache)
        self.football_data = football_data_retriever or get_football_data_retriever(cache=self.cache)

    async def execute(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """
        Main execution method for BaseAgent compatibility.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            Form analysis for both teams
        """
        return await self.analyze_both_teams(home_team, away_team)

    async def analyze_both_teams(
        self,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Analyze form for both teams simultaneously.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            Comparative form analysis
        """
        start_time = datetime.utcnow()

        # Analyze both in parallel
        home_form, away_form = await asyncio.gather(
            self.analyze_team_form(home_team),
            self.analyze_team_form(away_team),
        )

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        self.log_event(
            event_type="form_analysis_complete",
            details={
                "home_team": home_team,
                "away_team": away_team,
                "duration_ms": duration_ms,
            },
        )

        return {
            "home_team": home_form,
            "away_team": away_form,
            "comparative_analysis": await self._compare_form(home_form, away_form),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def analyze_team_form(self, team_name: str) -> Dict[str, Any]:
        """
        Analyze team's recent form and performance patterns.

        Args:
            team_name: Team name

        Returns:
            Form analysis including recent results, tactical patterns, metrics
        """
        # Get ESPN data for recent form
        recent_form = await self.retriever.get_recent_form(
            team_name,
            self.sport,
            num_games=5,
        )

        # Extract record data from ESPN schema
        record = recent_form.get('record', {})
        wins = record.get('wins', 0)
        draws = record.get('draws', 0)
        losses = record.get('losses', 0)
        goals_for = recent_form.get('goals_for', 0)
        goals_against = recent_form.get('goals_against', 0)
        form_string = recent_form.get('form_string', '')
        home_away_split = await self.analyze_home_away_split(team_name)

        split_summary = self._format_home_away_split(home_away_split)

        # Use Bedrock to synthesize comprehensive analysis
        analysis_prompt = f"""As an elite {self.sport} analyst, analyze the current form and tactical evolution of {team_name}:

Recent Form: {form_string or 'No data'}
Record: {wins}W-{draws}D-{losses}L
Goals For/Against: {goals_for} / {goals_against}
Home/Away Split: {split_summary}

Provide:
1. Current Form Status (in-form, declining, stable, resurgent)
2. Key Performance Trends (defensive record, goal-scoring rate)
3. Momentum Assessment (direction and confidence level)
4. Recent Performance Pattern (any notable streaks or fluctuations)
5. Tactical Implications for upcoming match

Keep analysis concise (4-5 sentences for commentary notes)."""

        form_analysis = await self.call_bedrock(
            prompt=analysis_prompt,
            temperature=0.4,
            max_tokens=200,
        )

        return {
            "team_name": team_name,
            "recent_form": recent_form,
            "home_away_split": home_away_split,
            "comprehensive_analysis": form_analysis,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def analyze_home_away_split(self, team_name: str) -> Dict[str, Any]:
        """Analyze a team's home and away split using football-data standings."""
        if self.sport != "soccer" or not self.football_data or not self.football_data.is_available:
            return {}

        competition_code = self.football_data.resolve_competition_code(team_name)
        if not competition_code:
            return {}

        standings = await self.football_data.get_standings(competition_code)
        team_rows = self.football_data.get_team_standing(standings, team_name)
        return {
            "competition_code": competition_code,
            **team_rows,
        }

    def _format_home_away_split(self, split: Dict[str, Any]) -> str:
        """Format standings splits for prompting."""
        home_row = split.get("home")
        away_row = split.get("away")
        if not home_row and not away_row:
            return "Unavailable"

        parts = []
        if home_row:
            parts.append(
                f"Home {home_row.get('won', 0)}W-{home_row.get('draw', 0)}D-{home_row.get('lost', 0)}L"
            )
        if away_row:
            parts.append(
                f"Away {away_row.get('won', 0)}W-{away_row.get('draw', 0)}D-{away_row.get('lost', 0)}L"
            )
        return " | ".join(parts)

    async def _compare_form(
        self,
        home_form: Dict[str, Any],
        away_form: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare form of both teams.

        Args:
            home_form: Home team form analysis
            away_form: Away team form analysis

        Returns:
            Comparative assessment
        """
        comparison_prompt = f"""As an elite {self.sport} analyst, compare the current form of {home_form['team_name']} (home) vs {away_form['team_name']} (away):

Home Team Form: {home_form.get('comprehensive_analysis', 'Analysis unavailable')[:200]}...

Away Team Form: {away_form.get('comprehensive_analysis', 'Analysis unavailable')[:200]}...

Provide:
1. Form Favorability (who is in better form)
2. Momentum Advantage (direction and magnitude)
3. Expected Tactical Approach given form
4. Key Matchup Areas most affected by form

Keep to 3-4 sentences."""

        comparison = await self.call_bedrock(
            prompt=comparison_prompt,
            temperature=0.4,
            max_tokens=150,  # 150 for local dev (300 in production)
        )

        return {
            "comparative_assessment": comparison,
            "likely_match_narrative": comparison.split(".")[0].strip() if comparison else "Unavailable",
        }


    async def close(self):
        """Clean up resources."""
        return None
