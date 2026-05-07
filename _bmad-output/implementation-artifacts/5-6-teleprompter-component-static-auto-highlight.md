# Story 5.6: Teleprompter Component — Static Display + Auto-Highlight

**Status:** done  
**Epic:** Epic 5 — UI/UX Revamp  
**Priority:** High (Wave 2)

---

## Story

As a commentator,
I want to see my pre-generated notes with auto-highlighting synced to match events,
So that I can stay on track during live commentary without manual scrolling.

**Reference:** `.bmad/screens/pitchai-landing-page.html` — Midnight Stadium tokens

---

## Acceptance Criteria

**Given** the Teleprompter component is rendered
**When** notes are being generated
**Then** a progress bar shows build status (0-100%)

**Given** notes generation is complete
**When** the match is live
**Then** the current beat is highlighted with:
- Background: `var(--accent-narrative-muted)` (rgba(255, 225, 109, 0.08))
- Left border: 3px solid `var(--accent-narrative)` (#ffe16d)
- ▶ marker before the beat text
- Next 3 beats visible with fading opacity

**Given** the user manually scrolls
**When** auto-scroll is interrupted
**Then** "Back to live" button appears to resume sync

**And** all text uses `var(--text-primary)` (#e5e2e1) for body, `var(--text-secondary)` (#c4c9ac) for metadata
**And** panel background uses `var(--bg-surface)` (#1A1A1A)
**And** tabs use Midnight Stadium token classes

---

## Tasks

- [x] Teleprompter uses `var(--bg-surface)` for panel background
- [x] Teleprompter uses `var(--text-primary)` and `var(--text-secondary)` for text
- [x] Highlight uses `var(--accent-narrative-muted)` and `var(--accent-narrative)`
- [x] Progress bar uses `var(--accent-critical)` gradient
- [x] Tabs use token-based styling
- [ ] Add Playwright test: teleprompter snapshot (dark mode)
- [ ] Add Playwright test: highlight visibility audit

---

## Dev Notes

- Component already implements confidence gating (skip beats < 0.6)
- Auto-scroll keeps current beat at ~30% from top
- Hold mode shows "Catch up" button when user scrolls manually
- Use CSS custom properties, not Tailwind hardcoded colors

---

## File List

| File | Action |
|------|--------|
| frontend/src/components/Teleprompter.jsx | MODIFIED (token alignment) |
| frontend/src/components/ui/Tabs.tsx | EXISTING (used for sections) |
| frontend/src/components/ui/Progress.tsx | EXISTING (used for build status) |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial story creation — documenting existing Teleprompter implementation |
| 2026-05-06 | Aligned to Midnight Stadium tokens (bg-surface, text-primary, accent-narrative) |

---

## Status

- [ ] ready-for-dev
- [ ] in-progress
- [ ] review
- [x] done
