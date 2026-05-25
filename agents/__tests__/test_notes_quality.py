from quality.notes_quality import score_notes


def test_notes_quality_flags_structured_tactical_notes_as_low_risk():
    markdown = """
# Commentary Notes: Home vs Away

## Match Frame
- 4-3-3 against 4-2-3-1.

## Tactical Themes
- The press starts from the first line and protects midfield access.

## Key Player Battles
- Watch the fullback height, transition defence, zone control, tempo, set piece marking, and the key duel.

## Team News Caveats
- Confirmed notes only.

## Live-Trigger Beats
- First set piece.
"""
    payload = {
        "beats": [
            {"text": "Press cue", "source": "ESPN", "source_urls": ["https://example.com/press"]},
            {"text": "Tactical cue", "source_attribution": [{"label": "research", "url": "https://example.com/tactical"}]},
        ]
    }

    score = score_notes(markdown, payload)

    assert score.total >= 0.65
    assert score.provenance == 1.0
    assert score.hallucination_risk == 0


def test_notes_quality_does_not_count_empty_source_attribution_as_provenance():
    score = score_notes("## Match Frame\n## Tactical Themes", {
        "beats": [{"text": "Cue", "source": "research", "source_attribution": [{"label": "research", "url": ""}]}],
    })

    assert score.provenance == 0.0


def test_notes_quality_penalizes_placeholders():
    score = score_notes("TODO placeholder {{player}} verified tactical snapshot unavailable", {"beats": []})

    assert score.hallucination_risk > 0
    assert score.total < 0.6
