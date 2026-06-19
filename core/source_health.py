"""
Per-source health registry across all runs. Used to dynamically route queries
away from degraded sources.
"""
from __future__ import annotations

import threading
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import defaultdict


@dataclass
class SourceHealth:
    source_name: str
    total_calls: int = 0
    success_rate: float = 1.0
    avg_duration_ms: float = 0.0
    avg_response_bytes: float = 0.0
    avg_completeness: float = 0.0
    avg_quality: float = 0.0
    consecutive_failures: int = 0
    last_error_at: Optional[datetime] = None
    degraded_since: Optional[datetime] = None
    is_degraded: bool = False

    def mark_degraded(self) -> None:
        self.degraded_since = datetime.now(timezone.utc)
        self.is_degraded = True

    def recover(self) -> None:
        self.is_degraded = False
        self.degraded_since = None
        self.consecutive_failures = 0


class SourceHealthRegistry:
    """Tracks per-source health across all runs."""

    _instance: Optional["SourceHealthRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._sources: dict[str, SourceHealth] = {}
        self._window_size = 100
        self._recent_results: dict[str, list[tuple[float, str]]] = defaultdict(list)
        self._degradation_threshold = 5
        self._initialized = True

    def get(self, source_name: str) -> Optional[SourceHealth]:
        return self._sources.get(source_name)

    def record_fetch(
        self,
        source_name: str,
        success: bool,
        duration_ms: int,
        response_bytes: int,
        completeness: float,
        quality: float,
    ) -> None:
        """Record a fetch result and update rolling health stats."""
        with self._lock:
            if source_name not in self._sources:
                self._sources[source_name] = SourceHealth(source_name=source_name)

            health = self._sources[source_name]
            health.total_calls += 1

            # Rolling window
            recent = self._recent_results[source_name]
            recent.append((quality, "success" if success else "failure"))
            if len(recent) > self._window_size:
                recent.pop(0)

            if recent:
                successes = sum(1 for _, s in recent[-self._window_size:] if s == "success")
                health.success_rate = successes / max(1, len(recent[-self._window_size:]))

            # Running averages
            n = health.total_calls
            health.avg_duration_ms = ((health.avg_duration_ms * (n - 1)) + duration_ms) / n
            health.avg_response_bytes = ((health.avg_response_bytes * (n - 1)) + response_bytes) / n
            health.avg_completeness = ((health.avg_completeness * (n - 1)) + completeness) / n
            health.avg_quality = ((health.avg_quality * (n - 1)) + quality) / n

            if not success:
                health.consecutive_failures += 1
                health.last_error_at = datetime.now(timezone.utc)
                if health.consecutive_failures >= self._degradation_threshold:
                    health.mark_degraded()
            else:
                if health.consecutive_failures >= self._degradation_threshold:
                    health.consecutive_failures = 0
                if health.is_degraded and health.consecutive_failures == 0:
                    health.recover()

    def is_healthy(self, source_name: str) -> bool:
        health = self.get(source_name)
        return not health or not health.is_degraded

    def get_all_health(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "total_calls": h.total_calls,
                "success_rate": round(h.success_rate, 2),
                "avg_quality": round(h.avg_quality, 2),
                "avg_duration_ms": round(h.avg_duration_ms),
                "consecutive_failures": h.consecutive_failures,
                "is_degraded": h.is_degraded,
                "degraded_since": h.degraded_since.isoformat() if h.degraded_since else None,
            }
            for name, h in self._sources.items()
        }


def get_source_health_registry() -> SourceHealthRegistry:
    return SourceHealthRegistry()