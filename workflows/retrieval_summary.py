"""Build per-run retrieval audit summary from the ledger for commentary notes."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from core.retrieval_ledger import get_ledger
from core.source_catalog import get_source_tier


def build_retrieval_summary(run_id: str) -> dict[str, Any]:
    """
    Query the ledger for this run and produce:
    - Per-source table: calls, good/bad/marginal counts, avg quality, avg duration
    - Top 5 failures with queries and error messages
    - Recommended sources to prioritize
    - Degraded sources to avoid or cross-verify
    """
    ledger = get_ledger()
    logs = ledger.get_run_logs(run_id)

    if not logs:
        return {
            "total_fetches": 0,
            "good_rate": 0.0,
            "total_duration_ms": 0,
            "source_table": [],
            "top_failures": [],
            "recommendations": {"prioritize": [], "avoid_or_verify": []},
        }

    per_source: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "good": 0, "bad": 0, "marginal": 0, "qualities": [], "durations": []}
    )
    for entry in logs:
        src = per_source[entry.source_name]
        src["calls"] += 1
        if entry.status == "success" and entry.data_quality >= 0.6:
            src["good"] += 1
        elif entry.status in {"empty", "error", "timeout", "blocked"} or entry.data_completeness < 0.3:
            src["bad"] += 1
        else:
            src["marginal"] += 1
        src["qualities"].append(entry.data_quality)
        src["durations"].append(entry.duration_ms)

    source_table: list[dict[str, Any]] = []
    for src_name, stats in sorted(per_source.items(), key=lambda x: x[1]["bad"], reverse=True):
        source_table.append({
            "source": src_name,
            "tier": get_source_tier(src_name),
            "calls": stats["calls"],
            "good": stats["good"],
            "bad": stats["bad"],
            "marginal": stats["marginal"],
            "avg_quality": round(mean(stats["qualities"]), 2) if stats["qualities"] else 0,
            "avg_duration_ms": round(mean(stats["durations"])) if stats["durations"] else 0,
        })

    failures = [entry for entry in logs if entry.status in {"empty", "error", "timeout", "blocked", "rate_limited"}]
    top_failures: list[dict[str, Any]] = []
    for entry in sorted(failures, key=lambda f: f.duration_ms, reverse=True)[:5]:
        top_failures.append({
            "source": entry.source_name,
            "query": entry.query_text[:100],
            "status": entry.status,
            "error": entry.error_message or "",
            "duration_ms": entry.duration_ms,
            "tier": entry.source_tier,
        })

    good_sources: list[str] = [s["source"] for s in source_table if s["good"] >= s["calls"] * 0.7]
    bad_sources: list[str] = [s["source"] for s in source_table if s["bad"] > s["calls"] * 0.5 or s["avg_quality"] < 0.3]

    total_fetches = len(logs)
    good_rate = round(sum(1 for entry in logs if entry.data_quality >= 0.6) / max(1, total_fetches), 2)
    total_duration_ms = sum(entry.duration_ms for entry in logs)

    return {
        "source_table": source_table,
        "top_failures": top_failures,
        "recommendations": {
            "prioritize": good_sources[:5],
            "avoid_or_verify": bad_sources[:5],
        },
        "total_fetches": total_fetches,
        "good_rate": good_rate,
        "total_duration_ms": total_duration_ms,
    }