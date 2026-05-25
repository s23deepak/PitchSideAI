import pytest

from models.narrative_beat import NarrativeBeat
from models.notes_jobs import build_vlm_context_payload
from models.notes_store import NotesStore
from workflows.live_notes_patch_workflow import LiveNotesPatchState, LiveNotesPatchWorkflow


@pytest.mark.asyncio
async def test_live_substitution_patch_updates_notes_and_vlm_context():
    base_store = NotesStore(
        raw_markdown="# Commentary Notes\n\n## PAGE 1: LINEUPS\n\n- Original lineup cue.",
        beats=[
            NarrativeBeat(
                text="Original lineup cue.",
                event_tags=["substitution"],
                section="lineups",
                source="fixture",
                confidence=0.8,
            )
        ],
    )

    result = await LiveNotesPatchWorkflow().run(
        LiveNotesPatchState(
            match_id="match-1",
            match_session="soccer#home#vs#away",
            event_id="event-1",
            event_type="substitution",
            description="Substitution: Player In on for Player Out.",
            source="vlm_detection",
            confidence=0.91,
            payload={"player_in": "Player In", "player_out": "Player Out"},
            notes_store_payload=base_store.to_dict(),
        )
    )

    assert result.patched_notes_store is not None
    assert "LIVE MATCH UPDATES" in result.patched_notes_store.raw_markdown
    assert "Substitution" in result.patch_summary
    assert result.impacted_sections == ["lineups", "player_profiles", "tactical_profile", "matchups"]
    assert result.vlm_context["latest_patch"]["event_id"] == "event-1"


def test_vlm_context_payload_is_versioned_and_compact():
    store = NotesStore(
        raw_markdown="# Notes\n\n" + ("A tactical note. " * 1000),
        beats=[
            NarrativeBeat(
                text="A tactical note.",
                event_tags=["goal"],
                section="storylines",
                source="test",
                confidence=0.7,
            )
        ],
    )

    payload = build_vlm_context_payload(store, notes_version=4, vlm_context_version=7, max_chars=120)

    assert payload["notes_version"] == 4
    assert payload["vlm_context_version"] == 7
    assert len(payload["markdown_context"]) <= 120
    assert payload["lookup_tags"] == ["goal"]
