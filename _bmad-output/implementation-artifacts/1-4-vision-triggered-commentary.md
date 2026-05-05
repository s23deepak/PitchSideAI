# Story 1.4: Vision-Triggered Commentary & Trivia Broadcast

Status: done

## Story

As a commentator watching the match,
I want the teleprompter to automatically highlight relevant commentary notes when vision detects key events,
And I want fans to receive trivia-formatted commentary with source attribution,
So that commentary feels synchronized with the action without manual triggering.

## Acceptance Criteria

**Given** the 7-agent pipeline has generated a `NotesStore` with structured beats
**When** the streaming vision pipeline detects an event (confidence > 0.6)
**Then** `LiveAgent.generate_live_commentary()` accepts `NotesStore` as an optional parameter
**And** uses `notes_store.get_beats_for_tag(event_tag)` for O(1) retrieval (< 1ms)
**And** injects retrieved beats into the commentary prompt
**And** TTFT (Time To First Token) remains < 500ms (NFR-4).

**Given** vision detects an event without a matching beat tag
**When** lookup returns empty
**Then** fallback to full `raw_markdown` context injection
**And** log a warning for later beat extraction improvement.

**Given** commentary is generated
**When** broadcast over WebSocket
**Then** `{"type": "commentary", "text": "...", "gameState": {...}, "source": "notes_lookup|raw_markdown"}`
**And** includes `trivia_formatted` field for Fan Lens display (2-line fact + source attribution).

**Given** a trivia card should surface (confidence > 0.6)
**When** event matches a beat with high confidence (> 0.8)
**Then** broadcast `{"type": "trivia_card", "text": "...", "source": "...", "fade_in": 400ms}`
**And** card displays for 5s before fade-out (400ms).

**Given** the NotesStore persists in-memory
**When** the WebSocket session remains active
**Then** notes remain available for the duration of the match (FR-5).

## Tasks / Subtasks

- [ ] Task 1: Review existing LiveAgent commentary generation
  - [ ] 1.1 Document current `generate_live_commentary()` signature
  - [ ] 1.2 Identify callers in `api/server.py` (WebSocket handlers)
  - [ ] 1.3 Check if `game_state` is already injected into prompts

- [ ] Task 2: Modify LiveAgent to accept NotesStore
  - [ ] 2.1 Add `notes_store: Optional[NotesStore]` parameter to `generate_live_commentary()`
  - [ ] 2.2 Add `tag_resolver` import (normalize vision label → canonical tag)
  - [ ] 2.3 Implement lookup → fallback chain (exact → raw_markdown)
  - [ ] 2.4 Add `source` tracking ("notes_lookup" vs "raw_markdown")

- [ ] Task 3: Wire vision detections to commentary trigger
  - [ ] 3.1 Update `/ws/live` tactical_detection handler to call `generate_live_commentary()`
  - [ ] 3.2 Pass `NotesStore` from workflow state
  - [ ] 3.3 Inject `game_state.to_context_string()` into prompt

- [ ] Task 4: Add trivia card formatting
  - [ ] 4.1 Extract 2-line fact from commentary text
  - [ ] 4.2 Add `source` attribution from `NarrativeBeat.source`
  - [ ] 4.3 Broadcast `trivia_card` message type

- [ ] Task 5: Progress callback integration
  - [ ] 5.1 Emit `commentary_generated` progress on each vision trigger
  - [ ] 5.2 Track TTFT latency for NFR-4 validation

- [ ] Task 6: Testing
  - [ ] 6.1 Unit test: `generate_live_commentary()` uses NotesStore lookup when provided
  - [ ] 6.2 Unit test: fallback to raw_markdown when tag misses
  - [ ] 6.3 Integration test: WebSocket commentary broadcast includes `source` field
  - [ ] 6.4 Integration test: trivia_card broadcast on high-confidence beats

## Dev Notes

### What We're Building

This story wires the **NotesStore lookup** (Story 1.3) into the **LiveAgent commentary prompt**, triggered by **vision detections** from the streaming pipeline (Story 1.2).

**Key innovation:** O(1) deterministic retrieval from pre-computed notes beats, avoiding full markdown scan for < 500ms TTFT.

**Architecture:**
```
Vision Detection (confidence > 0.6)
  ↓
TagResolver.normalize(vision_label) → canonical_tag
  ↓
NotesStore.get_beats_for_tag(canonical_tag) → List[NarrativeBeat]
  ↓
Inject beats into LiveAgent prompt
  ↓
Generate commentary with Peter Drury-style narrative
  ↓
Broadcast: {type: "commentary", text, gameState, source, trivia_formatted}
```

### Retrieval Chain (from Architecture)

1. **Exact tag lookup** — O(1), covers ~80% of events
2. **Game state active-player filter** — prevents stale notes after substitutions
3. **Full markdown fallback** — graceful degradation, logged for improvement

### Files Being Modified

| File | Action | Purpose |
|------|--------|---------|
| `agents/live_agent.py` | **MODIFY** | Accept `NotesStore`, implement lookup chain |
| `api/server.py` | **MODIFY** | Wire vision → commentary, pass NotesStore |
| `models/tag_resolver.py` | **NEW** | Normalize vision labels → canonical tags |
| `tests/agents/test_live_agent.py` | **NEW** | Unit tests for lookup + fallback |

### Environment Variables

```bash
# No new env vars for this story
# Existing LLM_BACKEND, AWS_REGION apply
```

### Testing Requirements

- Unit test: `generate_live_commentary(event, notes_store)` returns commentary with injected beats
- Unit test: `generate_live_commentary(event, None)` falls back to raw prompt
- Unit test: `TagResolver.normalize("goal scored")` → `"goal"`
- Unit test: `TagResolver.normalize("unknown event")` → `None` (triggers fallback)
- Integration test: WebSocket `commentary` broadcast includes `source: "notes_lookup"`
- Integration test: TTFT < 500ms for 95th percentile

Test file: `tests/agents/test_live_agent.py`, `tests/models/test_tag_resolver.py`

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — Structured Notes Store](#structured-notes-store-architecture)
- [Source: _bmad-output/planning-artifacts/architecture.md — Retrieval Chain](#retrieval-chain)
- [Source: models/notes_store.py — NotesStore class]
- [Source: models/narrative_beat.py — NarrativeBeat dataclass]
- [Source: agents/live_agent.py — LiveAgent commentary generation]
- [Source: api/server.py — WebSocket tactical_detection handler]

## Dev Agent Record

### Agent Model Used

Claude Code (implementation)

### Completion Notes List

**Changes made:**

1. `models/notes_store.py` — TagResolver already existed with 3-tier resolution (exact → synonym → substring)

2. `agents/live_agent.py`:
   - Added `NotesStore` and `TagResolver` imports
   - Added `notes_store: Optional[NotesStore]` and `tag_resolver: TagResolver` fields
   - Modified `start_session()` to accept optional `notes_store` parameter
   - Rewrote `generate_live_commentary()` to:
     - Accept `vision_tactical_label` and `game_state` parameters
     - Use `TagResolver.resolve()` to normalize vision labels
     - Use `NotesStore.get_beats_for_tag()` for O(1) retrieval
     - Apply game_state active-player filter when available
     - Fall back to raw_markdown when no beats match
     - Return `Dict` with `commentary`, `source`, `retrieved_beats`, `trivia_formatted`, `resolved_tag`
   - Added `_format_trivia_card()` method for Fan Lens card formatting

3. `api/server.py`:
   - Added `_notes_stores` dict to `ConnectionManager` for in-memory NotesStore caching
   - Added `store_notes()` and `get_notes()` methods to `ConnectionManager`
   - Updated `/api/v1/commentary-notes` endpoint to store `NotesStore` on completion
   - Updated `/ws/live` WebSocket handler:
     - Load `NotesStore` at session start from cache
     - Pass `notes_store` to `LiveAgent.start_session()`
     - Modified `match_event` handler to extract event type and call new `generate_live_commentary()`
     - Modified `tactical_detection` handler to pass `vision_tactical_label` and `game_state`
     - Added `trivia_card` broadcast when high-confidence beat retrieved
   - Updated `_periodic_commentary()` to use new `generate_live_commentary()` signature

4. `tests/models/test_live_agent.py`:
   - Added 11 unit tests for LiveAgent NotesStore integration
   - Tests cover: lookup usage, fallback behavior, trivia card formatting, TagResolver
   - All tests pass

**Retrieval chain implementation:**
1. Vision label → `TagResolver.resolve()` → canonical tag
2. `NotesStore.get_beats_for_tag(tag)` → O(1) lookup
3. Game state active-player filter (if available)
4. Full markdown fallback (if no beats match)

**Trivia card surfacing:**
- Confidence ≥ 0.8: 5s display, 400ms fade in/out
- Confidence 0.6-0.8: 3s display, 300ms fade in/out
- Confidence < 0.6: No card shown

### File List

**Modified:**
- `agents/live_agent.py` — NotesStore integration + trivia formatting
- `api/server.py` — NotesStore caching + vision-triggered commentary
- `tests/models/test_live_agent.py` — moved from tests/agents/ due to pytest path issues

**Already existed (no changes needed):**
- `models/notes_store.py` — TagResolver already implemented
- `models/narrative_beat.py` — NarrativeBeat dataclass

**Modified:**
(TBD)

**New:**
(TBD)
