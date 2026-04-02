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
from data_sources.factory import get_retriever

logger = logging.getLogger(__name__)


class TeamFormAgent(BaseAgent):
    """Analyze team form and tactical patterns."""

    def __init__(
        self,
        model_id: str = "us.nova-pro-1:0",
        sport: str = "soccer",
        cache: Optional[DataCache] = None,
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

        # Generate tactical analysis
        home_away_split = await self.analyze_home_away_split(team_name)

        # Use Bedrock to synthesize comprehensive analysis
        analysis_prompt = f"""As an elite {self.sport} analyst, analyze the current form and tactical evolution of {team_name}:

Recent Results:
{self._format_match_results(recent_form.get('recent_matches', []))}

W-D-L: {recent_form.get('w_d_l', [0,0,0])}
Goals For/Against: {recent_form.get('goals_for', 0):.1f} / {recent_form.get('goals_against', 0):.1f}

Home/Away: {home_away_split.get('home_record', 'N/A')} / {home_away_split.get('away_record', 'N/A')}

Provide:
1. Current Form Status (in-form, declining, stable, resurgent)
2. Key Performance Trends (defensive solidity, attacking flair, set pieces, transitions)
3. Momentum Assessment (momentum direction and confidence level)
4. Tactical Evolution (what's working, what's struggling)
5. Key Player Performance Impact

Keep analysis concise (4-5 sentences for commentary notes)."""

        form_analysis = await self.call_bedrock(
            prompt=analysis_prompt,
            temperature=0.4,
            max_tokens=200,  # 200 for local dev (400 in production)
        )

        return {
            "team_name": team_name,
            "recent_form": recent_form,
            "home_away_split": home_away_split,
            "comprehensive_analysis": form_analysis,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def analyze_home_away_split(self, team_name: str) -> Dict[str, Any]:
        """
        Analyze team's home vs away performance differential.

        Args:
            team_name: Team name

        Returns:
            Home/away record and performance patterns
        """
        # Fetch from ESPN
        form_data = await self.retriever.get_recent_form(team_name, self.sport, 10)

        home_away = form_data.get("home_away", {})

        # Analyze performance difference
        performance_diff = await self._analyze_performance_differential(
            home_away.get("home_record", ""),
            home_away.get("away_record", ""),
        )

        return {
            "home_record": home_away.get("home_record", "N/A"),
            "away_record": home_away.get("away_record", "N/A"),
            "performance_differential": performance_diff,
            "travel_fatigue_risk": performance_diff.get("travel_impact", "Low"),
        }

    def _format_match_results(self, matches: List[Dict[str, Any]]) -> str:
        """Format recent matches for prompt."""
        formatted = []
        for match in matches:
            formatted.append(
                f"- {match.get('opponent', 'Unknown')}: {match.get('result', 'Unknown')} "
                f"(Rating: {match.get('rating', 'N/A')}/10)"
            )
        return "\n".join(formatted) or "No recent matches"

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
            "likely_match_narrative": "Home team likely to dominate if they maintain form",
        }

    async def _analyze_performance_differential(
        self,
        home_record: str,
        away_record: str,
    ) -> Dict[str, Any]:
        """
        Calculate home vs away performance differential.

        Args:
            home_record: Home W-D-L record
            away_record: Away W-D-L record

        Returns:
            Analysis of home advantage
        """
        # Simple heuristic analysis
        home_wins = home_record.count("W")
        away_wins = away_record.count("W")
        differential = home_wins - away_wins

        if differential > 2:
            impact = "Very Strong"
            travel_impact = "Moderate"
        elif differential > 0:
            impact = "Moderate"
            travel_impact = "Low"
        else:
            impact = "Weak"
            travel_impact = "Low"

        return {
            "home_advantage": impact,
            "travel_impact": travel_impact,
            "differential": differential,
        }

    async def close(self):
        """Clean up resources."""
        await self.retriever.close()
