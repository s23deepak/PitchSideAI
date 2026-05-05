# Story 1.1: Narrative Data Models & Tag System

Status: done

## Story

As a system architect,
I want structured data models for narrative beats with an 8-tag event taxonomy and O(1) lookup,
so that pre-match commentary notes can be efficiently retrieved by event type during live match play.

## Acceptance Criteria

1. **NarrativeBeat dataclass** — `models/narrative_beat.py` defines `NarrativeBeat` with fields: `text` (str), `event_tags` (List[str]), `players` (List[str]), `section` (str), `source` (str), `confidence` (float, 0.0-1.0). All fields have type hints. `players` defaults to empty list. `confidence` defaults to 0.0.

2. **NotesStore with O(1) lookup** — `models/notes_store.py` defines `NotesStore` that accepts `List[NarrativeBeat]` + `raw_markdown: str` on init and builds `lookup: Dict[str, List[int]]` mapping event_tag → beat_indices. `raw_markdown` and `beats` are accessible as attributes (backwards compat via `.raw_markdown`).

3. **TagResolver with 3-tier resolution** — `TagResolver` class in `models/notes_store.py` resolves vision labels to 8 canonical tags via: exact match → synonym map → substring match → None. Synonym map covers vision-specific labels (e.g., "Goal scored" → "goal", "Booking" → "yellow_card").

4. **Goal safety gate** — `TagResolver.resolve()` accepts an optional `game_state` parameter. When resolving to "goal", the resolver verifies `game_state` score has changed before returning "goal". If score unchanged, the tag is rejected (returns None) — preventing false goal calls.

5. **Canonical tags are public constants** — The 8 canonical tags (`goal`, `yellow_card`, `red_card`, `substitution`, `foul`, `corner`, `free_kick_dangerous`, `offside`) are defined as module-level constants (e.g., a `CANONICAL_TAGS` frozenset or list) in `models/notes_store.py`.

6. **Package exports updated** — `models/__init__.py` exports `NarrativeBeat`, `NotesStore`, and `TagResolver` alongside existing exports (`GameState`, `GameEvent`, `MatchPhase`).

## Tasks / Subtasks

- [x] Task 1: Create NarrativeBeat dataclass (AC: 1)
  - [x] 1.1 Create `models/narrative_beat.py` with `NarrativeBeat` dataclass
  - [x] 1.2 All fields type-hinted; `players: List[str] = field(default_factory=list)`, `confidence: float = 0.0`
  - [x] 1.3 No methods — pure data class only

- [x] Task 2: Create NotesStore with TagResolver (AC: 2, 3, 4, 5)
  - [x] 2.1 Create `models/notes_store.py`
  - [x] 2.2 Define 8 canonical tag constants at module level
  - [x] 2.3 Define synonym map (vision label → canonical tag) covering at least: "Goal scored"→goal, "Booking"→yellow_card, "Sent off"→red_card, "Substitution"→substitution, "Foul committed"→foul, "Corner kick"→corner, "Free kick"→free_kick_dangerous, "Offside call"→offside
  - [x] 2.4 Implement `TagResolver` class with `resolve(vision_label: str, previous_score_total=None, current_score_total=None) -> Optional[str]`
  - [x] 2.5 Implement 3-tier resolution: exact match → synonym (casefold) → token-subset substring → None
  - [x] 2.6 Implement goal safety gate: if resolved tag is "goal" and score context provided, verify `current_score_total > previous_score_total`; reject if score unchanged
  - [x] 2.7 Implement `NotesStore` class: init takes `beats: List[NarrativeBeat]` + `raw_markdown: str`, builds `self.lookup: Dict[str, List[int]]` by scanning `beat.event_tags`
  - [x] 2.8 `NotesStore.get_beats_for_tag(tag: str) -> List[NarrativeBeat]` — O(1) lookup returning the actual beat objects
  - [x] 2.9 `NotesStore.index: Optional[Any]` attribute initialized to None (placeholder for numpy cosine similarity)

- [x] Task 3: Update package exports (AC: 6)
  - [x] 3.1 Update `models/__init__.py` to import and export NarrativeBeat, NotesStore, TagResolver, CANONICAL_TAGS
  - [x] 3.2 Preserve existing exports (GameState, GameEvent, MatchPhase)

### Review Findings

#### Code Review (2026-05-04)

- [ ] [Review][Decision] CANONICAL_TAGS is a mutable list — Should it be a `tuple` or `frozenset` for immutability? Currently callers can `CANONICAL_TAGS.append()`. [models/notes_store.py:16]
- [ ] [Review][Decision] NarrativeBeat.confidence has no range validation — Values outside 0.0-1.0 are accepted silently. The spec says "0.0-1.0" but dataclasses don't validate in `__init__`. Should we add a `__post_init__` range check? [models/narrative_beat.py:14]
- [ ] [Review][Decision] "goal_kick" token-subset matches "goal" — `_word_boundary_match("goal", "goal_kick")` splits to `{"goal","kick"}` ⊇ `{"goal"}`. The goal safety gate catches false positives (score won't change), but should we add "goal_kick" to the synonym map as `None` (explicit exclusion) or leave as-is? [models/notes_store.py:52-61]
- [ ] [Review][Patch] Missing trailing newlines — `narrative_beat.py`, `notes_store.py`, and `test_notes_store.py` all lack a final `\n` at EOF. [models/narrative_beat.py:14, models/notes_store.py:167, tests/models/test_notes_store.py:320]
- [ ] [Review][Patch] Blank line in resolve() parameter list — Unnecessary blank line between `self,` and `vision_label: str` in method signature. [models/notes_store.py:77-78]
- [ ] [Review][Patch] No test for `__post_init__` deserialization guard — The `if self.lookup: return` early-exit for pre-built lookup dicts is untested. [models/notes_store.py:157-158]

#### Code Review (2026-05-05) — Blind Hunter + Acceptance Auditor

- [x] [Review][Patch] `CANONICAL_TAGS` is mutable `List[str]` — changed to `tuple` for immutability [models/notes_store.py:16-25] **FIXED**
- [x] [Review][Patch] `NarrativeBeat.confidence` lacks 0.0-1.0 range validation — added `__post_init__` check [models/narrative_beat.py:14] **FIXED**
- [x] [Review][Patch] Missing trailing newline in `narrative_beat.py` [models/narrative_beat.py:14] **FIXED**
- [x] [Review][Patch] Docstring not properly closed on `NarrativeBeat` — added proper module docstring [models/narrative_beat.py:1-6] **FIXED**
- [x] [Review][Patch] `_SYNONYM_MAP` is mutable — changed to immutable `Mapping[str, str]` [models/notes_store.py:29-47] **FIXED**
- [x] [Review][Patch] `get_beats_for_tag` assumes indices valid — added bounds checking for stale indices [models/notes_store.py:164-172] **FIXED**
- [x] [Review][Defer] Goal safety gate silently suppresses goal tags without logging — enhancement, not bug [models/notes_store.py:142-147]
- [x] [Review][Defer] `NotesStore.__post_init__` skips lookup rebuild when pre-populated — already in spec review findings [models/notes_store.py:170-171]
- [x] [Review][Defer] `index: Optional[Any]` too vague — placeholder per spec, loses type safety [models/notes_store.py:166]
- [x] [Review][Defer] Casefold without Unicode normalization — edge case, not critical [models/notes_store.py:106,111,118]
- [x] [Review][Dismiss] Comment on same line as dataclass field — style preference only [models/notes_store.py:166]
- [x] [Review][Dismiss] `_word_boundary_match` could produce empty tokens — set dedupes, not a real issue [models/notes_store.py:72-73]
- [x] [Review][Dismiss] Goal safety gate uses score params instead of `game_state` — explicitly endorsed in spec Dev Notes [models/notes_store.py:76-82]
- [x] [Review][Dismiss] `get_beats_for_tag()` returns beats not indices — improved UX, internal lookup still uses indices [models/notes_store.py:164-167]

## Dev Notes

### What We're Building

This story creates the **data foundation** for the entire commentary system. Every subsequent story (notes pipeline in 1.3, vision-triggered commentary in 1.4, trivia cards in 1.6, teleprompter in 3.1-3.2) depends on these models. Get the data contracts right here and everything downstream composes cleanly.

**The two new files are:**
- `models/narrative_beat.py` — pure dataclass, zero logic (like `game_state.py`'s `GameEvent`)
- `models/notes_store.py` — `NotesStore` (data + lookup logic) + `TagResolver` (tag normalization logic)

**Integration order from Architecture:**
1. **This story** — Add NarrativeBeat + NotesStore in `models/`
2. Story 1.3 — Modify NoteOrganizer to return NotesStore (backwards compat via `raw_markdown`)
3. Story 1.4 — Wire `NotesStore.lookup()` into LiveAgent commentary prompt
4. Story 1.4+ — numpy cosine similarity fallback (only if Day 5 has slack)

### Architecture Compliance

**Structural conventions:**
- `models/` is for data structures — flat package, 3 files after this story
- `narrative_beat.py` is a pure dataclass (no logic), exactly like `game_state.py`'s `GameEvent`
- `notes_store.py` adds retrieval logic on top of the data — follows the `game_state.py` pattern (data + methods in same file)
- `TagResolver` lives in `notes_store.py`, not a separate file — it operates on the tag vocabulary that NotesStore uses, not an independent concern

**Patterns to follow:**
- Dataclass pattern: match `GameEvent` in `models/game_state.py:57-64` — use `@dataclass` with `field(default_factory=...)` for mutable defaults
- Module structure: match `models/game_state.py` — constants at top, then classes, then public API
- Export pattern: match `models/__init__.py:3` — explicit imports, explicit `__all__`

**Naming conventions (from Architecture):**
- Python files: `snake_case` — confirmed: `narrative_beat.py`, `notes_store.py`
- Python classes: `PascalCase` — confirmed: `NarrativeBeat`, `NotesStore`, `TagResolver`
- Python functions/methods: `snake_case` — `resolve()`, `get_beats_for_tag()`
- Module-level constants: `UPPER_SNAKE_CASE` — `CANONICAL_TAGS`

### Tag Taxonomy: The 8 Canonical Tags

```
goal, yellow_card, red_card, substitution, foul, corner, free_kick_dangerous, offside
```

These align with the existing `GameEvent.event_type` values already used in `game_state.py` (`goal`, `yellow_card`, `red_card`, `substitution`). The new ones (`foul`, `corner`, `free_kick_dangerous`, `offside`) extend the vocabulary for vision-detected events beyond what manual text parsing handles.

**Why these 8:** They cover every match event that triggers a trivia card or teleprompter highlight. Each maps to a distinct NarrativeBeat section.

### Safety Gate Design

The goal safety gate is critical because a false goal call is the highest-trust-cost failure mode. The architecture specifies: "Before any 'goal' tag fires, verify `game_state` score has changed."

**Implementation approach:** `TagResolver.resolve()` accepts an optional `game_state` parameter. When the resolved tag is "goal" and `game_state` is provided, the resolver checks whether the current score (home + away) exceeds a previously stored total. The simplest approach: `TagResolver` stores `_last_known_score_total: Optional[int]` and exposes `update_score(game_state)` for the caller to call after a legitimate goal. If score hasn't changed since last update, `resolve()` returns None for "goal".

Alternatively, simpler approach: pass `previous_total: Optional[int]` as a parameter to `resolve()`, and the caller (LiveAgent in story 1.4) manages the state. This keeps TagResolver stateless. Use this approach — stateless resolvers are easier to test.

### Synonym Map

Vision models use varied language. The synonym map bridges vision vocabulary to canonical tags:

```python
SYNONYM_MAP: Dict[str, str] = {
    "goal scored": "goal",
    "goal": "goal",
    "booking": "yellow_card",
    "yellow card": "yellow_card",
    "sent off": "red_card",
    "red card": "red_card",
    "dismissal": "red_card",
    "substitution": "substitution",
    "sub": "substitution",
    "foul committed": "foul",
    "foul": "foul",
    "corner kick": "corner",
    "corner": "corner",
    "free kick": "free_kick_dangerous",
    "set piece": "free_kick_dangerous",
    "offside call": "offside",
    "offside": "offside",
}
```

Casefold both keys and lookup values for matching.

### Retrieval Chain Pattern (Context for Stories 1.3-1.4)

The `NotesStore.lookup` is layer 1 of a 3-layer retrieval chain (reuses `FallbackStatsRetriever._chain()` pattern):

1. **Deterministic tag match** — `NotesStore.get_beats_for_tag(tag)` — O(1) dict lookup, covers ~80% of events. **This story implements this layer.**
2. Semantic/embedding match — numpy cosine similarity over ~100 beats, CPU-only, < 1ms. Story 1.4+ stretch.
3. Full context fallback — inject entire raw_markdown into LLM prompt. Story 1.4.

### Files Being Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `models/narrative_beat.py` | **NEW** | NarrativeBeat dataclass |
| `models/notes_store.py` | **NEW** | NotesStore + TagResolver + constants |
| `models/__init__.py` | **MODIFY** | Export new classes |

**No existing files are modified** beyond `__init__.py`. This story is purely additive.

### Existing Code to Be Aware Of

`models/game_state.py` (lines 57-64): `GameEvent` dataclass — use the same `@dataclass` + `field(default_factory=...)` pattern:
```python
@dataclass
class GameEvent:
    minute: Optional[int]
    event_type: str  # "goal", "yellow_card", "red_card", "substitution", "phase", "other"
    description: str
    team: Optional[str] = None
    player: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

`models/__init__.py` (lines 1-5): Current exports — preserve these and add new ones:
```python
from models.game_state import GameState, GameEvent, MatchPhase
__all__ = ["GameState", "GameEvent", "MatchPhase"]
```

`models/game_state.py` (lines 36-43): `MatchPhase` enum — reference for enum pattern.

### Testing Requirements

- Unit test: `TagResolver.resolve()` with exact match, synonym match, substring match, no match
- Unit test: Goal safety gate — score unchanged → returns None; score changed → returns "goal"
- Unit test: `NotesStore` initialization builds correct lookup dict
- Unit test: `NotesStore.get_beats_for_tag()` returns correct beats for each canonical tag
- Unit test: Empty beats list → lookup is empty dict, `get_beats_for_tag()` returns empty list
- Unit test: `NarrativeBeat` instantiation with defaults and with all fields

Test file: `tests/models/test_notes_store.py` or `tests/test_tag_resolver.py` (follow existing test conventions).

### Confidence-Gated Progression (Shared Pattern)

This story establishes the `confidence` field on NarrativeBeat. The 3-tier confidence gate (from Architecture) applies across 5 components but **originates here as a data field**:

```python
# > 0.9 → proceed (skip confirmation)
# >= 0.7 → confirm (brief verification, 1.5s max)
# < 0.7 → reject (auto-reject, prompt retry)
```

The `NarrativeBeat.confidence` field enables this gating in later stories. No gate logic in this story — just the data contract.

### Project Structure Notes

After this story, `models/` will contain:
```
models/
├── __init__.py          # Exports: GameState, GameEvent, MatchPhase, NarrativeBeat, NotesStore, TagResolver
├── game_state.py        # Existing: GameState, GameEvent, MatchPhase
├── narrative_beat.py    # NEW: NarrativeBeat dataclass
└── notes_store.py       # NEW: NotesStore + TagResolver + CANONICAL_TAGS
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 1.1](#story-11-narrative-data-models--tag-system)
- [Source: _bmad-output/planning-artifacts/architecture.md — Data Architecture](#data-architecture)
- [Source: _bmad-output/planning-artifacts/architecture.md — Event Tags Taxonomy Contract](#event-tags-taxonomy-contract)
- [Source: _bmad-output/planning-artifacts/architecture.md — Integration Order (step 1)](#integration-order-from-amelias-review)
- [Source: _bmad-output/planning-artifacts/architecture.md — Implementation Patterns](#implementation-patterns--consistency-rules)
- [Source: _bmad-output/planning-artifacts/architecture.md — First Implementation Priority (Day 1-2, items 1-2)](#first-implementation-priority-day-1-2)
- [Source: models/game_state.py — GameEvent dataclass pattern to follow]
- [Source: models/__init__.py — current exports to preserve]

## Dev Agent Record

### Agent Model Used

Claude Code (DeepSeek-V4-Pro)

### Debug Log References

- Substring matching evolved from plain `in` check → word-boundary → token-subset during test-driven development. Token-subset approach (`tag_tokens.issubset(text_tokens)`) handles compound tags like "red_card" matching "red_card_situation" while avoiding arbitrary substring false positives.
- Goal safety gate uses stateless approach (`previous_score_total`, `current_score_total` params) rather than instance state — simpler to test, caller manages state.

### Completion Notes List

- Created `models/narrative_beat.py` — pure dataclass with 6 fields, following GameEvent pattern from `game_state.py`
- Created `models/notes_store.py` — NotesStore (O(1) lookup, backwards-compat `raw_markdown`), TagResolver (3-tier: exact→synonym→token-subset→None, goal safety gate), CANONICAL_TAGS constant
- Updated `models/__init__.py` — added NarrativeBeat, NotesStore, TagResolver, CANONICAL_TAGS to exports; preserved all existing exports
- Created `tests/models/test_notes_store.py` — 47 tests across 4 test classes covering NarrativeBeat, TagResolver (exact/synonym/substring/no-match/goal-gate), NotesStore (lookup/empty/multi-beat/order), and CANONICAL_TAGS constant
- Ruff linting clean on all 3 files

### File List

- `models/narrative_beat.py` (NEW)
- `models/notes_store.py` (NEW)
- `models/__init__.py` (MODIFIED)
- `tests/models/test_notes_store.py` (NEW)