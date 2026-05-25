"""Validation helpers for the live-session WebSocket contract."""

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


SupportedLiveSport = Literal[
    "soccer",
    "cricket",
    "basketball",
    "tennis",
    "rugby",
    "american_football",
    "hockey",
    "baseball",
]


class LiveInitMessage(BaseModel):
    type: Literal["init"] = "init"
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    sport: SupportedLiveSport = "soccer"
    competition: str = Field(default="", max_length=160)


def parse_live_init_message(payload: dict[str, Any]) -> LiveInitMessage:
    """Return a normalized live-session init message or raise ValueError."""
    normalized_payload = {
        **payload,
        "sport": str(payload.get("sport", "soccer")).strip().lower(),
    }
    try:
        message = LiveInitMessage.model_validate(normalized_payload)
    except ValidationError as exc:
        raise ValueError("Invalid live session init payload") from exc

    home_team = message.home_team.strip()
    away_team = message.away_team.strip()
    competition = message.competition.strip()
    if not home_team or not away_team:
        raise ValueError("home_team and away_team are required")

    return message.model_copy(
        update={
            "home_team": home_team,
            "away_team": away_team,
            "sport": message.sport.strip().lower(),
            "competition": competition,
        }
    )
