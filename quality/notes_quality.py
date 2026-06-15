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
    "balanced on verified data",
)

REQUIRED_SECTIONS = (
    "MATCH FRAME",
    "AIR-READY RUNDOWN",
    "NARRATIVE SPINE",
    "TACTICAL DOSSIER",
    "SET-PIECE WATCH",
    "TEAM NEWS CAVEATS",
    "LIVE TRIGGER LINES",
)


@dataclass
class NotesQualityScore:
    structure: float
    tactical_depth: float
    precision: float
    provenance: float
    hallucination_risk: float
    evidence_strength: float = 0.5
    on_air_usability: float = 0.5
    score_cap: float = 1.0

    @property
    def total(self) -> float:
        raw = (
            self.structure * 0.25
            + self.tactical_depth * 0.2
            + self.precision * 0.15
            + self.provenance * 0.15
            + self.evidence_strength * 0.15
            + self.on_air_usability * 0.1
            + (1.0 - self.hallucination_risk) * 0.15
        )
        return round(min(raw, self.score_cap), 3)

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
    generic_hits = lowered.count("balanced on verified data") + lowered.count("no verified season-stat edge")
    hallucination_risk = min(1.0, hallucination_risk + min(0.35, generic_hits * 0.08))

    quality_report = notes_payload.get("quality_report") or {}
    accepted_count = int(quality_report.get("accepted_evidence_count") or 0) if isinstance(quality_report, dict) else 0
    degraded_count = len(quality_report.get("degraded_sections") or []) if isinstance(quality_report, dict) else 0
    if isinstance(quality_report, dict) and "accepted_evidence_count" in quality_report:
        evidence_strength = min(1.0, accepted_count / 4)
        score_cap = 0.62 if accepted_count == 0 else 1.0
        if degraded_count >= 4:
            score_cap = min(score_cap, 0.82)
    else:
        evidence_strength = provenance
        score_cap = 1.0

    on_air_markers = (
        "ready to say",
        "watch, say, prove",
        "wait for confirmation",
        "live trigger lines",
        "15-second opener",
    )
    on_air_usability = min(1.0, sum(1 for marker in on_air_markers if marker in lowered) / 4)

    return NotesQualityScore(
        structure=round(structure, 3),
        tactical_depth=round(tactical_depth, 3),
        precision=round(precision, 3),
        provenance=round(provenance, 3),
        hallucination_risk=round(hallucination_risk, 3),
        evidence_strength=round(evidence_strength, 3),
        on_air_usability=round(on_air_usability, 3),
        score_cap=round(score_cap, 3),
    )
