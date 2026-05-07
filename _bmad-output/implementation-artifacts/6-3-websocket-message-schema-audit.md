# Story 6.3: WebSocket Message Schema Audit

**Status:** ready-for-dev  
**Epic:** Epic 6 — Production Hardening & Deployment Validation  
**Priority:** Critical (Production Reliability)

---

## Story

As a backend developer maintaining the PitchAI WebSocket infrastructure,
I want a formal, validated WebSocket message schema with TypeScript-type documentation and runtime validation,
So that frontend-backend contracts are explicit, type-safe, and prevent integration bugs.

**Reference:** Architecture Decision "API & Communication Patterns" (architecture.md lines 211-254)

---

## Acceptance Criteria

**Given** the current WebSocket implementation in `api/server.py`
**When** the audit completes
**Then** all message types are documented in a schema file with:
- Message type name
- Direction (Client→Server, Server→Client, Bidirectional)
- Required fields with types
- Optional fields with types and defaults
- Example payload for each message type

**Given** the schema documentation
**When** compared against actual server code
**Then** every `manager.send()` and `manager.broadcast()` call matches documented schema
**And** every incoming message handler validates expected fields

**Given** the schema audit
**When** gaps are found between docs and code
**Then** either code is fixed to match schema OR schema is updated to match code
**And** discrepancies are logged in the audit report

**Given** the frontend WebSocket consumption
**When** reviewing `LiveSessionContext.jsx` and component usage
**Then** all received message types are accounted for in the schema
**And** all sent message types originate from documented user interactions

**AND** the schema includes these discovered message types (non-exhaustive — audit may find more):
- `init`, `ready`, `match_event`, `tactical_detection`, `query`, `settings_update`, `language_switch`
- `commentary`, `answer`, `error`, `beat_highlight`, `trivia_card`, `language_confirmed`
- `notes_ready`, `state_snapshot` (from architecture spec, verify implementation)

---

## Developer Context

### Why This Story Matters

The WebSocket protocol is the **single source of truth** for all component state in PitchAI. Every feature — commentary, Q&A, trivia cards, beat highlighting, language switching — flows through `/ws/live`. Currently:

1. **Schema is implicit** — defined only by scattered `manager.send()` calls in `api/server.py`
2. **No runtime validation** — malformed messages fail silently or cause cryptic errors
3. **Frontend guesses types** — `LiveSessionContext.jsx` infers payload shapes from usage
4. **Architecture spec ≠ code** — `architecture.md` documents `notes_ready` and `state_snapshot`, but code may differ

This audit produces a **living schema document** that:
- Serves as the contract for future development
- Enables TypeScript migration (if desired)
- Prevents "what fields does this message have?" questions
- Makes integration testing straightforward

### What This Story Is NOT

- **NOT implementing runtime validation** — that's a future story (6-6 tech debt)
- **NOT refactoring message handlers** — just documenting what exists
- **NOT adding new message types** — unless critical gaps are found

### What This Story IS

- **Documentation + verification** — read code, write schema, verify alignment
- **Gap analysis** — find where architecture spec diverges from implementation
- **Living artifact** — schema file that future stories update

---

## Technical Requirements

### 1. Schema Documentation Format

Create `_bmad-output/docs/websocket-schema.md` with this structure:

```markdown
# PitchAI WebSocket Message Schema

**Endpoint:** `/ws/live`  
**Protocol:** WebSocket (RFC 6455)  
**Content Type:** `application/json`

## Message Types

### `init` (Client → Server)

Session initialization. Must be first message after connect.

**Required Fields:**
- `home_team` (string): Home team name
- `away_team` (string): Away team name
- `sport` (string): Sport type (`soccer`, `cricket`, etc.)

**Optional Fields:**
- `match_session` (string|null): Existing session to rejoin

**Example:**
```json
{"type": "init", "home_team": "Real Madrid", "away_team": "Barcelona", "sport": "soccer"}
```
```

### 2. Message Type Inventory

Based on `api/server.py` scan, audit these message types (may find more):

**Client → Server:**
| Message Type | Handler Location | Required Fields | Optional Fields |
|--------------|------------------|-----------------|-----------------|
| `init` | Line ~1007 | `home_team`, `away_team`, `sport` | `match_session` |
| `match_event` | Line ~1046 | `description` | — |
| `tactical_detection` | Line ~1094 | `analysis` (object) | — |
| `query` | Line ~1302 | `text` | — |
| `settings_update` | Line ~1255 | `bias`, `excitement`, `knowledge_depth` | — |
| `language_switch` | Line ~1287 | `language` | — |

**Server → Client:**
| Message Type | Broadcast Location | Required Fields | Optional Fields |
|--------------|-------------------|-----------------|-----------------|
| `ready` | Line ~1011 | `message` | — |
| `commentary` | Line ~1080, ~1137, ~1201 | `text`, `source`, `timestamp` | `gameState`, `triviaCard` |
| `answer` | Line ~1320, ~265 | `text`, `timestamp` | — |
| `error` | Line ~1359, ~1512, ~1797 | `message` | `code` |
| `beat_highlight` | Line ~1233 | `beat_index`, `confidence` | — |
| `trivia_card` | Line ~1244, ~1094 | `text`, `tags` | — |
| `language_confirmed` | Line ~1297 | `language` | — |
| `notes_ready` | **AUDIT REQUIRED** — may not be implemented | `beat_count`, `sections` | — |
| `state_snapshot` | **AUDIT REQUIRED** — may not be implemented | `gameState`, `lastCommentary` | — |

### 3. Code-to-Schema Verification Steps

1. **Read `api/server.py` WebSocket handler** (lines ~900-1800)
   - Find every `manager.send()` and `manager.broadcast()` call
   - Extract message type and payload structure
   - Compare against architecture.md claims

2. **Read `LiveSessionContext.jsx`**
   - Find every `pitchai:` CustomEvent listener
   - Find every message dispatched to server
   - Verify field names match server expectations (snake_case ↔ camelCase)

3. **Read component files** that consume WebSocket state:
   - `VideoCanvas.jsx` — tactical detections
   - `Teleprompter.jsx` — commentary, beat_highlight
   - `TriviaCard.jsx` — trivia_card
   - `ControlsTray.jsx` — settings_update, language_switch
   - `MicButton.jsx` — query (via speech recognition)

4. **Cross-reference with architecture.md** (lines 240-254):
   ```
   | Direction | Message Type | Purpose |
   |-----------|-------------|---------|
   | Client → Server | `init` | Session setup |
   | Client → Server | `match_event` | Manual event input |
   | ... |
   ```

### 4. Gap Analysis Categories

When code ≠ spec, categorize:

| Gap Type | Example | Resolution |
|----------|---------|------------|
| **Missing Implementation** | `notes_ready` in spec, not in code | Implement OR remove from spec |
| **Field Mismatch** | `gameState` vs `game_state` | Standardize (camelCase for JSON) |
| **Undocumented Message** | `ping` found in code, not in spec | Add to schema |
| **Type Mismatch** | Spec says string, code sends number | Fix code or update spec |

### 5. Output Files

| File | Purpose |
|------|---------|
| `_bmad-output/docs/websocket-schema.md` | Living schema document |
| `_bmad-output/implementation-artifacts/6-3-audit-report.md` | Audit findings, gaps, resolutions |

---

## Architecture Compliance

### Naming Conventions (from architecture.md)

- **Python (server):** `snake_case` keys (`match_session`, `home_team`)
- **JavaScript (client):** `camelCase` keys (`matchSession`, `homeTeam`)
- **Bridge:** Translate at WebSocket boundary in `api/server.py`

**Audit Check:** Verify `api/server.py` does translation, or if frontend directly uses `snake_case`.

### Message Format Standard (from architecture.md)

All messages must follow:
```json
{"type": "...", ...data, "timestamp": "ISO8601"}
```

**Audit Check:** Verify all `manager.send()` calls include `timestamp`.

### Error Response Format (from architecture.md)

```json
{"type": "error", "code": "ERROR_CODE", "message": "..."}
```

**Audit Check:** Verify all error messages include `code` field, not just `message`.

---

## Testing Requirements

### Manual Verification Tests

1. **Schema Completeness Test**
   - Grep for all `manager.send(` and `manager.broadcast(` calls
   - Verify each message type appears in schema
   - Verify field names match exactly

2. **Direction Verification Test**
   - For each Client→Server type: find handler in `api/server.py`
   - For each Server→Client type: find broadcast location

3. **Frontend Integration Test**
   - For each Server→Client type: find consumer in frontend components
   - Verify no unused message types (bloat)

---

## Project Context Reference

### Related Architecture Decisions

From `architecture.md`:

- **Lines 211-254:** API & Communication Patterns — defines `notes_ready`, `state_snapshot`, settings update flow
- **Lines 378-385:** Format Standards — message format, error format, timestamp requirement
- **Lines 362-363:** Naming Conventions — snake_case Python ↔ camelCase JS bridge

### Related Stories

- **Story 6-1:** HF Space Deployment — requires stable WebSocket for demo
- **Story 6-2:** Settings Persistence — depends on `settings_update` message schema
- **Story 6-6:** Technical Debt — may implement runtime validation using this schema

---

## Story Completion Status

- [ ] ready-for-dev
- [ ] in-progress
- [ ] review
- [ ] done

---

## Dev Agent Record

### Audit Plan

1. **Inventory Phase** — Extract all message types from `api/server.py`
2. **Documentation Phase** — Write schema in standard format
3. **Verification Phase** — Cross-reference code, spec, and frontend
4. **Gap Analysis Phase** — Document discrepancies and resolutions

### Files to Audit

| File | Purpose |
|------|---------|
| `api/server.py` | WebSocket server implementation |
| `frontend/src/contexts/LiveSessionContext.jsx` | Frontend WebSocket state management |
| `frontend/src/components/**/*.jsx` | Component message consumers |
| `_bmad-output/planning-artifacts/architecture.md` | Architecture spec (source of truth) |

### Output Files

| File | Status |
|------|--------|
| `_bmad-output/docs/websocket-schema.md` | To create |
| `_bmad-output/implementation-artifacts/6-3-audit-report.md` | To create |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial story creation — WebSocket schema audit for production reliability |
