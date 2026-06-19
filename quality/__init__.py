"""
quality/__init__.py — Quality package exports.
"""
from quality.evidence import (
    EvidenceItem,
    build_evidence_quality_report,
    classify_source_tier,
    source_tier_priority,
    filter_allowed_search_results,
    validate_search_result,
    validate_scraped_content,
    preferred_domains_for_topic,
    is_allowed_url,
)
from quality.fact_ledger import (
    FactLedgerEntry,
    build_fact_ledger,
)
from quality.notes_quality import (
    NotesQualityScore,
    score_notes,
)
from quality.notes_refinement import (
    evaluate_notes_document,
    refine_notes_document,
)
from quality.response_scorer import score_response

__all__ = [
    "score_response",
    "EvidenceItem",
    "build_evidence_quality_report",
    "classify_source_tier",
    "source_tier_priority",
    "filter_allowed_search_results",
    "validate_search_result",
    "validate_scraped_content",
    "preferred_domains_for_topic",
    "is_allowed_url",
    "FactLedgerEntry",
    "build_fact_ledger",
    "NotesQualityScore",
    "score_notes",
    "evaluate_notes_document",
    "refine_notes_document",
]