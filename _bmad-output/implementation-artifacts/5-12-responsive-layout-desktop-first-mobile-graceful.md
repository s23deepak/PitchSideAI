# Story 5.12: Responsive Layout — Desktop First, Mobile Graceful

**Status:** ready-for-dev  
**Epic:** Epic 5 — UI/UX Revamp  
**Priority:** High (Wave 4)

---

## Story

As a user accessing PitchAI on different devices,
I want the layout to adapt to my screen size,
So that I can use the product on desktop, tablet, or mobile.

**Reference:** All `.bmad/screens/*.html` files

---

## Acceptance Criteria

**Given** desktop viewport (≥ 1440px)
**When** rendering
**Then**:
- Full Fan Lens layout as designed
- Full Commentator Dashboard 60/40 split
- All controls visible

**Given** tablet viewport (1024px - 1439px)
**When** rendering
**Then**:
- Video maintains 16:9, scaled down
- ControlsTray condensed (icons only, tooltips on tap)
- Trivia cards max 240px wide
- Commentator Dashboard: video 100%, teleprompter below (stacked)

**Given** mobile viewport (< 1024px)
**When** rendering
**Then**:
- Video 100% width
- ControlsTray becomes bottom sheet (swipe up)
- Trivia cards full width at bottom
- Commentator Dashboard: video only, teleprompter accessible via "Show Notes" button
- MicButton repositioned to top-right (thumb-friendly)

**And** all touch targets minimum 44×44px (WCAG 2.1 touch target size)
**And** no horizontal scroll at any breakpoint
**And** `prefers-reduced-motion` respected at all breakpoints

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Desktop viewport (1440px): Verify full Fan Lens + Commentator Dashboard layouts
- [ ] [AI-Test] Tablet viewport (1024px): Verify condensed ControlsTray, stacked Commentator layout
- [ ] [AI-Test] Mobile viewport (<1024px): Verify bottom sheet ControlsTray, "Show Notes" button
- [ ] [AI-Test] Touch targets: Verify all interactive elements ≥44×44px at mobile breakpoint
- [ ] [AI-Test] Horizontal scroll: Test all breakpoints → verify no horizontal overflow

---

## Tasks

- [x] Created `frontend/src/layouts/FanLensLayout.tsx` with responsive breakpoints
- [x] Created `frontend/src/layouts/CommentatorLayout.tsx` with 60/40 split → stacked → mobile toggle
- [x] Integrated FanLensLayout into MatchDashboard (fan view)
- [x] Integrated CommentatorLayout into MatchDashboard (commentator view)
- [x] Fixed Vite config to resolve `@` alias for layouts import
- [ ] Audit touch targets → ensure ≥44×44px
- [ ] Write Playwright test: desktop viewport (1440px)
- [ ] Write Playwright test: tablet viewport (1024px)
- [ ] Write Playwright test: mobile viewport (<1024px)
- [ ] Write Playwright test: touch target audit
- [ ] Write Playwright test: horizontal scroll check

---

## Dev Notes

- Desktop-first approach: base styles for ≥1440px, use `max-width` media queries for smaller
- ControlsTray bottom sheet: use fixed positioning + transform translateY for slide-up
- Touch targets: add padding to small elements (icons, badges) to reach 44×44px minimum
- Horizontal scroll: use `overflow-x: hidden` on body, `max-width: 100%` on images/video
- Swipe-up gesture: optional enhancement, use touch events + CSS scroll snap

---

## File List

| File | Action |
|------|--------|
| frontend/src/layouts/FanLensLayout.tsx | CREATED |
| frontend/src/layouts/CommentatorLayout.tsx | CREATED |
| frontend/src/components/MatchDashboard.jsx | MODIFIED (integrated layouts) |
| frontend/vite.config.js | MODIFIED (added @ alias resolve) |
| frontend/src/components/ControlsTray.tsx | TODO (responsive modes) |
| frontend/src/components/MicButton.tsx | TODO (mobile position) |
| frontend/src/components/TriviaCard.tsx | TODO (responsive sizing) |
| frontend/src/index.css | UNCHANGED |
| frontend/tests/e2e/responsive.spec.ts | TODO |

---

## Change Log

| Date | Change |
|------|--------|
| | Initial story creation |

---

## Status

- [ ] ready-for-dev
- [x] in-progress
- [ ] review
- [ ] done

## Dev Agent Record

### Implementation Summary

**Date:** 2026-05-06

**Completed:**
1. Created `frontend/src/layouts/FanLensLayout.tsx` with responsive breakpoints:
   - Desktop (≥1440px): Full layout with trivia cards bottom-left, MicButton bottom-right
   - Tablet (1024px-1439px): Condensed trivia cards (max 240px)
   - Mobile (<1024px): Bottom sheet ControlsTray, full-width trivia, MicButton top-right

2. Created `frontend/src/layouts/CommentatorLayout.tsx` with responsive breakpoints:
   - Desktop (≥1440px): 60/40 split (video 60%, teleprompter 40%)
   - Tablet (1024px-1439px): Stacked layout (video top, teleprompter below)
   - Mobile (<1024px): Video only with "Show Notes" button toggle

3. Integrated layouts into `MatchDashboard.jsx`:
   - Fan view uses FanLensLayout
   - Commentator view uses CommentatorLayout
   - View toggle switches between layouts

4. Fixed Vite config to resolve `@` alias for imports

**Build Status:** ✅ Successful (1.27s)
**Dev Server:** ✅ Running on http://localhost:5173/

**Pending:**
- Touch target audit (≥44×44px)
- Playwright E2E tests for responsive breakpoints
- ControlsTray responsive modes (condensed for tablet, bottom sheet for mobile)
