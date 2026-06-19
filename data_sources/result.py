"""
FetchResult — unified return type for every data source fetch.

Every fetch call returns a FetchResult with:
- Data payload, status, quality scores, source URLs
- Built-in classification: is_good, is_bad, is_marginal
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchResult:
    data: dict[str, Any] = field(default_factory=dict)
    raw_bytes: int = 0
    status: str = "success"
    error_message: str = ""
    duration_ms: int = 0
    completeness: float = 0.0
    quality: float = 0.0
    source_tier: int = 3
    source_name: str = ""
    source_urls: list[str] = field(default_factory=list)
    cache_hit: bool = False
    retry_count: int = 0
    placeholder_count: int = 0
    extracted_fields: dict[str, Any] = field(default_factory=dict)

    @property
    def is_good(self) -> bool:
        return self.completeness >= 0.7 and self.quality >= 0.6

    @property
    def is_bad(self) -> bool:
        return self.status in {"empty", "error", "timeout", "blocked"} or self.completeness < 0.3

    @property
    def is_marginal(self) -> bool:
        return not self.is_good and not self.is_bad

    @classmethod
    def empty(cls, source_name: str = "unknown", status: str = "empty") -> FetchResult:
        return cls(
            data={},
            raw_bytes=0,
            status=status,
            source_name=source_name,
            source_tier=3,
            completeness=0.0,
            quality=0.0,
        )