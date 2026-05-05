"""NarrativeBeat dataclass — pure data model for commentary notes."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class NarrativeBeat:
    """A single narrative beat for commentary notes.

    Attributes:
        text: The narrative text content.
        event_tags: List of canonical event tags associated with this beat.
        players: Player names mentioned in this beat.
        section: Which notes section this beat belongs to.
        source: Data provenance (StatsBomb, Firecrawl, FBref).
        confidence: Confidence score in range 0.0-1.0.
    """

    text: str
    event_tags: List[str]
    players: List[str] = field(default_factory=list)
    section: str = ""
    source: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        """Validate confidence is in valid 0.0-1.0 range."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
