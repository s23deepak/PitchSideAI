"""
Deterministic scoring function for every raw response before it enters an agent.
No LLM guessing about quality — pure heuristics based on response size,
placeholder count, source tier, and status.
"""
from __future__ import annotations

from typing import Any


def score_response(
    response_bytes: int,
    extracted_fields: dict[str, Any] | None = None,
    status: str = "success",
    source_tier: int = 3,
) -> tuple[float, float]:
    """Returns (completeness_score, quality_score) both 0-1.

    Completeness: how much data we got vs what we asked for
    Quality: how reliable/accurate that data is
    """
    fields = extracted_fields or {}

    # Base penalties — no data at all
    if status == "empty":
        return (0.0, 0.0)
    if status == "error":
        return (0.0, 0.0)
    if status == "timeout":
        return (0.0, 0.0)
    if status == "rate_limited":
        return (0.05, 0.0)
    if status == "blocked":
        return (0.05, 0.0)

    # Response size heuristic
    if response_bytes < 100:
        return (0.1, 0.0)
    if response_bytes < 500:
        return (0.3, 0.3)

    # Placeholder penalty
    placeholders = fields.get("placeholder_count", 0)
    field_count = max(1, sum(
        v for k, v in fields.items()
        if k != "placeholder_count" and isinstance(v, (int, float))
    ))
    if field_count == 1:
        field_count = max(1, len(fields) - (1 if "placeholder_count" in fields else 0))
    placeholder_ratio = placeholders / field_count if field_count > 0 else 1.0

    completeness = max(0.0, 1.0 - (placeholder_ratio * 0.8))

    # Quality starts from completeness, then penalized for placeholders
    quality = max(0.0, completeness - (placeholder_ratio * 0.3))

    # Source tier bonus/malus
    if source_tier == 1:
        quality = min(1.0, quality + 0.15)
    if source_tier == 3:
        quality = max(0.0, quality - 0.1)
    if source_tier == 4:
        quality = max(0.0, quality - 0.05)

    return (round(completeness, 2), round(quality, 2))