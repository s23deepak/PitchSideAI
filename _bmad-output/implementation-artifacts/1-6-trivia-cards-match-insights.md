# Story 1.6: Trivia Cards Match Insights Display

Status: done

## Story

As a fan watching the match in Fan Lens mode,
I want to see trivia cards and match insights in a dedicated panel with suggested question chips,
And I want to tap question chips to instantly ask about tactical situations,
So that I can engage with the match through guided discovery without typing questions.

## Acceptance Criteria

**Given** the WebSocket session is active
**When** a `trivia_card` message arrives (confidence > 0.6)
**Then** the MatchInsight component displays the card in a priority queue
**And** shows suggested question chips below the card ("Ask about this", "Related tactics", "Player stats")
**And** the card displays with source attribution and confidence indicator

**Given** a trivia card is displayed
**When** the user taps a question chip
**Then** the question is sent as a `query` message over WebSocket
**And** the card remains visible while the answer is generated
**And** the answer replaces the card content with smooth transition

**Given** multiple trivia cards arrive in quick succession
**When** cards are queued (max 5)
**Then** they display in priority order (confidence desc, then recency)
**And** older cards auto-dismiss after 15s unless user interacts

**Given** the user asks a question via chip
**When** the answer arrives
**Then** it displays in the same card slot with "Answer" badge
**And** a "Back to trivia" button returns to the card queue

**Given** no trivia cards are available
**When** the MatchInsight panel is empty
**Then** it shows a placeholder ("Match insights will appear here as the action unfolds")
**And** displays 3 static suggested questions to prime discovery

**Given** the match has commentary notes pre-generated
**When** the panel mounts
**Then** it loads initial trivia from `NotesStore.beats` with confidence > 0.7
**And** displays 1-2 starter cards to demonstrate the feature

## Tasks / Subtasks

- [ ] Task 1: Review existing trivia card implementation
  - [ ] 1.1 Document `VideoCanvas.jsx` trivia card rendering
  - [ ] 1.2 Identify gaps for dedicated MatchInsight panel
  - [ ] 1.3 Check WebSocket `trivia_card` and `query` message handlers in `api/server.py`

- [ ] Task 2: Create MatchInsight component
  - [ ] 2.1 Create `frontend/src/components/MatchInsight.jsx`
  - [ ] 2.2 Implement trivia card queue with priority sorting
  - [ ] 2.3 Add suggested question chips below each card
  - [ ] 2.4 Implement Q&A mode (question → answer transition)
  - [ ] 2.5 Add empty state with placeholder + starter questions

- [ ] Task 3: Wire WebSocket handlers
  - [ ] 3.1 Parse `trivia_card` messages into component state
  - [ ] 3.2 Send `query` messages on chip tap
  - [ ] 3.3 Handle `answer` messages and display in card slot
  - [ ] 3.4 Implement auto-dismiss timer (15s for non-interacted cards)

- [ ] Task 4: Load initial trivia from NotesStore
  - [ ] 4.1 Access pre-generated commentary notes on mount
  - [ ] 4.2 Filter beats with confidence > 0.7
  - [ ] 4.3 Format as starter trivia cards

- [ ] Task 5: Testing
  - [ ] 5.1 Manual test: Trivia cards display with correct timing
  - [ ] 5.2 Manual test: Question chips send queries and display answers
  - [ ] 5.3 Manual test: Priority queue orders by confidence
  - [ ] 5.4 Manual test: Empty state shows helpful placeholder

## Dev Notes

### What We're Building

This story creates the **MatchInsight panel** — a dedicated UI component for trivia cards and guided Q&A discovery. Unlike Story 1.5 which showed trivia cards as overlays on the video player, this story builds a persistent panel where fans can explore insights at their own pace.

**Key components:**
- `MatchInsight.jsx` — Trivia card queue + question chips + Q&A display
- Priority queue — Max 5 cards, sorted by confidence then recency
- Question chips — Pre-generated suggestions ("Ask about this", "Related tactics", "Player stats")
- Empty state — Placeholder + starter questions to prime discovery

**Architecture:**
```
WebSocket /ws/live
  ↓
trivia_card: {text, source, confidence, display_duration_ms}
  ↓
MatchInsight.queue.push(card) → sort by confidence desc
  ↓
Render top card + question chips
  ↓
User taps chip → send query → display answer
```

**Relationship to Story 1.5:**
- Story 1.5: Trivia cards as transient video overlays (3-5s display)
- Story 1.6: Trivia cards in persistent panel with Q&A interaction
- Both consume `trivia_card` WebSocket messages, different presentation

### Question Chip Types

| Chip | Generated Query |
|------|-----------------|
| "Ask about this" | "Tell me more about: {trivia_text}" |
| "Related tactics" | "What tactical patterns led to this?" |
| "Player stats" | "Show me stats for {player_name}" |
| "Historical context" | "Has this happened before this season?" |

### Files Being Modified

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/components/MatchInsight.jsx` | **NEW** | Trivia card panel with Q&A |
| `frontend/src/components/MatchDashboard.jsx` | **MODIFY** | Add MatchInsight panel to layout |
| `api/server.py` | **MODIFY** | Ensure `query` handler returns answers to WebSocket |
| `agents/live_agent.py` | **NO CHANGE** | Already has Q&A via `generate_live_commentary()` |

### Environment Variables

```bash
# Frontend
VITE_BACKEND_URL=ws://localhost:8000
```

### Testing Requirements

- Manual test: Trivia cards queue and display in priority order
- Manual test: Question chips trigger Q&A flow
- Manual test: Empty state shows helpful placeholder
- Manual test: Initial trivia loads from pre-generated notes

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — Frontend Architecture](#frontend-architecture)
- [Source: _bmad-output/planning-artifacts/architecture.md — WebSocket Protocol](#api-communication-patterns)
- [Source: frontend/src/components/VideoCanvas.jsx — Existing trivia card rendering]
- [Source: api/server.py — WebSocket query handler]
- [Source: agents/live_agent.py — Q&A generation]

## Dev Agent Record

### Agent Model Used

Claude Code (implementation)

### Completion Notes List

**Changes made:**

1. `frontend/src/components/MatchInsight.jsx` — **NEW** component created (~520 lines) with:
   - Trivia card queue with priority sorting (confidence desc, then recency)
   - Max 5 cards in queue, auto-dismiss after 15s for non-interacted cards
   - Q&A mode with smooth question → answer transitions
   - 4 suggested question chips per card:
     - "Ask about this" — Expands on current card text
     - "Related tactics" — Tactical pattern analysis
     - "Player stats" — Extracts player name, shows stats
     - "Historical context" — Season comparison
   - Empty state with placeholder + 3 starter questions
   - Initial trivia loading from `initialTrivia` prop (filters confidence > 0.7)
   - WebSocket integration for `trivia_card`, `query`, and `answer` messages
   - Card navigation (prev/next) for multi-card queues
   - Confidence badges (high/medium) and source attribution

2. `frontend/src/components/MatchDashboard.jsx` — **MODIFIED**:
   - Added `MatchInsight` import
   - Added MatchInsight panel to bottom row layout
   - Passed `initialTrivia` from `commentaryData.notes.beats`

**Key implementation details:**

- **Priority queue**: Cards sorted by confidence (desc) then timestamp (desc), max 5 cards
- **Auto-dismiss**: 15s timer for non-starter cards, resets on card change
- **Q&A flow**: Question chip tap → send `query` → show loading state → display `answer` → "Back to trivia" button
- **Starter questions**: Contextualized to match teams ("What's {homeTeam}'s recent form?")
- **Initial trivia**: Loads up to 2 starter cards from pre-generated notes (confidence > 0.7)

**Files created:**
- `frontend/src/components/MatchInsight.jsx`

**Files modified:**
- `frontend/src/components/MatchDashboard.jsx`

### File List

**New:**
- `frontend/src/components/MatchInsight.jsx` — ~520 lines, trivia cards + Q&A panel

**Modified:**
- `frontend/src/components/MatchDashboard.jsx` — MatchInsight integration

**Already existed (no changes needed):**
- `api/server.py` — WebSocket handlers already support `query` and `answer`
- `agents/live_agent.py` — Q&A generation already implemented
