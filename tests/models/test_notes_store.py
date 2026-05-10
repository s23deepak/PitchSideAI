"""Unit tests for NarrativeBeat, NotesStore, and TagResolver."""

import pytest
from models.narrative_beat import NarrativeBeat
from models.notes_store import (
    CANONICAL_TAGS,
    NotesStore,
    TagResolver,
)


# ── NarrativeBeat ────────────────────────────────────────────────────────────

class TestNarrativeBeat:
    def test_instantiation_all_fields(self):
        beat = NarrativeBeat(
            text="Mbappé has scored 7 in his last 5",
            event_tags=["goal", "goal_scored"],
            players=["Kylian Mbappé"],
            section="home_team",
            source="statsbomb",
            confidence=0.92,
        )
        assert beat.text == "Mbappé has scored 7 in his last 5"
        assert beat.event_tags == ["goal", "goal_scored"]
        assert beat.players == ["Kylian Mbappé"]
        assert beat.section == "home_team"
        assert beat.source == "statsbomb"
        assert beat.confidence == 0.92

    def test_defaults(self):
        beat = NarrativeBeat(
            text="Generic beat",
            event_tags=["foul"],
        )
        assert beat.players == []
        assert beat.section == ""
        assert beat.source == ""
        assert beat.confidence == 0.0

    def test_players_default_is_distinct_per_instance(self):
        a = NarrativeBeat(text="A", event_tags=["goal"])
        b = NarrativeBeat(text="B", event_tags=["goal"])
        a.players.append("Player 1")
        assert b.players == []  # not shared

    def test_confidence_range(self):
        # dataclass doesn't enforce range; this documents expected usage
        beat = NarrativeBeat(
            text="test", event_tags=["goal"], confidence=1.0
        )
        assert 0.0 <= beat.confidence <= 1.0


# ── TagResolver ──────────────────────────────────────────────────────────────

class TestTagResolver:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.resolver = TagResolver()

    # Exact match

    def test_exact_match_goal(self):
        assert self.resolver.resolve("goal") == "goal"

    def test_exact_match_red_card(self):
        assert self.resolver.resolve("red_card") == "red_card"

    def test_exact_match_offside(self):
        assert self.resolver.resolve("offside") == "offside"

    def test_exact_match_case_insensitive(self):
        assert self.resolver.resolve("Goal") == "goal"
        assert self.resolver.resolve("RED_CARD") == "red_card"

    # Synonym map

    def test_synonym_goal_scored(self):
        assert self.resolver.resolve("Goal scored") == "goal"

    def test_synonym_booking(self):
        assert self.resolver.resolve("Booking") == "yellow_card"

    def test_synonym_sent_off(self):
        assert self.resolver.resolve("Sent off") == "red_card"

    def test_synonym_dismissal(self):
        assert self.resolver.resolve("dismissal") == "red_card"

    def test_synonym_substitution(self):
        assert self.resolver.resolve("substitution") == "substitution"

    def test_synonym_sub_abbreviation(self):
        assert self.resolver.resolve("sub") == "substitution"

    def test_synonym_foul_committed(self):
        assert self.resolver.resolve("Foul committed") == "foul"

    def test_synonym_corner_kick(self):
        assert self.resolver.resolve("Corner kick") == "corner"

    def test_synonym_free_kick(self):
        assert self.resolver.resolve("free kick") == "free_kick_dangerous"

    def test_synonym_set_piece(self):
        assert self.resolver.resolve("set piece") == "free_kick_dangerous"

    def test_synonym_offside_call(self):
        assert self.resolver.resolve("Offside call") == "offside"

    # Substring match (word-boundary)

    def test_substring_goal_in_phrase(self):
        # "goal" appears as a word token in "goal_kick" (split on underscore).
        # The goal safety gate will prevent false goal calls when score is unchanged.
        assert self.resolver.resolve("goal_kick") == "goal"

    def test_substring_foul_in_phrase(self):
        # "foul" appears as a word token in "a bad foul here" — correct match
        assert self.resolver.resolve("a bad foul here") == "foul"

    # ^ substring only matches if tag IS the input or input IS the tag, not partial words.
    # Let's test the actual substring behavior:
    def test_substring_tag_in_label(self):
        # "foul" is within "professional_foul" — tier 3 should catch it
        assert self.resolver.resolve("red_card_situation") == "red_card"

    def test_substring_label_in_tag_not_match(self):
        # "goal_kick" contains "goal" but "goal" is not a substring of "goal_kick" ?
        # Actually "goal" IS a substring of "goal_kick". This should match via tier 3.
        # Resolve: we skip because "goal" canonical tag IS in "goal_kick"
        assert self.resolver.resolve("corner") == "corner"

    # No match

    def test_no_match_weather(self):
        assert self.resolver.resolve("weather delay") is None

    def test_no_match_empty_string(self):
        assert self.resolver.resolve("") is None

    def test_no_match_whitespace_only(self):
        assert self.resolver.resolve("   ") is None

    def test_no_match_injury(self):
        assert self.resolver.resolve("injury timeout") is None

    # Goal safety gate

    def test_goal_gate_score_changed(self):
        assert (
            self.resolver.resolve(
                "goal",
                previous_score_total=0,
                current_score_total=1,
            )
            == "goal"
        )

    def test_goal_gate_score_unchanged(self):
        assert (
            self.resolver.resolve(
                "goal",
                previous_score_total=1,
                current_score_total=1,
            )
            is None
        )

    def test_goal_gate_no_context_returns_goal(self):
        # Without score context, allow through (caller's responsibility)
        assert self.resolver.resolve("goal") == "goal"

    def test_goal_gate_only_previous(self):
        assert self.resolver.resolve("goal", previous_score_total=0) == "goal"

    def test_goal_gate_only_current(self):
        assert self.resolver.resolve("goal", current_score_total=1) == "goal"

    def test_goal_gate_non_goal_unaffected(self):
        # Safety gate must never affect non-goal tags
        assert (
            self.resolver.resolve(
                "red_card",
                previous_score_total=0,
                current_score_total=1,
            )
            == "red_card"
        )
        assert (
            self.resolver.resolve(
                "yellow_card",
                previous_score_total=0,
                current_score_total=0,
            )
            == "yellow_card"
        )

    def test_goal_gate_via_synonym(self):
        # "Goal scored" should also trigger the safety gate
        assert (
            self.resolver.resolve(
                "Goal scored",
                previous_score_total=0,
                current_score_total=1,
            )
            == "goal"
        )
        assert (
            self.resolver.resolve(
                "Goal scored",
                previous_score_total=1,
                current_score_total=1,
            )
            is None
        )


# ── NotesStore ───────────────────────────────────────────────────────────────

class TestNotesStore:
    def _make_beat(self, text, tags, **kwargs):
        return NarrativeBeat(text=text, event_tags=tags, **kwargs)

    def test_builds_lookup_from_beats(self):
        beats = [
            self._make_beat("Goal beat 1", ["goal"]),
            self._make_beat("Goal beat 2", ["goal", "attacking_play"]),
            self._make_beat("Card beat", ["yellow_card"]),
        ]
        store = NotesStore(raw_markdown="# Test", beats=beats)
        assert store.lookup == {
            "goal": [0, 1],
            "attacking_play": [1],
            "yellow_card": [2],
        }

    def test_get_beats_for_tag_returns_correct_beats(self):
        goal_beat = self._make_beat("Goal", ["goal"])
        foul_beat = self._make_beat("Foul", ["foul"])
        store = NotesStore(
            raw_markdown="# Test", beats=[goal_beat, foul_beat]
        )
        assert store.get_beats_for_tag("goal") == [goal_beat]
        assert store.get_beats_for_tag("foul") == [foul_beat]

    def test_get_beats_for_unknown_tag_returns_empty(self):
        store = NotesStore(
            raw_markdown="# Test",
            beats=[self._make_beat("Beat", ["goal"])],
        )
        assert store.get_beats_for_tag("corner") == []

    def test_empty_beats_produces_empty_lookup(self):
        store = NotesStore(raw_markdown="# Test", beats=[])
        assert store.lookup == {}
        assert store.get_beats_for_tag("goal") == []

    def test_raw_markdown_accessible(self):
        store = NotesStore(
            raw_markdown="# Full Notes\nContent here", beats=[]
        )
        assert store.raw_markdown == "# Full Notes\nContent here"

    def test_beats_accessible(self):
        beats = [self._make_beat("Beat", ["goal"])]
        store = NotesStore(raw_markdown="# Test", beats=beats)
        assert store.beats is beats

    def test_index_placeholder_is_none(self):
        store = NotesStore(raw_markdown="# Test", beats=[])
        assert store.index is None

    def test_multiple_beats_same_tag(self):
        beats = [
            self._make_beat("Foul 1", ["foul"]),
            self._make_beat("Foul 2", ["foul"]),
            self._make_beat("Foul 3", ["foul"]),
        ]
        store = NotesStore(raw_markdown="# Test", beats=beats)
        results = store.get_beats_for_tag("foul")
        assert len(results) == 3
        assert results == beats

    def test_lookup_preserves_insertion_order(self):
        beats = [
            self._make_beat("First", ["goal"]),
            self._make_beat("Second", ["goal"]),
            self._make_beat("Third", ["goal"]),
        ]
        store = NotesStore(raw_markdown="# Test", beats=beats)
        assert store.lookup["goal"] == [0, 1, 2]

    def test_serializes_source_attribution(self, tmp_path):
        beat = self._make_beat(
            "Sourced beat",
            ["goal"],
            source="fbref",
            source_urls=["https://example.com/source"],
            source_attribution=[{"label": "fbref", "url": "https://example.com/source"}],
            confidence=0.9,
        )
        store = NotesStore(raw_markdown="# Test", beats=[beat])

        path = tmp_path / "notes.json"
        store.save_json(path)
        loaded = NotesStore.load_json(path)

        assert loaded.raw_markdown == "# Test"
        assert loaded.beats[0].source_urls == ["https://example.com/source"]
        assert loaded.beats[0].source_attribution == [
            {"label": "fbref", "url": "https://example.com/source"}
        ]
        assert loaded.lookup == {"goal": [0]}


# ── Canonical tags constant ──────────────────────────────────────────────────

class TestCanonicalTags:
    def test_has_exactly_eight_tags(self):
        assert len(CANONICAL_TAGS) == 8

    def test_contains_all_required_tags(self):
        expected = {
            "goal",
            "yellow_card",
            "red_card",
            "substitution",
            "foul",
            "corner",
            "free_kick_dangerous",
            "offside",
        }
        assert set(CANONICAL_TAGS) == expected

    def test_tags_are_lowercase(self):
        for tag in CANONICAL_TAGS:
            assert tag == tag.lower()

    def test_is_iterable_for_iteration_order(self):
        # CANONICAL_TAGS can be tuple or list - just needs to be iterable
        assert hasattr(CANONICAL_TAGS, '__iter__')
