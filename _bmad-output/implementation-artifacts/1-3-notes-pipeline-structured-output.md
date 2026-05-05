# Story 1.3: Notes Pipeline with Structured Output

Status: done

## Story

As a commentator preparing for a match,
I want to enter a fixture and run the 7-agent pipeline that generates structured notes with live progress visible,
So that I have 5 pages of research-quality Peter Drury-style material organized by event type before the match begins.

## Acceptance Criteria

**Given** a fixture is submitted (home_team, away_team, venue, sport)
**When** the 7-agent pipeline executes in 3 phases (Phase 1: PlayerResearch, TeamForm, Historical, Weather, News in parallel; Phase 2: Matchup; Phase 3: NoteOrganizer)
**Then** each agent fetches data via the 3-layer stats chain (StatsBomb → Firecrawl → FBref)
**And** if an agent fails, remaining agents continue and the failed source is indicated in output.

**Given** an agent completes or fails
**When** status changes
**Then** a progress callback is broadcast over WebSocket: `{"type": "progress", "agent": "PlayerResearch", "status": "running|complete|failed", "items": "22/25"}`
**And** all 7 agents report their final status before pipeline completion.

**Given** the NoteOrganizer agent receives all agent outputs
**When** it synthesizes the final notes
**Then** it returns a `NotesStore` instance (not raw string)
**And** `notes_store.raw_markdown` contains the full 5-page Markdown document
**And** `notes_store.beats` contains at least 50 NarrativeBeats tagged with event types
**And** `notes_store.lookup` provides O(1) tag→beat_indices mapping
**And** existing code that accessed the old string output continues to work via `.raw_markdown`.

**Given** notes generation completes
**When** the pipeline finishes
**Then** a `notes_ready` WebSocket message is broadcast: `{"type": "notes_ready", "beat_count": N, "sections": ["match_info", "home_team", "away_team", "tactical", "historical"], "timestamp": "ISO8601"}`
**And** the NotesStore persists in-memory for the duration of the WebSocket session (FR-5).

## Tasks / Subtasks

- [ ] Task 1: Review existing agent pipeline
  - [ ] 1.1 Identify current NoteOrganizer output type
  - [ ] 1.2 Document all callers of NoteOrganizer.execute()
  - [ ] 1.3 Check LiveAgent for dependencies on string output

- [ ] Task 2: Modify NoteOrganizer to return NotesStore
  - [ ] 2.1 Import NarrativeBeat, NotesStore from models
  - [ ] 2.2 Change return type from str to NotesStore
  - [ ] 2.3 Parse existing markdown output into NarrativeBeat list
  - [ ] 2.4 Build lookup dict from beats
  - [ ] 2.5 Ensure raw_markdown attribute for backwards compat

- [ ] Task 3: Update agents that consume NoteOrganizer output
  - [ ] 3.1 Update LiveAgent.generate_live_commentary() to use NotesStore.lookup()
  - [ ] 3.2 Update api/server.py commentary generation to access .raw_markdown where needed
  - [ ] 3.3 Add NotesStore to WebSocket notes_ready broadcast

- [ ] Task 4: Wire NotesStore into LiveAgent commentary prompt
  - [ ] 4.1 Modify generate_live_commentary() to accept NotesStore
  - [ ] 4.2 Use NotesStore.get_beats_for_tag() for O(1) retrieval
  - [ ] 4.3 Fallback to raw_markdown if lookup misses

- [ ] Task 5: Progress callback integration
  - [ ] 5.1 Ensure each agent emits progress via WebSocket
  - [ ] 5.2 Track agent completion status
  - [ ] 5.3 Broadcast notes_ready when NoteOrganizer completes

- [ ] Task 6: Testing
  - [ ] 6.1 Unit test: NoteOrganizer returns NotesStore with correct beats
  - [ ] 6.2 Integration test: Full pipeline emits progress callbacks
  - [ ] 6.3 Integration test: notes_ready broadcast contains beat_count

## Dev Notes

### What We're Building

This story modifies the **existing 7-agent commentary notes pipeline** to return structured output (`NotesStore`) instead of raw markdown strings.

**Key change:** `NoteOrganizer.execute()` currently returns `str`. After this story, it returns `NotesStore` with:
- `raw_markdown: str` — full document for teleprompter display (backwards compat)
- `beats: List[NarrativeBeat]` — structured beats for O(1) lookup
- `lookup: Dict[str, List[int]]` — event_tag → beat_indices mapping

**Why this matters:** Story 1.4 (Vision-Triggered Commentary) needs O(1) lookup to match vision detections to pre-computed notes in < 500ms TTFT.

### Architecture Compliance

**Patterns to follow:**
- Backwards compatibility: `NotesStore.raw_markdown` ensures existing string-based code continues working
- Fallback chain: Story 1.4 will use lookup (deterministic) → cosine similarity (semantic) → full markdown (full context)
- Progress callbacks: Match existing pattern in `orchestration/engine.py` for workflow progress

**Integration order (from Architecture):**
1. **This story** — Modify NoteOrganizer to return NotesStore
2. Story 1.4 — Wire `NotesStore.lookup()` into LiveAgent commentary prompt
3. Story 1.4+ — numpy cosine similarity fallback (only if Day 5 has slack)

### Existing Code to Be Aware Of

`agents/note_organizer.py` — Current NoteOrganizer agent. Find and modify its `execute()` method.

`agents/live_agent.py` — LiveAgent.generate_live_commentary() may need updating to use NotesStore.

`api/server.py` — Commentary generation in `live_audio_ws` and `streaming_video_ws` handlers.

`orchestration/engine.py` — Workflow orchestration with progress callbacks.

### Environment Variables

```bash
# No new env vars for this story
# Existing agent config in config/defaults.py applies
```

### Testing Requirements

- Unit test: NoteOrganizer.execute() returns NotesStore with raw_markdown, beats, lookup
- Unit test: NotesStore.lookup contains all 8 canonical tags that have beats
- Unit test: NotesStore.get_beats_for_tag(tag) returns correct beats
- Integration test: Pipeline progress callbacks fire for all 7 agents
- Integration test: notes_ready WebSocket message includes beat_count and sections

Test file: `tests/agents/test_note_organizer.py`, `tests/agents/test_live_agent.py`

### Files Being Modified

| File | Action | Purpose |
|------|--------|---------|
| `agents/note_organizer.py` | **MODIFY** | Return NotesStore instead of str |
| `agents/live_agent.py` | **MODIFY** | Accept NotesStore, use lookup for O(1) retrieval |
| `api/server.py` | **MODIFY** | Broadcast notes_ready with beat_count |
| `tests/agents/test_note_organizer.py` | **NEW** | Unit tests for structured output |

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 1.3](#story-13-notes-pipeline-with-structured-output)
- [Source: _bmad-output/planning-artifacts/architecture.md — Structured Notes Store](#structured-notes-store-architecture)
- [Source: _bmad-output/planning-artifacts/architecture.md — Retrieval Chain](#retrieval-chain)
- [Source: models/notes_store.py — NotesStore class]
- [Source: models/narrative_beat.py — NarrativeBeat dataclass]
- [Source: agents/ — existing 7-agent pipeline]

## Dev Agent Record

### Agent Model Used

Claude Code (implementation)

### Debug Log References

- `CommentaryNoteOrganizerAgent.execute()` now returns `NotesStore` instead of `Tuple[str, Dict]`
- New method `synthesize_to_notes_store()` parses markdown into `List[NarrativeBeat]` with event tags
- Legacy `synthesize_to_markdown_json()` preserved for backwards compatibility
- `NotesStore` provides O(1) lookup via `get_beats_for_tag(tag)`
- Workflow state updated to store `notes_store` attribute

### Completion Notes List

**Changes made:**
1. `agents/specialized_commentary/note_organizer_agent.py`:
   - Added import for `NotesStore`, `NarrativeBeat`
   - Changed `execute()` return type to `NotesStore`
   - Added `synthesize_to_notes_store()` method
   - Added `_extract_beats_from_markdown()` to parse markdown into structured beats
   - Preserved legacy `synthesize_to_markdown_json()` for backwards compat

2. `agents/coordinator.py`:
   - Fixed import: `NoteOrganizerAgent` → `CommentaryNoteOrganizerAgent`
   - Updated agent instantiation

3. `workflows/commentary_notes_workflow.py`:
   - Added `notes_store: Optional[Any] = None` field to `CommentaryNotesState`
   - Updated `synthesize_notes()` to call `synthesize_to_notes_store()`
   - Stores both `notes_store` and `markdown_notes` (backwards compat)

**Beat extraction logic:**
- Player profiles → tagged with `substitution`, `goal` events
- Key matchups → tagged with `foul`, `free_kick_dangerous`
- Form patterns → tagged with `corner`, `offside`
- Historical context → tagged with `goal`, `yellow_card`, `red_card`
- Weather impact → tagged with `foul`, `corner`

### File List

**Modified:**
- `agents/specialized_commentary/note_organizer_agent.py` — Return NotesStore
- `agents/coordinator.py` — Fixed import
- `workflows/commentary_notes_workflow.py` — Store NotesStore in state

