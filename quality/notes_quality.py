"""Lightweight quality scoring for commentary notes regression tests."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


RISK_PATTERNS = (
    "unavailable 2",
    "lorem ipsum",
    "todo",
    "placeholder",
    "{{",
    "}}",
    "verified tactical snapshot unavailable",
)

REQUIRED_SECTIONS = (
    "MATCH FRAME",
    "TACTICAL THEMES",
    "KEY PLAYER BATTLES",
    "TEAM NEWS CAVEATS",
    "LIVE-TRIGGER BEATS",
)


@dataclass
class NotesQualityScore:
    structure: float
    tactical_depth: float
    precision: float
    provenance: float
    hallucination_risk: float

    @property
    def total(self) -> float:
        return round(
            self.structure * 0.25
            + self.tactical_depth * 0.25
            + self.precision * 0.2
            + self.provenance * 0.15
            + (1.0 - self.hallucination_risk) * 0.15,
            3,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["total"] = self.total
        return payload


def score_notes(markdown: str, notes_payload: dict[str, Any] | None = None) -> NotesQualityScore:
    notes_payload = notes_payload or {}
    upper = markdown.upper()
    structure_hits = sum(1 for section in REQUIRED_SECTIONS if section in upper)
    structure = min(1.0, structure_hits / len(REQUIRED_SECTIONS))

    tactical_terms = (
        "press",
        "transition",
        "midfield",
        "fullback",
        "shape",
        "zone",
        "duel",
        "set piece",
        "line",
        "tempo",
    )
    tactical_depth = min(1.0, sum(markdown.lower().count(term) for term in tactical_terms) / 12)

    numeric_or_specific = sum(char.isdigit() for char in markdown)
    precision = min(1.0, (numeric_or_specific / 20) + (len(markdown) / 16000))

    beats = notes_payload.get("beats") or []
    sourced_beats = [
        beat for beat in beats
        if isinstance(beat, dict) and (
            any(str(url).startswith(("http://", "https://")) for url in (beat.get("source_urls") or []))
            or any(
                isinstance(item, dict) and str(item.get("url", "")).startswith(("http://", "https://"))
                for item in (beat.get("source_attribution") or [])
            )
        )
    ]
    provenance = min(1.0, len(sourced_beats) / max(1, len(beats))) if beats else 0.3

    lowered = markdown.lower()
    risk_hits = sum(1 for pattern in RISK_PATTERNS if pattern in lowered)
    hallucination_risk = min(1.0, risk_hits / 3)

    return NotesQualityScore(
        structure=round(structure, 3),
        tactical_depth=round(tactical_depth, 3),
        precision=round(precision, 3),
        provenance=round(provenance, 3),
        hallucination_risk=round(hallucination_risk, 3),
    )
