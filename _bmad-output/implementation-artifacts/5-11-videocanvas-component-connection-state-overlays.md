# Story 5.11: VideoCanvas Component — Connection State Overlays

**Status:** done  
**Epic:** Epic 5 — UI/UX Revamp  
**Priority:** High (Wave 2)

---

## Story

As a user watching the match stream,
I want clear visual feedback about connection state and streaming status,
So that I know when the stream is live, paused, or reconnecting.

**Reference:** `.bmad/screens/pitchai-landing-page.html` — Midnight Stadium tokens

---

## Acceptance Criteria

**Given** the VideoCanvas component is rendered
**When** streaming is active
**Then** the video player shows the tactical overlay with player/ball markers

**Given** connection is lost
**When** WebSocket disconnects
**Then** overlay shows "Reconnecting..." with `var(--warning)` color

**Given** stream is paused
**When** user pauses playback
**Then** pause indicator uses `var(--text-muted)` for icon

**Given** trivia card arrives
**When** confidence >= 0.6
**Then** card fades in with token-based styling

**And** overlay uses `var(--bg-surface-container)` (#2A2A2A) for semi-transparent backgrounds
**And** player dots use semantic colors (home=blue, away=red from tokens)
**And** all text uses `var(--text-primary)` or `var(--text-secondary)`

---

## Tasks

- [x] VideoCanvas uses `var(--bg-surface-container)` for overlay backgrounds
- [x] Connection state uses `var(--warning)` for reconnecting, `var(--danger)` for disconnected
- [x] Tactical overlay uses token-based colors
- [x] Trivia card animation uses Midnight Stadium tokens
- [x] Player/ball markers use semantic colors
- [ ] Add Playwright test: connection state overlays
- [ ] Add Playwright test: tactical detection visibility

---

## Dev Notes

- Component handles both camera input and file playback
- WebSocket connection to /ws/live for real-time updates
- Tactical detections show for 3 seconds then auto-hide
- Trivia cards auto-dismiss after 3-8 seconds based on confidence

---

## File List

| File | Action |
|------|--------|
| frontend/src/components/VideoCanvas.jsx | MODIFIED (token alignment) |
| frontend/src/components/TriviaCard.jsx | MODIFIED (token alignment) |
| frontend/src/components/ui/Badge.tsx | EXISTING (source labels) |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial story creation — documenting existing VideoCanvas implementation |
| 2026-05-06 | Aligned to Midnight Stadium tokens (bg-surface-container, semantic colors, text tokens) |

---

## Status

- [ ] ready-for-dev
- [ ] in-progress
- [ ] review
- [x] done
