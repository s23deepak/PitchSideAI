# PitchAI WebSocket Message Schema

**Endpoint:** `/ws/live`  
**Protocol:** WebSocket (RFC 6455)  
**Content Type:** `application/json`  
**Last Updated:** 2026-05-06

---

## Overview

The `/ws/live` WebSocket endpoint is the **single source of truth** for all real-time state in PitchAI. All component state flows through this connection — commentary, Q&A, trivia cards, beat highlighting, and settings.

### Connection Flow

```
1. Client connects to ws://backend/ws/live
2. Client sends "init" message with match details
3. Server responds with "status" → "ready"
4. Server starts periodic commentary background task
5. Client sends events/queries; Server broadcasts commentary/answers
6. Client disconnects or times out after 120s idle
```

### Message Format Standard

All messages follow this format:
```json
{"type": "...", ...dataFields, "timestamp": "ISO8601"}
```

- **Python (server):** `snake_case` keys (`match_session`, `home_team`)
- **JavaScript (client):** `camelCase` keys (`matchSession`, `homeTeam`)
- **Bridge:** Translation happens in `LiveSessionContext.jsx` — server sends `snake_case`, client converts to `camelCase` when dispatching CustomEvents

---

## Client → Server Messages

### `init`

**Direction:** Client → Server  
**Required:** Yes (must be first message after connect)  
**Handler:** `live_audio_ws()` line 961-967

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `home_team` | string | Home team name (e.g., "Real Madrid") |
| `away_team` | string | Away team name (e.g., "Barcelona") |
| `sport` | string | Sport type: `soccer`, `cricket`, `basketball`, `tennis`, `rugby`, `american_football`, `hockey`, `baseball` |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `match_session` | string | Existing session key to rejoin (rarely used) |

**Example:**
```json
{"type": "init", "home_team": "Real Madrid", "away_team": "Barcelona", "sport": "soccer"}
```

---

### `match_event`

**Direction:** Client → Server  
**Required:** No (user-triggered)  
**Handler:** `live_audio_ws()` line 1046-1103

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Natural language event description (e.g., "Haaland scores! 1-0 in 34'") |

**Example:**
```json
{"type": "match_event", "description": "Goal! Vinicius Jr. scores from outside the box. 2-0 in 67'"}
```

**Server Response:** Broadcasts `commentary` message with `gameState` updated.

---

### `tactical_detection`

**Direction:** Client → Server  
**Required:** No (vision model triggered)  
**Handler:** `live_audio_ws()` line 1105-1253

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `analysis` | object | Tactical analysis result from vision model |

**Analysis Object Schema:**
| Field | Type | Description |
|-------|------|-------------|
| `tactical_label` | string | Normalized label: `goal`, `yellow_card`, `red_card`, `substitution`, `foul`, `corner`, `free_kick_dangerous`, `offside` |
| `confidence` | float | 0.0-1.0 confidence score |
| `timestamp_ms` | number | Video timestamp in milliseconds |
| `actionable_insight` | string | Brief insight text |
| `key_observation` | string | Key observation text |
| `clip_start_timestamp_ms` | number | Clip start time |
| `clip_end_timestamp_ms` | number | Clip end time |

**Example:**
```json
{
  "type": "tactical_detection",
  "analysis": {
    "tactical_label": "goal",
    "confidence": 0.92,
    "timestamp_ms": 2040000,
    "actionable_insight": "Clinical finish from close range after cross from right wing",
    "key_observation": "Striker positioned perfectly at far post",
    "clip_start_timestamp_ms": 2035000,
    "clip_end_timestamp_ms": 2045000
  }
}
```

**Server Response:** Broadcasts `commentary` + `beat_highlight` + optionally `trivia_card`.

---

### `query`

**Direction:** Client → Server  
**Required:** No (user-triggered Q&A)  
**Handler:** `live_audio_ws()` line 1302-1348

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Question text (e.g., "Who scored the last goal?") |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `confidence` | float | STT confidence score (0.0-1.0) if from speech recognition |

**Example:**
```json
{"type": "query", "text": "What formation is Real Madrid playing?", "confidence": 0.95}
```

**Server Response:** `answer` message with optional `player_identification` and `overlay_coordinates`.

---

### `settings_update`

**Direction:** Client → Server  
**Required:** No (user-triggered)  
**Handler:** `live_audio_ws()` line 1255-1285

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `bias` | float | Commentary bias: -1.0 (away) to 1.0 (home), default 0 |
| `excitement` | float | Excitement level: 0.0 (calm) to 1.0 (excited), default 0.5 |
| `knowledge_depth` | float | Knowledge depth: 0.0 (casual) to 1.0 (expert), default 0.5 |

**Validation:** All values are clamped to valid ranges on server.

**Example:**
```json
{"type": "settings_update", "bias": 0.3, "excitement": 0.8, "knowledge_depth": 0.5}
```

**Server Response:** None (settings stored for next commentary cycle).

---

### `language_switch`

**Direction:** Client → Server  
**Required:** No (user-triggered)  
**Handler:** `live_audio_ws()` line 1287-1300

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `language` | string | ISO 639-1 language code: `en`, `es`, `fr`, `de`, etc. |

**Example:**
```json
{"type": "language_switch", "language": "es"}
```

**Server Response:** `language_confirmed` acknowledgment.

---

## Server → Client Messages

### `ready`

**Direction:** Server → Client  
**Trigger:** Session initialized successfully  
**Broadcast:** `live_audio_ws()` line 1010-1016

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"ready"` |
| `message` | string | Status message |
| `match_session` | string | Session key (e.g., `soccer#real-madrid#vs#barcelona`) |
| `has_notes_store` | boolean | Whether pre-match notes exist |
| `qa_enhanced` | boolean | Story 2.2 + 2.4 parallel Q&A enabled |

**Example:**
```json
{
  "type": "ready",
  "message": "Session ready. Commentary will fire on events, frame detections, and every 60 s. Q&A available with player identification.",
  "match_session": "soccer#real-madrid#vs#barcelona",
  "has_notes_store": true,
  "qa_enhanced": true
}
```

---

### `status`

**Direction:** Server → Client  
**Trigger:** Session starting, research beginning  
**Broadcast:** `live_audio_ws()` line 981-986

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"status"` |
| `message` | string | Status message (e.g., "Researching Real Madrid vs Barcelona...") |
| `workflow_id` | string | Orchestrator workflow ID |
| `match_session` | string | Session key |

**Example:**
```json
{
  "type": "status",
  "message": "Researching Real Madrid vs Barcelona...",
  "workflow_id": "wf_abc123",
  "match_session": "soccer#real-madrid#vs#barcelona"
}
```

---

### `commentary`

**Direction:** Server → Client  
**Trigger:** Event received, tactical detection, periodic timer (60s)  
**Broadcast:** `live_audio_ws()` lines 1079-1088, 1136-1150, 1200-1219

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"commentary"` |
| `text` | string | Commentary text |
| `source` | string | Source type: `event`, `timer`, `detection`, `analysis` |
| `timestamp` | string | ISO 8601 timestamp |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `gameState` | object | Current `GameState` dict (always included for event/detection triggers) |
| `trigger` | string | What triggered this commentary |
| `label` | string | Tactical label (for detection-triggered) |
| `confidence` | float | Confidence score |
| `videoTimestampMs` | number | Video timestamp in ms |
| `videoRangeLabel` | string | Human-readable time range (e.g., "34:00–34:10") |
| `beat_indices` | array | Beat indices for teleprompter highlighting (Story 3.2) |
| `resolved_tag` | string | Normalized event tag |
| `retrieved_beat_count` | number | Number of beats retrieved from NotesStore |

**Example:**
```json
{
  "type": "commentary",
  "text": "Vinicius Jr. has been electric down the left flank! The Brazilian has completed 8 dribbles tonight — more than any other player on the pitch.",
  "source": "detection",
  "label": "attacking_play",
  "confidence": 0.87,
  "videoTimestampMs": 2040000,
  "videoRangeLabel": "34:00–34:10",
  "trigger": "Vinicius completes dazzling run down left wing",
  "timestamp": "2026-05-06T14:32:15.123Z",
  "gameState": {"home_score": 2, "away_score": 0, "minute": 67},
  "beat_indices": [42, 43, 44],
  "resolved_tag": "attacking_play",
  "retrieved_beat_count": 3
}
```

---

### `beat_highlight`

**Direction:** Server → Client  
**Trigger:** High-confidence beat retrieved from NotesStore  
**Broadcast:** `live_audio_ws()` line 1232-1238

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"beat_highlight"` |
| `beat_index` | number | Index of beat to highlight in NotesStore |
| `confidence` | float | Confidence score (0.0-1.0) |
| `timestamp` | string | ISO 8601 timestamp |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `next_indices` | array | Next 3 beat indices for preview (teleprompter auto-scroll) |

**Example:**
```json
{
  "type": "beat_highlight",
  "beat_index": 42,
  "confidence": 0.92,
  "next_indices": [43, 44, 45],
  "timestamp": "2026-05-06T14:32:15.456Z"
}
```

**Client Action:** Dispatches `pitchai:beat_highlight` CustomEvent for Teleprompter component.

---

### `trivia_card`

**Direction:** Server → Client  
**Trigger:** High-confidence beat retrieved (confidence > 0.6)  
**Broadcast:** `live_audio_ws()` lines 1093-1103, 1243-1253

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"trivia_card"` |
| `text` | string | Trivia card text |
| `source` | string | Data source (StatsBomb, Firecrawl, FBref) |
| `confidence` | float | Confidence score |
| `display_duration_ms` | number | How long to display (e.g., 5000) |
| `timestamp` | string | ISO 8601 timestamp |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `event_tag` | string | Associated event tag |
| `fade_in_ms` | number | Fade in duration |
| `fade_out_ms` | number | Fade out duration |

**Example:**
```json
{
  "type": "trivia_card",
  "text": "Vinicius Jr. has 12 goals this season — already a career high!",
  "source": "Firecrawl",
  "event_tag": "attacking_play",
  "confidence": 0.88,
  "display_duration_ms": 5000,
  "fade_in_ms": 400,
  "fade_out_ms": 400,
  "timestamp": "2026-05-06T14:32:15.789Z"
}
```

**Client Action:** Dispatches `pitchai:trivia_card` CustomEvent for TriviaCard component.

---

### `answer`

**Direction:** Server → Client  
**Trigger:** Q&A query processed  
**Broadcast:** `live_audio_ws()` line 1319-1348

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"answer"` |
| `text` | string | Answer text |
| `timestamp` | string | ISO 8601 timestamp |

**Optional Fields (Story 2.2 + 2.4):**
| Field | Type | Description |
|-------|------|-------------|
| `gameState` | object | Current game state |
| `temporal_context` | string | `"full"` or `"limited"` — KV cache retention status |
| `timestamp_ms` | number | Video timestamp for split-screen navigation |
| `player_identification` | object | Story 2.4 player ID result |
| `overlay_coordinates` | object | SVG overlay coordinates for Fan Lens |

**Player Identification Object:**
| Field | Type | Description |
|-------|------|-------------|
| `player_name` | string | Identified player name |
| `confidence` | float | ID confidence (0.0-1.0) |
| `source` | string | ID source: `jersey_number`, `lineup_data`, `facial_features` |
| `jersey_number` | number | Jersey number if identified |

**Overlay Coordinates Object:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"circle"` or `"zone"` |
| `cx` / `cy` | number | Circle center coordinates |
| `r` | number | Circle radius |
| `rx` / `ry` | number | Zone dimensions (if zone type) |
| `stroke` | string | SVG stroke color (hex) |
| `stroke_width` | number | SVG stroke width |

**Example:**
```json
{
  "type": "answer",
  "text": "Real Madrid is playing a 4-3-3 formation with Vinicius Jr. on the left wing, Benzema up top, and Rodrygo on the right.",
  "timestamp": "2026-05-06T14:35:22.123Z",
  "gameState": {"home_score": 2, "away_score": 0, "minute": 70},
  "temporal_context": "full",
  "timestamp_ms": 2100000,
  "player_identification": {
    "player_name": "Vinicius Jr.",
    "confidence": 0.95,
    "source": "jersey_number + lineup_data",
    "jersey_number": 20
  },
  "overlay_coordinates": {
    "type": "circle",
    "cx": 35,
    "cy": 50,
    "r": 8,
    "stroke": "#00ff00",
    "stroke_width": 3
  }
}
```

**Client Action:** Dispatches `pitchai:qa_answer` CustomEvent for SplitScreen component.

---

### `language_confirmed`

**Direction:** Server → Client  
**Trigger:** Language switch acknowledged  
**Broadcast:** `live_audio_ws()` line 1296-1300

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"language_confirmed"` |
| `language` | string | Confirmed language code |
| `timestamp` | string | ISO 8601 timestamp |

**Example:**
```json
{
  "type": "language_confirmed",
  "language": "es",
  "timestamp": "2026-05-06T14:30:00.000Z"
}
```

---

### `error`

**Direction:** Server → Client  
**Trigger:** Any error condition  
**Broadcast:** `live_audio_ws()` lines 1359, 1512, 1797

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"error"` |
| `message` | string | Error message |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Error code (not consistently implemented — tech debt) |

**Example:**
```json
{"type": "error", "message": "Connection timeout"}
```

---

### `info`

**Direction:** Server → Client  
**Trigger:** Session idle timeout (120s)  
**Broadcast:** `live_audio_ws()` line 1028-1031

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"info"` |
| `message` | string | Info message |

**Example:**
```json
{"type": "info", "message": "Session idle. Reconnect to continue."}
```

---

## Undocumented / Missing Message Types

### `notes_ready` (Architecture Spec Only)

**Status:** Documented in `architecture.md` line 215-225, **NOT implemented** in code.

**Intended Purpose:** Broadcast when pre-match notes generation completes.

**Current Implementation:** Notes generation is via SSE `/api/v1/commentary/prepare-notes`, not WebSocket. Frontend polls via `prepareNotes()` in `LiveSessionContext.jsx`.

**Recommendation:** Either:
1. Implement `notes_ready` broadcast when SSE completes (consistent with WebSocket-first architecture)
2. Remove from architecture spec (current SSE approach works)

---

### `state_snapshot` (Architecture Spec Only)

**Status:** Documented in `architecture.md` line 254, **NOT implemented** in code.

**Intended Purpose:** Full state snapshot on WebSocket reconnect.

**Current Implementation:** Reconnection logic in `LiveSessionContext.jsx` closes old WS and creates new session with fresh `init`. No state replay.

**Recommendation:** Implement for production robustness (post-hackathon).

---

### `ping` (Code Only)

**Status:** Implemented in `video_stream_ws()` line 1432, not in `/ws/live`.

**Purpose:** Keepalive check for video streaming WebSocket.

**Recommendation:** Add to `/ws/live` for production idle detection (currently uses `info` message).

---

## CustomEvent Forwarding (Frontend)

The `LiveSessionContext.jsx` forwards WebSocket messages to React components via CustomEvents:

| WebSocket Type | CustomEvent Name | Detail Fields |
|----------------|------------------|---------------|
| `beat_highlight` | `pitchai:beat_highlight` | `beatIndex`, `confidence`, `nextIndices` |
| `trivia_card` | `pitchai:trivia_card` | Full message payload |
| `answer` | `pitchai:qa_answer` | Full message payload |

Components listen via:
```javascript
window.addEventListener('pitchai:beat_highlight', (e) => { ... })
```

---

## Gap Analysis Summary

| Gap | Category | Severity | Resolution |
|-----|----------|----------|------------|
| `notes_ready` not implemented | Missing Implementation | Medium | Keep SSE approach for hackathon; consider WS broadcast post-hackathon |
| `state_snapshot` not implemented | Missing Implementation | Medium | Low priority for 5-min demo; add for production |
| `error` missing `code` field | Field Mismatch | Low | Tech debt — add error codes in 6-6 |
| `ping` only in video WS, not live WS | Inconsistency | Low | Add to live WS for production idle detection |

---

## Related Files

| File | Purpose |
|------|---------|
| `api/server.py` | WebSocket server implementation (lines 915-1367) |
| `frontend/src/contexts/LiveSessionContext.jsx` | Frontend state management |
| `frontend/src/components/Teleprompter.jsx` | Consumes `beat_highlight` |
| `frontend/src/components/TriviaCard.jsx` | Consumes `trivia_card` |
| `frontend/src/components/SplitScreen.jsx` | Consumes `answer` |
| `_bmad-output/planning-artifacts/architecture.md` | Architecture spec (lines 211-254) |
