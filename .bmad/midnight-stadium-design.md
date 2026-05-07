# Midnight Stadium Design System

**For:** PitchAI Live Commentary Interface  
**Stitch Project:** 15768476927893272015  
**Version:** 3.0  
**Date:** May 2026

---

## Quick Reference

### Colors

```
SURFACE COLORS
┌─────────────────────────────────────┐
│ #131313  Surface Primary (bg)       │
│ #1A1A1A  Surface Secondary (cards)  │
│ #20201F  Surface Hover               │
│ #2A2A2A  Surface Container           │
│ #353535  Surface Border (1px)        │
└─────────────────────────────────────┘

FUNCTIONAL ACCENTS
┌─────────────────────────────────────┐
│ #CCFF00  Electric Lime (CRITICAL)   │
│ #FFD700  Gold (NARRATIVE)           │
│ #FFFFFF  Crisp White (DATA)         │
└─────────────────────────────────────┘
```

### Color Usage Rules

| Use This | For This | Never For |
|----------|----------|-----------|
| Electric Lime | Live badge, recording, AI active borders | Body text, decoration |
| Gold | Key highlights, milestones, premium stats | Interactive states |
| White | Dense data, headings | Muted info |

### Typography

```
Inter (Body/Narrative)
├── 48px/800  Display XL (headers)
├── 32px/700  Headline LG
├── 24px/700  Headline MD
├── 18px/400  Body LG
└── 16px/400  Body MD

Space Grotesk (Technical/Labels)
├── 12px/700  Label Caps (uppercase, 0.1em spacing)
└── 14px/500  Data Mono (coordinates, timestamps)
```

### Spacing & Radius

```
Spacing (4px grid)
├── 4px   xs
├── 8px   sm
├── 16px  md (gutter)
├── 24px  lg (margin)
└── 32px  xl

Radius
├── 4px   sm (buttons, chips)
├── 8px   md (cards)
├── 12px  lg (containers)
└── 9999px full (pills, toggles)
```

---

## Design Philosophy

### What This Is

- **Bloomberg Terminal meets F1 telemetry** — functional, dense, professional
- **Broadcast software aesthetic** — every element serves a purpose
- **Technical and precise** — Space Grotesk for data, solid surfaces
- **High contrast** — AAA accessibility, critical states pop

### What This Is NOT

- ❌ Not glassmorphism / frosted glass
- ❌ Not glow effects or drop shadows
- ❌ Not breathing/pulsing animations
- ❌ Not gradient backgrounds
- ❌ Not "AI blue" or "tech purple"
- ❌ Not playful with large rounded corners

---

## Component Quick Specs

### MicButton (48px floating)

```
States:
┌─────────────┬──────────────┬─────────────────────┐
│ State       │ Border       │ Animation           │
├─────────────┼──────────────┼─────────────────────┤
│ Idle        │ #353535      │ None                │
│ Hover       │ #CCFF00      │ Border brightens    │
│ Recording   │ #EF4444      │ Pulse               │
│ Confirmation│ #CCFF00      │ Transcript popover  │
│ Processing  │ #CCFF00      │ Rotating ring       │
│ Disabled    │ #353535 50%  │ None                │
└─────────────┴──────────────┴─────────────────────┘

Background: Always #1A1A1A (solid)
Shape: Circle, 48px
Position: Bottom-right of VideoCanvas
```

### ControlsTray

```
Position: Fixed bottom
Height: 56px
Background: #1A1A1A solid
Border: 1px solid #353535 (top)
Behavior: Auto-hide after 3s idle (desktop)
          Always visible (touch)
Contents: [Language] [Bias±] [Excitement 0-1] [Knowledge 0-1] [View toggle]
```

### Teleprompter Beat Highlighting

```
Current Beat:
├── Background: 15% Electric Lime
├── Left border: 3px solid #CCFF00
├── Marker: ▶ (Space Grotesk)
└── Position: Auto-scroll to 30% from top

Next 3 Beats:
├── Opacity: 0.7 → 0.6 → 0.5
└── No background

Confidence Gate: Skip if < 0.7
```

### TriviaCard

```
Display Duration:
├── 5s if confidence ≥ 0.8
└── 3s if confidence < 0.8

Animation:
├── Fade in: 300ms opacity
├── Fade out: 300ms opacity
└── NO scale, NO slide

Background: #1A1A1A solid
Border: 1px solid #353535
Radius: 8px
```

---

## Interaction Patterns

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Hold-to-talk (MicButton) |
| ←/→ | Bias slider |
| ↑/↓ | Excitement/Knowledge sliders |
| Escape | Cancel/dismiss |
| Tab | Cycle focus |

### Auto-Dismiss

| Element | Duration |
|---------|----------|
| TriviaCard | 3-5s (confidence-based) |
| SplitScreen | 8s |
| ControlsTray | 3s idle (desktop) |
| Tooltips | Persist after first hover |

---

## Implementation Checklist

### Required

- [ ] All surfaces are solid colors (no backdrop-blur)
- [ ] All borders are 1px solid #353535
- [ ] Electric Lime ONLY for critical states
- [ ] Gold ONLY for narrative highlights
- [ ] Space Grotesk for all technical labels
- [ ] 4px base radius (small, technical)
- [ ] AAA contrast ratios (7:1+ primary, 4.5:1+ secondary)

### Forbidden

- [ ] backdrop-filter: blur()
- [ ] box-shadow for glow
- [ ] Gradient backgrounds
- [ ] Breathing/pulsing borders
- [ ] Radius > 12px (except full)
- [ ] Decorative elements

---

## Local References

Saved Stitch screens:

```
.bmad/screens/
├── pitchai-landing-page.html    (landing page)
├── fan-lens-broadcast.html      (main view)
├── fan-ai-temporal-replay.html  (Q&A overlay)
├── commentator-dashboard.html   (teleprompter)
└── notes-generation-hub.html    (notes interface)
```

---

## Stitch Project Access

**Project ID:** `15768476927893272015`  
**Title:** PRD Reference Web Design  
**Design System:** Midnight Stadium

**Key Screens:**

| Screen ID | Title |
|-----------|-------|
| `0e1249c7...` | Fan Lens - Broadcast Pro |
| `7b7bc848...` | Fan AI Temporal Replay |
| `bb2a756d...` | Refined Commentator Dashboard |
| `bcd8df1f...` | Notes Generation Hub |

---

## Why This Design Works

1. **Functional First** — Every visual element communicates state or data
2. **Accessible** — AAA contrast, clear interactive states
3. **Professional** — Broadcast software aesthetic, not consumer app
4. **Performant** — Solid colors paint faster than glassmorphism
5. **Scalable** — 4px grid system easy to maintain
6. **Distinctive** — Electric Lime sets it apart from generic "dark mode"
