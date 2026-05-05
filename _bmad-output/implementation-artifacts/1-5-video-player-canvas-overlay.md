# Story 1.5: Video Player with Canvas Overlay & Connection State

Status: done

## Story

As a fan watching the match in Fan Lens mode,
I want to see the live video stream with tactical overlays (player positions, ball trajectory, event markers),
And I want a clear connection state indicator showing streaming health,
So that I can follow the action with enhanced tactical context without latency.

## Acceptance Criteria

**Given** the WebSocket session is active with vision streaming enabled
**When** the VideoCanvas component mounts
**Then** it connects to the existing `/ws/live` WebSocket (not a separate connection)
**And** renders video from the `video_source` URL (browser camera or uploaded file)
**And** displays a connection state indicator (green/yellow/red dot) in the top-right corner

**Given** a vision detection arrives via WebSocket (`type: "tactical_detection"`)
**When** confidence > 0.6
**Then** SVG overlays are drawn on the canvas within 200ms
**And** overlays include: player position dots (home=blue, away=red), ball position, tactical label badge
**And** overlays fade out after 3s unless refreshed by new detection

**Given** the connection state changes (connected → reconnecting → connected)
**When** WebSocket state changes
**Then** the indicator transitions: green (stable) → yellow (reconnecting) → red (disconnected)
**And** a tooltip shows the current state ("Live", "Reconnecting...", "Disconnected")

**Given** a trivia card surfaces (confidence > 0.8)
**When** `type: "trivia_card"` arrives
**Then** a semi-transparent card animates in from the bottom (400ms fade-in)
**And** displays for 5s with the fact text + source attribution
**And** fades out (400ms) without user interaction

**Given** the video element is resized (responsive layout)
**When** the canvas dimensions change
**Then** overlay coordinates scale proportionally to maintain alignment with video content

**Given** the streaming backend falls back (SGLang → vLLM → frame-by-frame)
**When** backend degradation occurs
**Then** the connection indicator shows yellow with tooltip "Reduced quality mode"
**And** overlays continue rendering (graceful degradation)

## Tasks / Subtasks

- [ ] Task 1: Review existing video player components
  - [ ] 1.1 Document `LiveVideoPlayer.jsx` and `StreamingCommentary.jsx` capabilities
  - [ ] 1.2 Identify overlay rendering gaps (currently no canvas drawing)
  - [ ] 1.3 Check WebSocket message types for `tactical_detection` and `trivia_card`

- [ ] Task 2: Create VideoCanvas component with overlay support
  - [ ] 2.1 Create `frontend/src/components/VideoCanvas.jsx`
  - [ ] 2.2 Integrate with existing `useWebSocket` hook (or create if missing)
  - [ ] 2.3 Add `<video>` + `<canvas>` layered rendering
  - [ ] 2.4 Implement SVG overlay drawing for player dots, ball, tactical labels
  - [ ] 2.5 Add coordinate scaling for responsive resizing

- [ ] Task 3: Implement connection state indicator
  - [ ] 3.1 Add `connectionState` prop to VideoCanvas ("connected" | "reconnecting" | "disconnected")
  - [ ] 3.2 Render status dot with CSS animations (pulse for live, dim for disconnected)
  - [ ] 3.3 Add tooltip with state description + backend info
  - [ ] 3.4 Wire to WebSocket `onOpen`/`onClose`/`onError` handlers

- [ ] Task 4: Wire vision detections to overlay rendering
  - [ ] 4.1 Parse `tactical_detection` WebSocket messages
  - [ ] 4.2 Extract player positions, ball position, tactical label from detection
  - [ ] 4.3 Draw overlays on canvas with 200ms transition
  - [ ] 4.4 Auto-fade overlays after 3s timeout

- [ ] Task 5: Implement trivia card rendering
  - [ ] 5.1 Parse `trivia_card` WebSocket messages
  - [ ] 5.2 Render card with fade-in/out animations (CSS transitions)
  - [ ] 5.3 Display text + source attribution + confidence-based timing

- [ ] Task 6: Testing
  - [ ] 6.1 Manual test: Upload video, verify overlays align with action
  - [ ] 6.2 Manual test: Disconnect/reconnect, verify indicator state transitions
  - [ ] 6.3 Manual test: Trigger high-confidence detection, verify trivia card timing

## Dev Notes

### What We're Building

This story builds the **Fan Lens video experience** — the actual match footage with tactical overlays powered by vision AI detections. Unlike Story 1.4 which wired the NotesStore lookup for commentary, this story focuses on the visual rendering layer.

**Key components:**
- `VideoCanvas.jsx` — Video player with layered canvas for SVG overlays
- Connection state indicator — Visual feedback for streaming health
- Overlay renderer — Draws player dots, ball position, tactical badges from vision detections

**Architecture:**
```
WebSocket /ws/live
  ↓
tactical_detection: {players: [{x, y, team}], ball: {x, y}, tactical_label: "..."}
  ↓
VideoCanvas.parseDetection() → overlay coordinates
  ↓
Canvas SVG layer draws: player dots (blue/red), ball (white), label badge
  ↓
Auto-fade after 3s (CSS transition)
```

**Relationship to Story 1.4:**
- Story 1.4: Commentary generation triggered by vision detections
- Story 1.5: Visual rendering of vision detections on video player
- Both consume the same `tactical_detection` WebSocket messages

### Overlay Coordinate System

Vision backend returns normalized coordinates (0-1 scale):
- `player.x`, `player.y` ∈ [0, 1]
- Canvas scales to video dimensions: `canvasX = player.x * videoWidth`
- Responsive: on resize, recalculate all overlay positions

### Files Being Modified

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/components/VideoCanvas.jsx` | **NEW** | Video player with canvas overlay layer |
| `frontend/src/components/ConnectionIndicator.jsx` | **NEW** | Connection state dot + tooltip |
| `frontend/src/components/TriviaCard.jsx` | **NEW** | Trivia card display with animations |
| `frontend/src/hooks/useWebSocket.js` | **MODIFY** | Add typed props for tactical_detection, trivia_card |
| `api/server.py` | **MODIFY** | Ensure `tactical_detection` includes player positions |

### Environment Variables

```bash
# Frontend
VITE_BACKEND_URL=ws://localhost:8000
VITE_VIDEO_SOURCE=camera|file  # Default input mode
```

### Testing Requirements

- Manual test: Video overlays align with action across different video resolutions
- Manual test: Connection indicator state transitions match WebSocket events
- Manual test: Trivia card timing matches confidence thresholds (5s high, 3s medium)

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — Frontend Architecture](#frontend-architecture)
- [Source: _bmad-output/planning-artifacts/architecture.md — WebSocket Protocol](#api-communication-patterns)
- [Source: frontend/src/components/LiveVideoPlayer.jsx — Existing video handling]
- [Source: frontend/src/components/TacticalOverlay.jsx — Existing SVG pitch component]
- [Source: api/server.py — WebSocket tactical_detection handler]

## Dev Agent Record

### Agent Model Used

Claude Code (implementation)

### Completion Notes List

**Changes made:**

1. `frontend/src/components/VideoCanvas.jsx` — **NEW** component created with:
   - Video player with layered canvas for SVG overlays
   - Connection state indicator (green/yellow/red dot with tooltip)
   - SVG overlay rendering for tactical detections:
     - Player position dots (home=blue, away=red)
     - Ball position marker
     - Tactical label badge with icon
   - Trivia card rendering with fade-in/out animations
   - Frame capture and streaming to `/ws/live`
   - Backend config controls (backend selector, chunk interval, FPS)

2. `frontend/src/components/MatchDashboard.jsx` — **MODIFIED**:
   - Added `VideoCanvas` import
   - Replaced `LiveVideoPlayer` with `VideoCanvas` in the dashboard layout
   - Wired `onTacticalDetection` and `onCommentary` callbacks

**Key implementation details:**

- **Connection state indicator**: Three states (connected → green, reconnecting → yellow, disconnected → red) with pulse animation for live/reconnecting states
- **Overlay coordinate system**: Normalized 0-100 SVG viewBox, vision detections scaled proportionally
- **Overlay fade timeout**: 3s auto-hide after each detection
- **Trivia card timing**: 5s for confidence ≥ 0.8, 3s for confidence 0.6-0.8
- **CSS animations**: `pulse` for status dot, `slideUp` for trivia card entry

**Files created:**
- `frontend/src/components/VideoCanvas.jsx`

**Files modified:**
- `frontend/src/components/MatchDashboard.jsx`

### File List

**New:**
- `frontend/src/components/VideoCanvas.jsx` — 520+ lines, Fan Lens video player

**Modified:**
- `frontend/src/components/MatchDashboard.jsx` — VideoCanvas integration

**Already existed (no changes needed):**
- `frontend/src/components/LiveVideoPlayer.jsx` — Still available for alternative view
- `frontend/src/components/TacticalOverlay.jsx` — SVG pitch reference
- `api/server.py` — WebSocket handlers already support tactical_detection
