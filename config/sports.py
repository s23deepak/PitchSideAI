"""
Sports Configuration System
Centralized sport definitions, rules, and requirements.
"""
from enum import Enum
from typing import Dict, List
from dataclasses import dataclass, field


class SportType(str, Enum):
    """Supported sports."""
    SOCCER = "soccer"
    CRICKET = "cricket"
    BASKETBALL = "basketball"
    TENNIS = "tennis"
    RUGBY = "rugby"
    AMERICAN_FOOTBALL = "american_football"
    HOCKEY = "hockey"
    BASEBALL = "baseball"


@dataclass
class SportConfig:
    """Configuration for a sport."""
    sport_type: SportType
    display_name: str
    formation_regex: List[str]  # e.g., ["4-3-3", "3-5-2"] for soccer
    key_metrics: List[str]  # Sport-specific metrics
    tactical_labels: List[str]  # Sport-specific tactical classifications
    team_positions: List[str]  # Key player positions
    research_topics: List[str]  # Topics to research pre-match

    def __hash__(self):
        return hash(self.sport_type.value)


# ── Sport-Specific Configurations ────────────────────────────────────────────

SPORTS_CONFIG: Dict[SportType, SportConfig] = {
    SportType.SOCCER: SportConfig(
        sport_type=SportType.SOCCER,
        display_name="Soccer/Football",
        formation_regex=["\\d-\\d-\\d", "3-5-2", "4-3-3", "5-3-2"],
        key_metrics=[
            "possession %",
            "shots on target",
            "passes completed",
            "tackles",
            "interceptions",
            "corners",
            "fouls",
            "yellow cards",
            "offside positions"
        ],
        tactical_labels=[
            "High Press",
            "Low Block",
            "Gegenpressing",
            "Counter Attack",
            "Build-Up Play",
            "Transition",
            "Set Piece Attack",
            "Set Piece Defense",
            "Wing Play",
            "Central Play",
            "Normal Play"
        ],
        team_positions=[
            "GK",
            "CB",
            "LB",
            "RB",
            "LWB",
            "RWB",
            "CM",
            "CDM",
            "CAM",
            "ST",
            "CF",
            "LW",
            "RW",
            "LM",
            "RM"
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
            "manager tactical approach"
        ]
    ),

    SportType.CRICKET: SportConfig(
        sport_type=SportType.CRICKET,
        display_name="Cricket",
        formation_regex=[],  # Not applicable
        key_metrics=[
            "runs scored",
            "wickets lost",
            "run rate",
            "dot ball %",
            "four boundaries",
            "six boundaries",
            "maiden overs",
            "economy rate",
            "strike rate",
            "average"
        ],
        tactical_labels=[
            "Aggressive Batting",
            "Defensive Batting",
            "Pace Attack",
            "Spin Attack",
            "Death Bowling",
            "Powerplay",
            "Middle Overs",
            "Death Overs",
            "Field Spread",
            "In-Field",
            "Normal"
        ],
        team_positions=[
            "Batsman",
            "Bowler",
            "All-rounder",
            "Wicket-keeper",
            "Opening Batsman",
            "Middle Order",
            "Lower Order",
            "Fast Bowler",
            "Spinner"
        ],
        research_topics=[
            "recent form (last 10 matches)",
            "head-to-head records",
            "key player stats (runs, wickets)",
            "home/away performance",
            "pitch conditions (historically)",
            "weather forecasts",
            "team combinations",
            "batting order preferences",
            "bowling strategies",
            "powerplay performance"
        ]
    ),

    SportType.BASKETBALL: SportConfig(
        sport_type=SportType.BASKETBALL,
        display_name="Basketball",
        formation_regex=[],
        key_metrics=[
            "points per game",
            "field goal %",
            "3-point %",
            "free throw %",
            "rebounds",
            "assists",
            "steals",
            "blocks",
            "turnovers",
            "+/-"
        ],
        tactical_labels=[
            "Zone Defense",
            "Man-to-Man",
            "Full Court Press",
            "Pick and Roll",
            "Fast Break",
            "Isolation",
            "Spacing",
            "Transition",
            "Half Court Set"
        ],
        team_positions=[
            "Point Guard",
            "Shooting Guard",
            "Small Forward",
            "Power Forward",
            "Center"
        ],
        research_topics=[
            "recent form",
            "head-to-head matchups",
            "key player performances",
            "defensive schemes",
            "bench depth",
            "injury reports",
            "pace of play",
            "three-point shooting trends",
            "rebounding strength",
            "turnover rates"
        ]
    ),

    SportType.RUGBY: SportConfig(
        sport_type=SportType.RUGBY,
        display_name="Rugby",
        formation_regex=[],
        key_metrics=[
            "tries scored",
            "points",
            "tackles made",
            "tackles missed" ,
            "turnovers won",
            "lineout win %",
            "scrum dominance",
            "penalties conceded",
            "yellow cards",
            "red cards"
        ],
        tactical_labels=[
            "Scrum Attack",
            "Lineout Drive",
            "Backs Attack",
            "Defensive Formation",
            "Kickoff Play",
            "Breakdown",
            "Ruck Control",
            "Maul Attack",
            "Set Phase",
            "Open Play"
        ],
        team_positions=[
            "Hooker",
            "Prop",
            "Lock",
            "Flanker",
            "Number 8",
            "Scrum-half",
            "Fly-half",
            "Wing",
            "Centre",
            "Full-back"
        ],
        research_topics=[
            "recent results",
            "head-to-head records",
            "player injuries",
            "scrum strength",
            "lineout accuracy",
            "backline pace",
            "defensive patterns",
            "set-piece dominance",
            "bench impact",
            "altitude/weather factors"
        ]
    ),

    SportType.TENNIS: SportConfig(
        sport_type=SportType.TENNIS,
        display_name="Tennis",
        formation_regex=[],
        key_metrics=[
            "serve speed",
            "1st serve %",
            "ace count",
            "break point conversion",
            "rally win %",
            "net approach %",
            "winners",
            "unforced errors",
            "double faults"
        ],
        tactical_labels=[
            "Serve and Volley",
            "Baseline Rally",
            "Aggressive Serve",
            "Defensive Return",
            "Net Play",
            "Slice Attack",
            "Topspin Forehand",
            "Break Point Save",
            "Tire Opponent",
            "Aggressive Serve"
        ],
        team_positions=[],  # Singles/Doubles
        research_topics=[
            "recent tournament results",
            "head-to-head record",
            "surface preference",
            "recent form (last 10 matches)",
            "serve consistency",
            "mental toughness history",
            "injury history",
            "surface-specific strengths",
            "key shots (forehand, backhand)",
            "fitness level"
        ]
    ),
}


def get_sport_config(sport: str) -> SportConfig:
    """Get configuration for a sport."""
    try:
        sport_type = SportType(sport.lower())
        return SPORTS_CONFIG[sport_type]
    except (KeyError, ValueError):
        raise ValueError(
            f"Unsupported sport: {sport}. "
            f"Supported: {', '.join([s.value for s in SportType])}"
        )


def get_tactical_labels(sport: str) -> List[str]:
    """Get tactical labels for a sport."""
    config = get_sport_config(sport)
    return config.tactical_labels


def get_research_topics(sport: str) -> List[str]:
    """Get research topics for a sport."""
    config = get_sport_config(sport)
    return config.research_topics


def get_team_positions(sport: str) -> List[str]:
    """Get team positions for a sport."""
    config = get_sport_config(sport)
    return config.team_positions


if __name__ == "__main__":
    # Example usage
    soccer = get_sport_config("soccer")
    print(f"Sport: {soccer.display_name}")
    print(f"Tactical Labels: {soccer.tactical_labels[:3]}")
    print(f"Key Metrics: {soccer.key_metrics[:3]}")
