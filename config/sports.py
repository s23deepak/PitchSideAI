"""
Sports Configuration System
Centralized sport definitions, rules, and requirements.
Football (Soccer) only configuration for FIFA World Cup 2026.
"""
from enum import Enum
from typing import Dict, List
from dataclasses import dataclass, field


class SportType(str, Enum):
    """Supported sports - Football only for World Cup 2026."""
    SOCCER = "soccer"


@dataclass
class SportConfig:
    """Configuration for a sport."""
    sport_type: SportType
    display_name: str
    formation_regex: List[str]
    key_metrics: List[str]
    tactical_labels: List[str]
    team_positions: List[str]
    research_topics: List[str]
    tactical_definitions: Dict[str, str] = field(default_factory=dict)


# ── Football (Soccer) Configuration ─────────────────────────────────────────

SOCCER_CONFIG = SportConfig(
    sport_type=SportType.SOCCER,
    display_name="Football",
    formation_regex=["\\d-\\d-\\d", "3-5-2", "4-3-3", "4-4-2", "4-2-3-1", "5-3-2", "3-4-3"],
    key_metrics=[
        "possession %",
        "shots on target",
        "passes completed",
        "pass accuracy %",
        "tackles",
        "interceptions",
        "corners",
        "fouls",
        "yellow cards",
        "red cards",
        "offsides",
        "saves",
        "xG (Expected Goals)"
    ],
    tactical_labels=[
        "High Press",
        "Low Block",
        "Gegenpressing",
        "Counter Attack",
        "Build-Up Play",
        "Possession Play",
        "Direct Play",
        "Transition",
        "Set Piece Attack",
        "Set Piece Defense",
        "Wing Play",
        "Central Play",
        "False 9",
        "Tiki-Taka",
        "Park the Bus",
        "Normal Play"
    ],
    tactical_definitions={
        "High Press": "Attackers aggressively closing down defenders in their own third, often with multiple players swarming the ball carrier.",
        "Low Block": "Defending team packed densely in their own penalty area, making it hard for opponents to penetrate.",
        "Gegenpressing": "Immediate pressing after losing possession, trying to win the ball back within seconds.",
        "Counter Attack": "Rapid transition from defense to attack, exploiting space left by the opposing team.",
        "Build-Up Play": "Patient possession from the back, with defenders and midfielders passing to progress up the field.",
        "Possession Play": "Dominating ball possession with short, controlled passes to control the tempo.",
        "Direct Play": "Long balls forward, bypassing midfield, aiming for quick attacks.",
        "Set Piece Attack": "Structured attack from corners, free kicks, or throw-ins with players positioned in the box.",
        "Set Piece Defense": "Defending players packed densely inside their own penalty area during opponent set pieces.",
        "Wing Play": "Attacks focused on the flanks, with wingers or fullbacks delivering crosses.",
        "Central Play": "Attacks through the middle of the pitch, often involving intricate passing.",
        "False 9": "A striker who drops deep into midfield, creating space for wingers or midfielders to exploit.",
        "Tiki-Taka": "Short, quick passing triangles to maintain possession and probe for openings.",
        "Park the Bus": "Ultra-defensive setup with all players behind the ball, prioritizing defense over attack.",
        "Transition": "The moment of switching from defense to attack or vice versa."
    },
    team_positions=[
        "GK",  # Goalkeeper
        "CB",  # Center Back
        "LB",  # Left Back
        "RB",  # Right Back
        "LWB",  # Left Wing Back
        "RWB",  # Right Wing Back
        "CDM",  # Defensive Midfielder
        "CM",  # Central Midfielder
        "CAM",  # Attacking Midfielder
        "LM",  # Left Midfielder
        "RM",  # Right Midfielder
        "LW",  # Left Winger
        "RW",  # Right Winger
        "ST",  # Striker
        "CF",  # Center Forward
    ],
    research_topics=[
        "recent form (last 5 matches)",
        "head-to-head history",
        "key injuries and suspensions",
        "home/away record",
        "formation preferences",
        "set-piece efficiency",
        "high press tolerance",
        "defensive organization",
        "key player performances",
        "manager tactical approach",
        "goals scored/conceded trends",
        "clean sheet record"
    ]
)


# ── Configuration Access ─────────────────────────────────────────────────────

SPORTS_CONFIG: Dict[SportType, SportConfig] = {
    SportType.SOCCER: SOCCER_CONFIG
}


def get_sport_config(sport: str = "soccer") -> SportConfig:
    """Get configuration for football/soccer."""
    return SOCCER_CONFIG


def get_tactical_labels(sport: str = "soccer") -> List[str]:
    """Get tactical labels for football."""
    return SOCCER_CONFIG.tactical_labels


def get_research_topics(sport: str = "soccer") -> List[str]:
    """Get research topics for football."""
    return SOCCER_CONFIG.research_topics


def get_team_positions(sport: str = "soccer") -> List[str]:
    """Get team positions for football."""
    return SOCCER_CONFIG.team_positions


def get_formation_regex(sport: str = "soccer") -> List[str]:
    """Get formation regex patterns for football."""
    return SOCCER_CONFIG.formation_regex


if __name__ == "__main__":
    # Example usage
    soccer = get_sport_config()
    print(f"Sport: {soccer.display_name}")
    print(f"Tactical Labels: {soccer.tactical_labels[:5]}")
    print(f"Key Metrics: {soccer.key_metrics[:5]}")
    print(f"Formations: {soccer.formation_regex}")
