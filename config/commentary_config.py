"""
Commentary configuration - Settings for commentary notes preparation system.

Defines API keys, data sources, note generation settings, and output formats.
"""

import os
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from config import LLM_BACKEND, OLLAMA_MODEL, OPENAI_MODEL, VLLM_MODEL

# ===== API Key Configuration =====

EXTERNAL_API_KEYS: Dict[str, Optional[str]] = {
    "espn": os.getenv("ESPN_API_KEY"),
    "openweathermap": os.getenv("OPENWEATHERMAP_API_KEY"),
    "goal_com": os.getenv("GOAL_COM_API_KEY"),
    "cricbuzz": os.getenv("CRICBUZZ_API_KEY"),
    "tavily": os.getenv("TAVILY_API_KEY"),
    "football_data": os.getenv("FOOTBALL_DATA_API_KEY"),
}


# ===== Data Retrieval Settings =====

def _get_commentary_model_ids() -> Dict[str, str]:
    """Return model IDs for commentary agents based on active backend."""
    if LLM_BACKEND == "ollama":
        m = OLLAMA_MODEL
    elif LLM_BACKEND == "openai":
        m = OPENAI_MODEL
    elif LLM_BACKEND == "vllm":
        m = VLLM_MODEL
    else:
        # Bedrock: use differentiated models per role
        return {
            "research": "us.nova-pro-1:0",
            "form": "us.nova-pro-1:0",
            "weather": "us.nova-sonic-1:0",
            "matchup": "us.nova-lite-1:0",
            "news": "us.nova-sonic-1:0",
            "organizer": "us.nova-pro-1:0",
        }
    # Non-Bedrock: single model for all roles
    return {k: m for k in ("research", "form", "weather", "matchup", "news", "organizer")}


@dataclass
class DataRetrievalConfig:
    """Configuration for data retrieval operations."""

    timeout_seconds: int = 30  # Timeout for each API call
    cache_ttl_seconds: int = 3600  # 1 hour cache for team/player stats
    max_retries: int = 3  # Retries on network failures
    cache_backend: str = "memory"  # "memory" or "redis"
    redis_url: Optional[str] = os.getenv("REDIS_URL")


# ===== Note Generation Settings =====

@dataclass
class NoteGenerationConfig:
    """Configuration for note generation."""

    players_per_team: int = 25  # Peter Drury standard: 25 players per team
    recent_matches_to_analyze: int = 5  # How many recent matches to analyze for form
    h2h_history_depth: int = 10  # Number of H2H matches to analyze
    max_matchups_to_feature: int = 5  # Top critical matchups to highlight

    model_ids: Dict[str, str] = field(
        default_factory=lambda: _get_commentary_model_ids()
    )

    # Temperature settings for LLM calls
    temperatures: Dict[str, float] = field(
        default_factory=lambda: {
            "research": 0.3,  # Deterministic for facts
            "form": 0.4,  # Slightly creative
            "historical": 0.5,  # Narrative voice
            "weather": 0.3,  # Deterministic
            "matchup": 0.3,  # Tactical analysis
            "news": 0.2,  # Factual
            "organize": 0.4,  # Synthesis
        }
    )


# ===== Output Settings =====

@dataclass
class OutputConfig:
    """Configuration for output generation."""

    markdown_template: str = "templates/commentary_notes.md"
    include_embedded_json: bool = True
    include_player_photos: bool = False
    max_notes_size_mb: int = 10

    # Output format options
    format: str = "markdown_json"  # "markdown_json", "json_only", "markdown_only"


# ===== Workflow Settings =====

@dataclass
class WorkflowConfig:
    """Configuration for workflow orchestration."""

    max_concurrent_agents: int = 5  # Max agents running in parallel
    workflow_timeout_seconds: int = 120  # 2 minutes for full workflow
    agent_timeout_seconds: int = 30  # Per-agent timeout
    enable_streaming: bool = True  # Stream progress to client
    cache_intermediate_results: bool = True  # Cache agent outputs
    retry_failed_agents: int = 1  # Retries for failed agents


# ===== Global Configuration Instance =====

# Data retrieval
DATA_RETRIEVAL = DataRetrievalConfig()

# Note generation
NOTE_GENERATION = NoteGenerationConfig()

# Output
OUTPUT = OutputConfig()

# Workflow
WORKFLOW = WorkflowConfig()


# ===== Helper Functions =====

def get_model_id(agent_type: str) -> str:
    """Get appropriate model ID for agent type."""
    defaults = _get_commentary_model_ids()
    return NOTE_GENERATION.model_ids.get(agent_type, defaults.get("research", "us.nova-pro-1:0"))


def get_temperature(agent_type: str) -> float:
    """Get temperature setting for agent type."""
    return NOTE_GENERATION.temperatures.get(agent_type, 0.3)


def validate_api_keys() -> Dict[str, bool]:
    """Validate that required API keys are configured."""
    validation = {}
    required_keys = ["openweathermap"]  # Minimum required keys

    for key_name, key_value in EXTERNAL_API_KEYS.items():
        validation[key_name] = key_value is not None and key_value != "mock-key"

    all_required_available = all(
        validation.get(req_key, False) for req_key in required_keys
    )

    return {**validation, "all_available": all_required_available}


if __name__ == "__main__":
    # Print configuration summary
    print("=== Commentary Configuration ===")
    print(f"Players per team: {NOTE_GENERATION.players_per_team}")
    print(f"Max concurrent agents: {WORKFLOW.max_concurrent_agents}")
    print(f"Workflow timeout: {WORKFLOW.workflow_timeout_seconds}s")
    print(f"Output format: {OUTPUT.format}")
    print("\nAPI Keys Status:", validate_api_keys())
