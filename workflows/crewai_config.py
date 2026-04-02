"""
CrewAI configuration - Define agent roles and tasks for multi-agent system.

Configures CrewAI for coordinating specialized commentary research agents.
"""

from dataclasses import dataclass
from typing import Optional


# ===== Agent Roles Definition =====

@dataclass
class AgentRole:
    """Definition of an agent's role in the crew."""

    role: str  # Agent role name
    goal: str  # What the agent is trying to accomplish
    backstory: str  # Agent personality and background
    tools: list = None  # Tools available to agent

    def __post_init__(self):
        if self.tools is None:
            self.tools = []


# ===== Agent Role Definitions =====

PLAYER_RESEARCH_AGENT = AgentRole(
    role="Player Research Specialist",
    goal="Research comprehensive player profiles for 25-player squads",
    backstory="""You are a meticulous sports analyst who specializes in player profiling.
You have deep knowledge of player statistics, playing styles, career trajectories, and
current form. Your role is to provide detailed, accurate profiles for each player on
the team, suitable for professional commentary.""",
    tools=["espn_data_fetcher", "wikipedia_fetcher", "player_stats_analyzer"],
)

TEAM_FORM_AGENT = AgentRole(
    role="Form Analyst",
    goal="Analyze team form, tactical patterns, and performance trends",
    backstory="""You are an expert tactical analyst with deep understanding of how teams
evolve their approach. You analyze recent form, identify tactical patterns, and assess
momentum. Your insights help commentators understand current team dynamics.""",
    tools=["form_analyzer", "tactical_pattern_detector", "statistics_engine"],
)

HISTORICAL_CONTEXT_AGENT = AgentRole(
    role="Historian & Storyteller",
    goal="Build compelling historical narratives and context",
    backstory="""You are a sports historian who specializes in building narrative context.
You understand rivalries, key moments, redemption arcs, and the stories that make
matches special. Your role is to provide the historical and emotional context.""",
    tools=["h2h_analyzer", "historical_database", "narrative_builder"],
)

WEATHER_CONTEXT_AGENT = AgentRole(
    role="Weather & Conditions Analyst",
    goal="Analyze weather impact on tactical play",
    backstory="""You are an expert in how weather affects different sports. You understand
how temperature, wind, humidity, and conditions influence tactical decisions and player
performance. Your contextual analysis helps commentators explain match conditions.""",
    tools=["weather_api", "sport_condition_analyzer", "impact_assessor"],
)

MATCHUP_ANALYSIS_AGENT = AgentRole(
    role="Matchup Specialist",
    goal="Identify critical player matchups and positional battles",
    backstory="""You are a tactical matchup expert who specializes in identifying key
individual battles. You understand player strengths, weaknesses, and how different
playing styles interact. Your analysis highlights the human drama behind team tactics.""",
    tools=["matchup_analyzer", "player_comparison_engine", "tactical_predictor"],
)

NEWS_AGENT = AgentRole(
    role="News Correspondent",
    goal="Gather current team news, injuries, and lineup information",
    backstory="""You are an up-to-date sports journalist who specializes in team news.
You know the latest on injuries, suspensions, transfers, and tactical adjustments.
Your information is current, accurate, and crucial for understanding match context.""",
    tools=["news_aggregator", "injury_tracker", "lineup_confirmer"],
)

NOTE_ORGANIZER_AGENT = AgentRole(
    role="Commentary Notes Organizer",
    goal="Synthesize all research into professional Drury-style notes",
    backstory="""You are a professional commentary notes organizer inspired by Peter Drury.
You take all research from other agents and synthesize it into clear, organized,
compelling notes structured for professional sports commentary.""",
    tools=["note_formatter", "markdown_generator", "json_builder"],
)


# ===== Task Definition =====

@dataclass
class TaskDefinition:
    """Definition of a task for agents to complete."""

    description: str  # What needs to be done
    agent_role: str  # Which agent performs this task
    expected_output: str  # What the output should contain
    async_execution: bool = True  # Run asynchronously?


# ===== Task Definitions =====

TASKS = {
    "research_home_squad": TaskDefinition(
        description="Research the home team's starting XI and squad",
        agent_role="Player Research Specialist",
        expected_output="Complete player profiles for 25 home team players including statistics, playing style, recent form",
        async_execution=True,
    ),
    "research_away_squad": TaskDefinition(
        description="Research the away team's starting XI and squad",
        agent_role="Player Research Specialist",
        expected_output="Complete player profiles for 25 away team players including statistics, playing style, recent form",
        async_execution=True,
    ),
    "analyze_home_form": TaskDefinition(
        description="Analyze home team's recent form and tactical patterns",
        agent_role="Form Analyst",
        expected_output="Form analysis including W-D-L record, goals, tactical approach, current momentum",
        async_execution=True,
    ),
    "analyze_away_form": TaskDefinition(
        description="Analyze away team's form and tactical evolution",
        agent_role="Form Analyst",
        expected_output="Form analysis with tactical insights specific to away performance",
        async_execution=True,
    ),
    "gather_historical_context": TaskDefinition(
        description="Build H2H history and key storylines",
        agent_role="Historian & Storyteller",
        expected_output="H2H record, recent match patterns, key narrative elements and storylines",
        async_execution=True,
    ),
    "analyze_weather": TaskDefinition(
        description="Get weather conditions and analyze tactical impact",
        agent_role="Weather & Conditions Analyst",
        expected_output="Current weather conditions, forecast, sport-specific tactical impact analysis",
        async_execution=True,
    ),
    "identify_matchups": TaskDefinition(
        description="Identify critical player matchups and positional battles",
        agent_role="Matchup Specialist",
        expected_output="Key 1v1 matchups, positional strengths/weaknesses, likely tactical battles",
        async_execution=True,
    ),
    "gather_team_news": TaskDefinition(
        description="Gather current news, injuries, and lineups for both teams",
        agent_role="News Correspondent",
        expected_output="Team news summary, injuries, suspensions, lineup confirmation status, late changes",
        async_execution=True,
    ),
    "synthesize_commentary_notes": TaskDefinition(
        description="Synthesize all research into final professional commentary notes",
        agent_role="Commentary Notes Organizer",
        expected_output="Professional Markdown + JSON commentary notes in Drury style, ready for commentary",
        async_execution=False,  # Final synthesis - run after all others
    ),
}


# ===== Crew Configuration =====

CREW_CONFIG = {
    "agents": [
        PLAYER_RESEARCH_AGENT,
        TEAM_FORM_AGENT,
        HISTORICAL_CONTEXT_AGENT,
        WEATHER_CONTEXT_AGENT,
        MATCHUP_ANALYSIS_AGENT,
        NEWS_AGENT,
        NOTE_ORGANIZER_AGENT,
    ],
    "tasks": list(TASKS.values()),
    "verbose": True,
    "max_iterations": 1,
    "max_concurrent_tasks": 5,  # Run up to 5 agents in parallel
}


# ===== Helper Functions =====

def get_agent_for_role(role: str) -> Optional[AgentRole]:
    """Get agent configuration for a given role."""
    agent_map = {
        "Player Research Specialist": PLAYER_RESEARCH_AGENT,
        "Form Analyst": TEAM_FORM_AGENT,
        "Historian & Storyteller": HISTORICAL_CONTEXT_AGENT,
        "Weather & Conditions Analyst": WEATHER_CONTEXT_AGENT,
        "Matchup Specialist": MATCHUP_ANALYSIS_AGENT,
        "News Correspondent": NEWS_AGENT,
        "Commentary Notes Organizer": NOTE_ORGANIZER_AGENT,
    }
    return agent_map.get(role)


def get_parallel_tasks() -> list:
    """Get tasks that can run in parallel (before synthesis)."""
    return [
        task for task_name, task in TASKS.items()
        if task.async_execution and task_name != "synthesize_commentary_notes"
    ]


def get_sequential_tasks() -> list:
    """Get tasks that must run sequentially (synthesis)."""
    return [task for task in TASKS.values() if not task.async_execution]


if __name__ == "__main__":
    print("=== CrewAI Configuration ===")
    print(f"Number of agents: {len(CREW_CONFIG['agents'])}")
    print(f"Number of tasks: {len(CREW_CONFIG['tasks'])}")
    print(f"Max concurrent: {CREW_CONFIG['max_concurrent_tasks']}")
    print("\nAgent Roles:")
    for agent in CREW_CONFIG["agents"]:
        print(f"  - {agent.role}: {agent.goal}")
