# PitchAI Live Commentary Interface — UX Design Specification (Midnight Stadium)

**Version:** 3.0 | **Date:** May 2026 | **Stitch Project:** 15768476927893272015

---

## Executive Summary

This specification defines the **Midnight Stadium** design system for PitchAI's live commentary interface. The aesthetic is "**Bloomberg Terminal meets F1 telemetry**" — functional broadcast software, not decorative AI art.

**Key Principles:**
1. Function Over Decoration — Every visual element serves an informational purpose
2. Solid Surfaces — No glassmorphism, no backdrop-blur, no faux-depth effects
3. Monochrome Base — Deep obsidian (#131313) canvas with charcoal (#1A1A1A) differentiation
4. Functional Accent Colors — Electric Lime (#CCFF00) for critical states, Gold (#FFD700) for narrative highlights
5. Technical Typography — Space Grotesk for data/labels, Inter for body/narrative
6. 4px Grid — All spacing and radius based on 4px unit

---

## Reference Screens

**Stitch Project:** `15768476927893272015`

**Local HTML References:** `.bmad/screens/*.html`
| Screen | File | Purpose |
|--------|------|---------|
| Landing Page | `pitchai-landing-page.html` | Hero, features, CTA |
| Fan Lens | `fan-lens-broadcast.html` | Main broadcast dashboard |
| Q&A Overlay | `fan-ai-temporal-replay.html` | SplitScreen temporal replay |
| Commentator Dashboard | `commentator-dashboard.html` | Teleprompter with beat highlighting |
| Notes Hub | `notes-generation-hub.html` | Pre-match notes generation |

---

## Design Tokens

### Colors

```css
/* Surface Colors - SOLID, no effects */
--surface-primary: #131313;      /* Deep Obsidian */
--surface-secondary: #1A1A1A;    /* Charcoal */
--surface-hover: #20201F;
--surface-container: #2A2A2A;
--surface-border: #353535;       /* 1px solid borders */

/* Functional Accents */
--electric-lime: #CCFF00;        /* CRITICAL states only */
--electric-lime-dim: #ABD600;
--gold: #FFD700;                 /* NARRATIVE highlights only */
--crisp-white: #FFFFFF;

/* Text */
--text-primary: #E5E2E1;         /* AAA 7:1+ */
--text-secondary: #C4C9AC;       /* AA 4.5:1+ */
--text-muted: #8E9379;

/* Semantic */
--success: #10B981;
--warning: #F59E0B;
--danger: #EF4444;
```

### Typography

```css
/* Inter - Body/Narrative */
--font-inter: 'Inter', system-ui, sans-serif;
--text-display-xl: 48px/1.1 800 -0.02em;
--text-headline-lg: 32px/1.2 700;
--text-headline-md: 24px/1.2 700;
--text-body-lg: 18px/1.5 400;
--text-body-md: 16px/1.5 400;

/* Space Grotesk - Technical/Labels */
--font-space: 'Space Grotesk', monospace, sans-serif;
--text-label-caps: 12px/1 700 uppercase 0.1em;
--text-data-mono: 14px/1.4 500;
```

### Spacing & Radius

```css
/* 4px Grid */
--space-xs: 4px;
--space-sm: 8px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;

/* Small, Technical Radius */
--radius-sm: 4px;    /* buttons, chips */
--radius-md: 8px;    /* cards */
--radius-lg: 12px;   /* containers */
--radius-full: 9999px;
```

---

## Layout Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard Header (sticky, 60px)                            │
│  [← Back]  Home Team vs Away Team      [Prepare Notes]      │
├─────────────────────────────────────────────────────────────┤
│  Top Row (full width, auto-height)                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  VideoCanvas (16:9 aspect, tactical overlays)          │  │
│  │  + MicButton (48px floating, bottom-right)             │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Bottom Row (3 columns, 300px min-height)                   │
│  ┌─────────────┬─────────────┬─────────────┐               │
│  │ Commentary  │  Event Feed │ MatchInsight│               │
│  │  Feed       │             │ (Trivia/Q&A)│               │
│  └─────────────┴─────────────┴─────────────┘               │
├─────────────────────────────────────────────────────────────┤
│  Notes Container (full width, collapsible)                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Teleprompter (long-sheet) or CommentaryNotesViewer   │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ControlsTray (fixed bottom, auto-hide after 3s idle)       │
│  [EN|ES] [Bias slider] [Excitement] [Knowledge] [View toggle]│
└─────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### MicButton (48px Floating Q&A)

| State | Border | Animation |
|-------|--------|-----------|
| Idle | #353535 | None |
| Hover | #CCFF00 | Border brightens |
| Recording | #EF4444 | Pulse |
| Confirmation | #CCFF00 | Transcript popover |
| Processing | #CCFF00 | Rotating ring |
| Disabled | #353535 (50% opacity) | None |

**Background:** Always #1A1A1A (solid)  
**Position:** 16px from bottom-right of VideoCanvas  
**Interaction:** Hold-to-talk (Space key)

---

### ControlsTray

- **Position:** Fixed bottom, 56px height
- **Background:** #1A1A1A solid with 1px #353535 top border
- **Auto-hide:** 3s idle (desktop), always visible (touch)
- **Controls:** Language toggle, Bias slider (-1 to +1), Excitement (0-1), Knowledge (0-1), View toggle

---

### Teleprompter Beat Highlighting

| Element | Style |
|---------|-------|
| Current beat | 15% Electric Lime bg, 3px left border, ▶ marker |
| Next 3 beats | Opacity 0.7 → 0.6 → 0.5 |
| Auto-scroll | Keep current at 30% from top, 300ms ease |
| Confidence gate | Skip if < 0.7 |

---

### TriviaCard

- **Display duration:** 5s if confidence ≥ 0.8, else 3s
- **Animation:** Fade in/out 300ms (opacity only, no scale/slide)
- **Background:** #1A1A1A solid, 1px #353535 border, 8px radius

---

## Forbidden Patterns (AI-Generated Look)

❌ `backdrop-filter: blur()` — No glassmorphism  
❌ `box-shadow` for glow effects  
❌ Breathing/pulsing border animations  
❌ Gradient backgrounds  
❌ Border radius > 12px (except full)  
❌ "AI blue" or "tech purple" colors  
❌ Decorative elements without function

---

## Approved Patterns (Broadcast Software)

✅ Solid color surfaces only  
✅ 1px solid borders (#353535 or Electric Lime for active)  
✅ Small radius (4-8px base)  
✅ Technical typography (Space Grotesk for labels)  
✅ Functional color usage (Lime = critical, Gold = highlight)  
✅ Dense information layout  
✅ Monochrome base with selective accent

---

## Acceptance Criteria

### Visual

- [ ] All surfaces are solid colors (no backdrop-blur)
- [ ] All borders are 1px solid #353535
- [ ] Electric Lime ONLY for critical states (Live, recording, active AI)
- [ ] Gold ONLY for narrative highlights (milestones, premium stats)
- [ ] Space Grotesk for all technical labels
- [ ] 4px base radius (small, technical)

### Accessibility

- [ ] AAA contrast ratios (7:1+ primary text, 4.5:1+ secondary)
- [ ] Keyboard navigation (Tab, Enter, Space, Arrows, Escape)
- [ ] prefers-reduced-motion supported (opacity transitions only)
- [ ] Focus indicators visible (Electric Lime outline)

### Functional

- [ ] ControlsTray auto-hides after 3s idle (desktop)
- [ ] MicButton has all 6 states implemented
- [ ] Teleprompter beat highlighting respects 0.7 confidence threshold
- [ ] TriviaCard display duration varies by confidence (5s/3s)
- [ ] WebSocket reconnection handled gracefully

---

## Implementation Notes

**All UI components MUST be built based on the reference HTML files in `.bmad/screens/`.** Open these files in a browser to see the exact visual design. Do not guess colors, spacing, or layouts — copy them exactly from the reference.

**Stitch Project Reference:** `15768476927893272015`  
**Design System:** Midnight Stadium  
**Key Screens:**
- `0e1249c7...` — Fan Lens - Broadcast Pro
- `7b7bc848...` — Fan AI Temporal Replay
- `bb2a756d...` — Refined Commentator Dashboard
- `bcd8df1f...` — Notes Generation Hub
- `0dd1f12f...` — PitchAI Landing Page
