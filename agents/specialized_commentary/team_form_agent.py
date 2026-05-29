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
        Analyze form for both teams simultaneously with parallel comparison.

        Args:
            home_team: Home team
            away_team: Away team

        Returns:
            Comparative form analysis
        """
        start_time = datetime.utcnow()

        # Analyze both teams in parallel, THEN run comparison
        home_form, away_form = await asyncio.gather(
            self.analyze_team_form(home_team),
            self.analyze_team_form(away_team),
        )

        # Run comparison IN PARALLEL with any remaining work (none here, but pattern matters)
        comparative_analysis = await self._compare_form(home_form, away_form)

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
            "comparative_analysis": comparative_analysis,
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
        recent_form = self._normalize_recent_form(recent_form)
        record = recent_form.get('record', {})
        wins = record.get('wins')
        draws = record.get('draws')
        losses = record.get('losses')
        goals_for = recent_form.get('goals_for')
        goals_against = recent_form.get('goals_against')
        form_string = recent_form.get('form_string', '')
        home_away_split = await self.analyze_home_away_split(team_name)

        split_summary = self._format_home_away_split(home_away_split)
        has_form_evidence = self._has_form_evidence(recent_form, home_away_split)
        if not has_form_evidence:
            return {
                "team_name": team_name,
                "recent_form": recent_form,
                "home_away_split": home_away_split,
                "comprehensive_analysis": "",
                "data_status": "unavailable",
                "timestamp": datetime.utcnow().isoformat(),
            }
        if self._has_only_sequence_evidence(recent_form, home_away_split):
            return {
                "team_name": team_name,
                "recent_form": recent_form,
                "home_away_split": home_away_split,
                "comprehensive_analysis": "",
                "data_status": "partial",
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Use Bedrock to synthesize comprehensive analysis
        analysis_prompt = f"""As an elite {self.sport} analyst, analyze the current form and tactical evolution of {team_name}:

Recent Form: {form_string or 'No data'}
Record: {self._format_record(wins, draws, losses)}
Goals For/Against: {self._format_metric_pair(goals_for, goals_against)}
Home/Away Split: {split_summary}

Provide:
1. Current Form Status (in-form, declining, stable, resurgent)
2. Key Performance Trends (defensive record, goal-scoring rate)
3. Momentum Assessment (direction and confidence level)
4. Recent Performance Pattern (any notable streaks or fluctuations)
5. Tactical Implications for upcoming match

Keep analysis concise (4-5 sentences for commentary notes)."""

        form_analysis = await self.call_llm(
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

    def _normalize_recent_form(self, recent_form: Dict[str, Any]) -> Dict[str, Any]:
        """Preserve missing form values as unavailable instead of numeric zero."""
        if not isinstance(recent_form, dict):
            return {"record": {"wins": None, "draws": None, "losses": None}, "form_string": ""}
        normalized = dict(recent_form)
        raw_record = recent_form.get("record", {}) if isinstance(recent_form.get("record"), dict) else {}
        normalized["record"] = {
            key: raw_record[key] if key in raw_record and raw_record[key] is not None else None
            for key in ("wins", "draws", "losses")
        }
        for key in ("goals_for", "goals_against"):
            if key not in recent_form or recent_form.get(key) is None:
                normalized[key] = None
        return normalized

    def _has_form_evidence(self, recent_form: Dict[str, Any], home_away_split: Dict[str, Any]) -> bool:
        record = recent_form.get("record", {}) if isinstance(recent_form, dict) else {}
        record_values = [record.get(key) for key in ("wins", "draws", "losses")]
        if any(self._is_positive_number(value) for value in record_values):
            return True
        if self._is_meaningful_form_string(recent_form.get("form_string", "")):
            return True
        if self._is_positive_number(recent_form.get("goals_for")) or self._is_positive_number(recent_form.get("goals_against")):
            return True
        return bool(self._format_home_away_split(home_away_split) != "Unavailable")

    def _has_only_sequence_evidence(self, recent_form: Dict[str, Any], home_away_split: Dict[str, Any]) -> bool:
        if not self._is_meaningful_form_string(recent_form.get("form_string", "")):
            return False
        record = recent_form.get("record", {}) if isinstance(recent_form, dict) else {}
        record_values = [record.get(key) for key in ("wins", "draws", "losses")]
        has_record = any(self._is_positive_number(value) for value in record_values)
        has_goals = self._is_positive_number(recent_form.get("goals_for")) or self._is_positive_number(recent_form.get("goals_against"))
        has_split = self._format_home_away_split(home_away_split) != "Unavailable"
        return not (has_record or has_goals or has_split)

    def _is_positive_number(self, value: Any) -> bool:
        try:
            return value is not None and float(value) > 0
        except (TypeError, ValueError):
            return False

    def _format_record(self, wins: Any, draws: Any, losses: Any) -> str:
        if wins is None and draws is None and losses is None:
            return "Unavailable"
        return f"{wins if wins is not None else 'unavailable'}W-{draws if draws is not None else 'unavailable'}D-{losses if losses is not None else 'unavailable'}L"

    def _format_metric_pair(self, first: Any, second: Any) -> str:
        if first is None and second is None:
            return "Unavailable"
        return f"{first if first is not None else 'unavailable'} / {second if second is not None else 'unavailable'}"

    def _is_meaningful_form_string(self, form_string: Any) -> bool:
        if not isinstance(form_string, str):
            return False
        cleaned = form_string.strip().lower()
        return bool(cleaned) and cleaned not in {"no data", "unavailable", "unknown", "n/a", "none", "tbd"}

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
        if home_form.get("data_status") == "unavailable" and away_form.get("data_status") == "unavailable":
            return {
                "comparative_assessment": "",
                "likely_match_narrative": "Unavailable",
                "data_status": "unavailable",
            }

        if self._should_use_deterministic_comparison(home_form, away_form):
            return self._build_comparative_fallback(home_form, away_form)

        comparison_prompt = f"""As an elite {self.sport} analyst, compare the current form of {home_form['team_name']} (home) vs {away_form['team_name']} (away):

Home Team Form: {home_form.get('comprehensive_analysis', 'Analysis unavailable')[:200]}...

Away Team Form: {away_form.get('comprehensive_analysis', 'Analysis unavailable')[:200]}...

Provide:
1. Form Favorability (who is in better form)
2. Momentum Advantage (direction and magnitude)
3. Expected Tactical Approach given form
4. Key Matchup Areas most affected by form

Keep to 3-4 sentences."""

        comparison = await self.call_llm(
            prompt=comparison_prompt,
            temperature=0.4,
            max_tokens=150,  # 150 for local dev (300 in production)
        )

        return {
            "comparative_assessment": comparison,
            "likely_match_narrative": comparison.split(".")[0].strip() if comparison else "Unavailable",
        }

    def _should_use_deterministic_comparison(self, home_form: Dict[str, Any], away_form: Dict[str, Any]) -> bool:
        if home_form.get("data_status") == "partial" or away_form.get("data_status") == "partial":
            return True
        return not home_form.get("comprehensive_analysis") or not away_form.get("comprehensive_analysis")

    def _build_comparative_fallback(self, home_form: Dict[str, Any], away_form: Dict[str, Any]) -> Dict[str, Any]:
        home_team = home_form.get("team_name", "Home team")
        away_team = away_form.get("team_name", "Away team")
        home_sequence = self._form_sequence(home_form)
        away_sequence = self._form_sequence(away_form)
        parts = []
        if home_sequence:
            parts.append(f"{home_team}'s recent-results cue is {home_sequence}.")
        if away_sequence:
            parts.append(f"{away_team}'s recent-results cue is {away_sequence}.")
        if not parts:
            assessment = (
                "Verified comparative form detail is thin in this run. Use the opening phase to judge territory, "
                "pressure resistance, and transition recovery rather than leaning on a pre-match form verdict."
            )
        else:
            assessment = (
                " ".join(parts)
                + " Treat those sequences as context, not a prediction; the useful booth read is whether either side turns it into territory, clean buildup, and repeatable transition defense."
            )
        return {
            "comparative_assessment": assessment,
            "likely_match_narrative": assessment.split(".")[0].strip(),
            "data_status": "partial",
        }

    def _form_sequence(self, form: Dict[str, Any]) -> str:
        recent_form = form.get("recent_form", {}) if isinstance(form, dict) else {}
        sequence = recent_form.get("form_string", "") if isinstance(recent_form, dict) else ""
        return sequence if self._is_meaningful_form_string(sequence) else ""


    async def close(self):
        """Clean up resources."""
        return None
