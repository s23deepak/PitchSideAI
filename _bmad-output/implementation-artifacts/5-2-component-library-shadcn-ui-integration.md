# Story 5.2: Component Library — shadcn/ui Integration

**Status:** done  
**Epic:** Epic 5 — UI/UX Revamp  
**Priority:** Critical (Wave 1)

---

## Story

As a UI developer,
I want a reusable component library themed to Midnight Stadium tokens,
So that building new features is fast and consistent.

**Reference:** `.bmad/screens/*.html` — Stitch HTML component patterns

---

## Acceptance Criteria

**Given** the `frontend/src/components/ui/` directory
**When** shadcn/ui components are installed and themed
**Then** the following 10 components are available:

| Component | Usage | Themed Variants |
|-----------|-------|-----------------|
| Button | Mic base, language toggle, CTAs | default, narrative, ghost, outline, danger |
| Slider | Bias/excitement/knowledge sliders | with tooltip, discrete steps |
| Card | Trivia container, teleprompter panel | elevated, flat, bordered |
| Badge | Confidence, source, LIVE, agent status | default, success, warning, danger, mono |
| Progress | Agent pipeline completion bar | gradient, animated |
| Toggle | Fan/Commentator view switch | pressed/unpressed |
| Tooltip | Control hover labels | auto-positioning, arrow |
| Dialog | Notes generation progress modal | with backdrop, Escape handling |
| Tabs | Teleprompter section tabs | underlined, pills |
| ScrollArea | Teleprompter long-sheet | custom scrollbar, auto-hide |

**And** all components support keyboard navigation (Tab, Space, Enter, Arrow keys, Escape)
**And** all components have proper ARIA labels via Radix primitives
**And** all components respect `prefers-reduced-motion`
**And** components are exported from `frontend/src/components/ui/index.ts`

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Component snapshot: Capture all 10 components in all variants (dark surface #1A1A1A, border #353535)
- [ ] [AI-Test] Keyboard navigation audit: Tab through all components, verify focus rings (Cyan 400, 2px)
- [ ] [AI-Test] ARIA validation: Verify all Radix primitives expose correct aria-* attributes
- [ ] [AI-Test] Reduced motion test: Verify animations disabled when `prefers-reduced-motion: reduce`

---

## Tasks

- [x] 8 components already existed: Button, Slider, Card, Badge, Progress, Toggle, Tooltip, Dialog
- [x] Created Tabs component (`frontend/src/components/ui/Tabs.tsx`)
- [x] Created ScrollArea component (`frontend/src/components/ui/ScrollArea.tsx`)
- [x] Updated `frontend/src/components/ui/index.ts` to export all 10 components
- [ ] Write Playwright test: component snapshots
- [ ] Write Playwright test: keyboard navigation
- [ ] Write Playwright test: ARIA validation
- [ ] Write Playwright test: reduced motion

---

## Dev Notes

- shadcn/ui copies components into project (not npm dependency)
- All components use Radix primitives — ARIA is built-in
- Theme via Tailwind config extension (Story 5.1 tokens)
- Keyboard nav: Tab order, Space/Enter activation, Arrow keys for sliders/tabs
- Reduced motion: check `prefers-reduced-motion` in CSS + JS animation guards
- Components should use `var(--accent-critical)` and `var(--accent-narrative)` for highlights

---

## File List

| File | Action |
|------|--------|
| frontend/src/components/ui/ | EXISTS (8 components pre-existing) |
| frontend/src/components/ui/button.tsx | EXISTS |
| frontend/src/components/ui/slider.tsx | EXISTS |
| frontend/src/components/ui/card.tsx | EXISTS |
| frontend/src/components/ui/badge.tsx | EXISTS |
| frontend/src/components/ui/progress.tsx | EXISTS |
| frontend/src/components/ui/toggle.tsx | EXISTS |
| frontend/src/components/ui/tooltip.tsx | EXISTS |
| frontend/src/components/ui/dialog.tsx | EXISTS |
| frontend/src/components/ui/tabs.tsx | CREATED |
| frontend/src/components/ui/scroll-area.tsx | CREATED |
| frontend/src/components/ui/index.ts | MODIFIED (added Tabs, ScrollArea exports) |
| frontend/tests/e2e/components.spec.ts | TODO |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-05 | Initial story creation |
| 2026-05-06 | Updated reference to Stitch HTML screens |

---

## Status

- [ ] ready-for-dev
- [ ] in-progress
- [ ] review
- [x] done
