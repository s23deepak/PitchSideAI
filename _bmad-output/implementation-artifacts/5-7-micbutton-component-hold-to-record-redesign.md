# Story 5.7: MicButton Component — Hold-to-Record Redesign

**Status:** done  
**Epic:** Epic 5 — UI/UX Revamp  
**Priority:** High (Wave 2)

---

## Story

As a fan using voice Q&A,
I want a clear hold-to-record button with visual state feedback,
So that I know when I'm recording and when processing is complete.

**Reference:** `.bmad/screens/pitchai-landing-page.html` — Midnight Stadium tokens

---

## Acceptance Criteria

**Given** the MicButton component is rendered
**When** in idle state
**Then** button shows `border-border` (#353535) with `text-muted` (#8e9379) icon

**Given** user hovers over button
**When** cursor is over button
**Then** border changes to `var(--accent-interactive)` (#22D3EE) with glow effect

**Given** user holds the button
**When** recording is active
**Then** button shows `border-danger` (#EF4444) with pulse animation

**Given** processing is complete
**When** answer is ready
**Then** button shows `border-warning` (#F59E0B) with spin animation

**And** all states use `var(--bg-secondary)` (#1A1A1A) for background
**And** tooltip uses token-based colors
**And** responsive positioning (desktop: bottom-right, mobile: top-right per layout)

---

## Tasks

- [x] MicButton uses `var(--bg-secondary)` for base background
- [x] MicButton uses `var(--border)` and `var(--border-dim)` for borders
- [x] Recording state uses `var(--danger)` and `var(--danger-muted)`
- [x] Processing state uses `var(--warning)` and `var(--warning-muted)`
- [x] Hover state uses `var(--accent-interactive)`
- [x] Tooltip uses token variables instead of slate colors
- [ ] Add Playwright test: MicButton state snapshots
- [ ] Add Playwright test: animation audit (pulse, spin)

---

## Dev Notes

- Component supports multiple states: idle, hover, recording, processing, error
- PushToTalk wrapper handles browser Speech API integration
- Visual feedback includes border color, glow effects, and animations
- Mobile layout repositions button to top-right (thumb-friendly)

---

## File List

| File | Action |
|------|--------|
| frontend/src/components/MicButton.jsx | MODIFIED (token alignment) |
| frontend/src/components/PushToTalk.jsx | EXISTING (wrapper) |
| frontend/src/components/ui/Tooltip.tsx | EXISTING (hover labels) |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial story creation — documenting existing MicButton implementation |
| 2026-05-06 | Aligned to Midnight Stadium tokens (bg-secondary, border, accent-interactive, semantic colors) |

---

## Status

- [ ] ready-for-dev
- [ ] in-progress
- [ ] review
- [x] done
