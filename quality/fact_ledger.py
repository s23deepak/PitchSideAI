"""Typed fact ledger for commentary notes grounding."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

from quality.evidence import classify_source_tier, source_tier_priority


@dataclass
class FactLedgerEntry:
    claim: str
    topic: str
    status: str
    sources: list[dict[str, str]]
    confidence: float
    guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_fact_ledger(all_outputs: dict[str, Any]) -> dict[str, Any]:
    """Build claim-level status buckets from accepted evidence and targeted search."""
    entries: list[FactLedgerEntry] = []
    quality_report = all_outputs.get("quality_report") if isinstance(all_outputs.get("quality_report"), dict) else {}

    for item in quality_report.get("accepted_evidence", []) or []:
        if not isinstance(item, dict):
            continue
        entries.append(_entry_from_evidence_item(item))

    targeted = all_outputs.get("targeted_evidence") if isinstance(all_outputs.get("targeted_evidence"), dict) else {}
    for topic, results in (targeted.get("results_by_topic") or {}).items():
        topic_results = [result for result in results or [] if isinstance(result, dict)]
        if not topic_results:
            entries.append(FactLedgerEntry(
                claim=f"{topic} evidence unavailable",
                topic=str(topic),
                status="unverified",
                sources=[],
                confidence=0.0,
                guidance="Do not state this topic as fact.",
            ))
            continue
        entries.extend(_entries_from_search_results(str(topic), topic_results))

    counts: dict[str, int] = {"verified": 0, "preview_supported": 0, "conflicting": 0, "unverified": 0}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1

    protected_claims = _protected_claim_status(entries)
    return {
        "entries": [entry.to_dict() for entry in entries],
        "counts": counts,
        "protected_claims": protected_claims,
        "strict_mode": True,
    }


def _entry_from_evidence_item(item: dict[str, Any]) -> FactLedgerEntry:
    tier = str(item.get("source_tier") or classify_source_tier(str(item.get("url") or ""), str(item.get("source_name") or "")))
    status = "verified" if source_tier_priority(tier) <= source_tier_priority("structured") else "preview_supported"
    return FactLedgerEntry(
        claim=str(item.get("claim") or "").strip(),
        topic=str(item.get("topic") or "general"),
        status=status,
        sources=[{
            "title": str(item.get("source_name") or item.get("source") or item.get("url") or "source"),
            "url": str(item.get("url") or item.get("source_url") or ""),
            "tier": tier,
        }],
        confidence=float(item.get("confidence") or (0.88 if status == "verified" else 0.68)),
        guidance=(
            "Safe as a hard fact."
            if status == "verified"
            else "Use softer attribution such as 'reports suggest' or 'preview evidence points to'."
        ),
    )


def _entries_from_search_results(topic: str, results: list[dict[str, Any]]) -> list[FactLedgerEntry]:
    by_claim: list[FactLedgerEntry] = []
    domains = {_domain(str(result.get("url") or "")) for result in results}
    domains.discard("")
    best_tier_priority = min(
        (source_tier_priority(classify_source_tier(str(result.get("url") or ""), str(result.get("source") or ""))) for result in results),
        default=source_tier_priority("untrusted"),
    )
    hard_verified = best_tier_priority <= source_tier_priority("structured") or len(domains) >= 2

    for result in results[:5]:
        title = str(result.get("title") or "").strip()
        content = str(result.get("content") or "").strip()
        claim = title or content[:180]
        if not claim:
            continue
        tier = classify_source_tier(str(result.get("url") or ""), str(result.get("source") or ""))
        status = "verified" if hard_verified and source_tier_priority(tier) <= source_tier_priority("trusted_media") else "preview_supported"
        by_claim.append(FactLedgerEntry(
            claim=claim[:300],
            topic=topic,
            status=status,
            sources=[{"title": title or _domain(str(result.get("url") or "")), "url": str(result.get("url") or ""), "tier": tier}],
            confidence=0.86 if status == "verified" else 0.66,
            guidance=(
                "Safe as a hard fact when phrased close to source wording."
                if status == "verified"
                else "Treat as preview-supported, not confirmed match truth."
            ),
        ))
    return by_claim


def _protected_claim_status(entries: list[FactLedgerEntry]) -> dict[str, str]:
    text = " ".join(entry.claim.lower() for entry in entries if entry.status == "verified")
    return {
        "exact_h2h_count": "verified" if "head-to-head" in text or "h2h" in text else "unverified",
        "no_injuries": "verified" if "no injuries" in text or "no injury" in text else "unverified",
        "final_world_cup": "verified" if "final world cup" in text or "last world cup" in text else "unverified",
        "exact_player_age": "verified" if " age " in f" {text} " or "years old" in text else "unverified",
    }


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host
