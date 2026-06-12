from quality.fact_ledger import build_fact_ledger
from quality.notes_refinement import evaluate_notes_document, refine_notes_document


def test_fact_ledger_marks_one_source_preview_as_preview_supported():
    ledger = build_fact_ledger({
        "quality_report": {"accepted_evidence": []},
        "targeted_evidence": {
            "results_by_topic": {
                "tactical": [{
                    "title": "Korea Republic v Czechia tactical preview",
                    "content": "Preview expects Czechia to threaten from set pieces.",
                    "url": "https://www.sportsmole.co.uk/football/korea-republic/preview.html",
                    "source": "exa",
                }]
            }
        },
    })

    assert ledger["counts"]["preview_supported"] == 1
    assert ledger["entries"][0]["status"] == "preview_supported"
    assert "softer attribution" in ledger["entries"][0]["guidance"].lower() or "preview" in ledger["entries"][0]["guidance"].lower()


def test_fact_ledger_marks_official_or_structured_sources_verified():
    ledger = build_fact_ledger({
        "quality_report": {
            "accepted_evidence": [{
                "claim": "Fixture page available",
                "topic": "fixture",
                "source_name": "FIFA",
                "url": "https://www.fifa.com/en/match-centre/match/fixture",
                "source_tier": "official",
                "confidence": 0.95,
            }]
        },
        "targeted_evidence": {"results_by_topic": {}},
    })

    assert ledger["counts"]["verified"] == 1
    assert ledger["entries"][0]["status"] == "verified"


def test_notes_refinement_softens_unsupported_h2h_age_and_final_world_cup_claims():
    markdown = """# Broadcast Prep: Korea Republic vs Czechia

## Match Frame

These teams have met exactly once. Son is 34 years old and this is his final World Cup.
He was born the same year the Berlin Wall fell.
"""
    ledger = {
        "entries": [],
        "protected_claims": {
            "exact_h2h_count": "unverified",
            "no_injuries": "unverified",
            "final_world_cup": "unverified",
            "exact_player_age": "unverified",
        },
    }

    evaluation = evaluate_notes_document(
        markdown,
        fact_ledger=ledger,
        quality_report={"accepted_evidence_count": 0, "degraded_sections": []},
        beats=[],
    )
    refined = refine_notes_document(
        markdown,
        evaluation=evaluation,
        fact_ledger=ledger,
        home_team="Korea Republic",
        away_team="Czechia",
    )

    assert evaluation["unsupported_claims"]
    assert "met exactly once" not in refined
    assert "34 years old" not in refined
    assert "final World Cup" not in refined
    assert "Berlin Wall" not in refined
    assert "### Narrative Spine" in refined
    assert "### Set-Piece Watch" in refined
    assert "## Fact-Check Notes" in refined
