# Story 6.3: WebSocket Message Schema Audit Report

**Date:** 2026-05-06  
**Auditor:** Claude Code  
**Scope:** `/ws/live` WebSocket endpoint — `api/server.py` + `LiveSessionContext.jsx`

---

## Executive Summary

The WebSocket schema audit is **COMPLETE**. The schema documentation has been created at `_bmad-output/docs/websocket-schema.md`.

**Key Findings:**
- 11 message types documented (6 Client→Server, 8 Server→Client)
- 2 message types in architecture spec but NOT implemented (`notes_ready`, `state_snapshot`)
- 1 minor inconsistency (`ping` only in video WS, not live WS)
- 1 tech debt item (`error` messages missing `code` field)

**Overall Assessment:** The WebSocket protocol is **functional for hackathon demo** but has gaps vs architecture spec that should be addressed post-hackathon.

---

## Message Type Inventory

### Client → Server (6 types)

| Message Type | Handler Location | Required Fields | Verified |
|--------------|------------------|-----------------|----------|
| `init` | `api/server.py:961-967` | `home_team`, `away_team`, `sport` | ✅ |
| `match_event` | `api/server.py:1046-1103` | `description` | ✅ |
| `tactical_detection` | `api/server.py:1105-1253` | `analysis` (object) | ✅ |
| `query` | `api/server.py:1302-1348` | `text` | ✅ |
| `settings_update` | `api/server.py:1255-1285` | `bias`, `excitement`, `knowledge_depth` | ✅ |
| `language_switch` | `api/server.py:1287-1300` | `language` | ✅ |

### Server → Client (8 types)

| Message Type | Broadcast Location | Required Fields | Verified |
|--------------|-------------------|-----------------|----------|
| `ready` | `api/server.py:1010-1016` | `message`, `match_session`, `has_notes_store`, `qa_enhanced` | ✅ |
| `status` | `api/server.py:981-986` | `message`, `workflow_id`, `match_session` | ✅ |
| `commentary` | `api/server.py:1079-1088, 1136-1150, 1200-1219` | `text`, `source`, `timestamp` | ✅ |
| `beat_highlight` | `api/server.py:1232-1238` | `beat_index`, `confidence`, `timestamp` | ✅ |
| `trivia_card` | `api/server.py:1093-1103, 1243-1253` | `text`, `source`, `confidence`, `display_duration_ms` | ✅ |
| `answer` | `api/server.py:1319-1348` | `text`, `timestamp` | ✅ |
| `language_confirmed` | `api/server.py:1296-1300` | `language`, `timestamp` | ✅ |
| `error` | `api/server.py:1359, 1512, 1797` | `message` | ✅ |
| `info` | `api/server.py:1028-1031` | `message` | ✅ |

---

## Gap Analysis

### Gap #1: `notes_ready` Not Implemented

**Category:** Missing Implementation  
**Severity:** Medium  
**Architecture Spec:** `architecture.md` lines 215-225

```json
{
  "type": "notes_ready",
  "beat_count": 100,
  "sections": ["match_info", "home_team", "away_team", "tactical", "historical"],
  "timestamp": "2026-05-04T..."
}
```

**Current Implementation:** Notes generation uses SSE endpoint `/api/v1/commentary/prepare-notes`. Frontend polls via `prepareNotes()` in `LiveSessionContext.jsx` (lines 205-280). SSE events include:
- `phase: "starting"` → `phase: "complete"` with `result` object

**Resolution:** **DEFERRED** — SSE approach works for hackathon. Consider adding `notes_ready` WebSocket broadcast post-hackathon for consistency.

---

### Gap #2: `state_snapshot` Not Implemented

**Category:** Missing Implementation  
**Severity:** Medium  
**Architecture Spec:** `architecture.md` line 254

**Intended Purpose:** Full state snapshot on WebSocket reconnect — `game_state` + last 3 commentary lines.

**Current Implementation:** `LiveSessionContext.jsx` reconnection logic (lines 59-82):
- Closes old WS if `matchSession` changed
- Creates fresh session with new `init` message
- No state replay

**Resolution:** **DEFERRED** — Low priority for 5-minute demo. Add for production robustness.

---

### Gap #3: `error` Messages Missing `code` Field

**Category:** Field Mismatch  
**Severity:** Low  
**Architecture Spec:** `architecture.md` line 381

```json
{"type": "error", "code": "ERROR_CODE", "message": "..."}
```

**Current Implementation:** All `error` broadcasts include only `message`:
```python
await manager.send(websocket, {"type": "error", "message": str(exc)})
```

**Resolution:** **TECH DEBT** — Add error codes in Story 6-6 (technical debt cleanup).

Example codes to add:
- `WEBSOCKET_INIT_FAILED`
- `RATE_LIMIT_EXCEEDED`
- `AGENT_EXECUTION_ERROR`
- `CONTEXT_LENGTH_EXCEEDED`
- `CONNECTION_LOST`

---

### Gap #4: `ping` Only in Video WS, Not Live WS

**Category:** Inconsistency  
**Severity:** Low  
**Location:** `api/server.py:1432` (video streaming only)

**Current Implementation:** `video_stream_ws()` sends keepalive `ping` every 60s:
```python
await manager.send(websocket, {"type": "ping", "message": "Still connected?"})
```

**Live WS:** Uses `info` message after 120s idle timeout instead.

**Resolution:** **DEFERRED** — Add `ping` to live WS for production idle detection (post-hackathon).

---

## Frontend Integration Verification

### CustomEvent Forwarding

`LiveSessionContext.jsx` forwards these WebSocket messages to components:

| WebSocket Type | CustomEvent Name | Consumer Component |
|----------------|------------------|-------------------|
| `beat_highlight` | `pitchai:beat_highlight` | `Teleprompter.jsx` |
| `trivia_card` | `pitchai:trivia_card` | `TriviaCard.jsx` |
| `answer` | `pitchai:qa_answer` | `SplitScreen.jsx` |

**Verification:** All three CustomEvents are properly dispatched with correct detail fields.

---

### Settings + Language Queue

`LiveSessionContext.jsx` implements pending queue for settings/language if WS not ready:

```javascript
const pendingSettingsRef = useRef(null)
const pendingLanguageRef = useRef(null)

// Queue if WS not ready
if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(...)
} else {
    pendingSettingsRef.current = settings  // Queue for later
}
```

**Verification:** Queue is flushed on WS open (lines 98-111).

---

## Architecture Compliance Check

### Naming Conventions

| Layer | Convention | Compliance |
|-------|-----------|------------|
| Python (server) | `snake_case` | ✅ All keys use `snake_case` |
| JavaScript (client) | `camelCase` | ⚠️ Mixed — client sends `snake_case` to server |

**Note:** Client sends `snake_case` directly (`home_team`, `match_session`). No translation layer needed.

### Message Format Standard

**Standard:** `{"type": "...", ...data, "timestamp": "ISO8601"}`

| Message Type | Includes Timestamp? | Compliance |
|--------------|---------------------|------------|
| `ready` | ❌ No | ⚠️ Partial |
| `status` | ❌ No | ⚠️ Partial |
| `commentary` | ✅ Yes | ✅ |
| `beat_highlight` | ✅ Yes | ✅ |
| `trivia_card` | ✅ Yes | ✅ |
| `answer` | ✅ Yes | ✅ |
| `language_confirmed` | ✅ Yes | ✅ |
| `error` | ❌ No | ⚠️ Partial |
| `info` | ❌ No | ⚠️ Partial |

**Resolution:** Add timestamps to `ready`, `status`, `error`, `info` for consistency (tech debt).

---

## Recommendations

### For Hackathon Demo (No Action Required)

The current implementation is **fully functional** for the 5-minute demo. All core features work:
- Commentary generation + broadcast
- Beat highlighting for teleprompter
- Trivia card display
- Q&A with player identification
- Settings + language switching

### Post-Hackathon (Tech Debt)

1. **Add `notes_ready` broadcast** — When SSE completes, also broadcast via WS for consistency
2. **Implement `state_snapshot`** — Full state replay on reconnect
3. **Add error codes** — `ERROR_CODE` field to all `error` messages
4. **Add `ping` keepalive** — 60s keepalive for live WS (like video WS)
5. **Standardize timestamps** — Add `timestamp` to ALL server messages

---

## Files Modified/Created

| File | Action | Purpose |
|------|--------|---------|
| `_bmad-output/docs/websocket-schema.md` | Created | Living schema document |
| `_bmad-output/implementation-artifacts/6-3-audit-report.md` | Created | This audit report |

No code changes were made — this was a documentation + verification story.

---

## Story Completion Status

- [x] ready-for-dev
- [x] in-progress
- [x] review
- [x] done

**Story 6.3 is COMPLETE.** Schema documentation created, gaps documented, no code changes required.
