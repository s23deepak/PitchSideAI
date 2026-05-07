# PitchAI Live Commentary Interface — UX Design Specification

**Version:** 3.0 (Midnight Stadium) | **Date:** May 2026 | **Stitch Project:** 15768476927893272015

---

## A. Design Philosophy

### Midnight Stadium Aesthetic

**Brand Personality:** Intelligent, Energetic, Premium

**Visual Inspiration:** Bloomberg Terminal meets F1 telemetry — functional broadcast software, not decorative AI art.

**Key Principles:**

1. **Function Over Decoration** — Every visual element serves an informational purpose
2. **Solid Surfaces** — No glassmorphism, no backdrop-blur, no faux-depth effects
3. **Monochrome Base** — Deep obsidian canvas with charcoal differentiation
4. **Functional Accent Colors** — Electric Lime for critical states, Gold for narrative highlights
5. **Technical Typography** — Space Grotesk for data/labels, Inter for body/narrative
6. **4px Grid** — All spacing and radius based on 4px unit

---

## B. Layout Structure

### Overall Page Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard Header (sticky, 60px)                            │
│  [← Back]  Home Team vs Away Team      [Prepare Notes]      │
├─────────────────────────────────────────────────────────────┤
│  Top Row (full width, auto-height)                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  PushToTalk (compact, 56px circular button + transcript)│  │
│  ├───────────────────────────────────────────────────────┤  │
│  │  VideoCanvas (16:9 aspect, tactical overlays)          │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │  MicButton (48px floating, bottom-right)               │  │
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

### Responsive Breakpoints

- **Desktop (>1024px):** 3-column bottom row, full teleprompter
- **Tablet (768-1024px):** 2-column bottom row, stacked panels
- **Mobile (<768px):** Single column, ControlsTray always visible

---

## C. Visual Design System

### Color Tokens (Midnight Stadium — Dark Theme)

```css
/* Surface Colors — Solid, light-absorbing */
--surface-primary: #131313;      /* Deep Obsidian — main canvas */
--surface-secondary: #1A1A1A;    /* Charcoal — containers */
--surface-hover: #20201F;        /* Container hover state */
--surface-container: #2A2A2A;    /* Elevated panels */
--surface-border: #353535;       /* 1px solid borders */

/* Functional Accent Colors */
--electric-lime: #CCFF00;        /* CRITICAL: Vision, active states, Live badge */
--electric-lime-dim: #ABD600;    /* Secondary lime state */
--gold: #FFD700;                 /* NARRATIVE: Highlights, milestones, premium stats */
--crisp-white: #FFFFFF;          /* Maximum legibility text/data */

/* Text Colors */
--text-primary: #E5E2E1;         /* AAA 7:1+ contrast */
--text-secondary: #C4C9AC;       /* AA 4.5:1+ contrast */
--text-muted: #8E9379;           /* Tertiary info */

/* Semantic Colors */
--success: #10B981;              /* Emerald — success states */
--warning: #F59E0B;              /* Amber — warnings */
--danger: #EF4444;               /* Red — errors, disconnected */
```

### Color Usage Rules

| Color | Usage | Never Use For |
|-------|-------|---------------|
| Electric Lime (#CCFF00) | Live badge, recording state, AI detection borders, active buttons | Body text, decorative elements |
| Gold (#FFD700) | Key highlights, legendary stats, narrative moments | Interactive states, borders |
| Crisp White | Dense data, headings, primary text | Muted information |
| Surface Border (#353535) | All component borders | Accent elements |

### Typography

**Font Families:**

- **Inter** — Body text, narrative content, general UI (15px base)
- **Space Grotesk** — Technical labels, data points, timestamps, coordinates

**Type Scale:**

```css
/* Display — Match headers, hero stats */
--display-xl: 48px/800/-0.02em;  /* Inter ExtraBold */

/* Headlines — Section titles */
--headline-lg: 32px/700/1.2;     /* Inter Bold */
--headline-md: 24px/700/1.2;     /* Inter Bold */

/* Body — Commentary, descriptions */
--body-lg: 18px/400/1.5;         /* Inter Regular */
--body-md: 16px/400/1.5;         /* Inter Regular */

/* Labels — Technical data, badges */
--label-caps: 12px/700/0.1em;    /* Space Grotesk Bold, uppercase */
--data-mono: 14px/500/1.4;       /* Space Grotesk Medium */
```

### Spacing Scale (4px Unit)

```css
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 16px;
--spacing-lg: 24px;
--spacing-xl: 32px;
--spacing-gutter: 16px;
--spacing-margin: 24px;
```

### Border Radius (4px Base)

```css
--radius-sm: 4px;    /* Buttons, chips, small elements */
--radius-md: 8px;    /* Cards, panels */
--radius-lg: 12px;   /* Large containers */
--radius-full: 9999px; /* Pills, toggles */
```

**Rule:** All radius values are small (0.25rem base). No large rounded corners — this is technical, not playful.

### Shadows & Elevation

**No drop shadows.** Elevation is conveyed through:

1. **Surface brightness** — Lighter surfaces appear elevated
2. **1px solid borders** — #353535 defines edges sharply
3. **Active illumination** — Electric Lime inner stroke for AI-active elements

```css
/* Border treatment */
border: 1px solid var(--surface-border);

/* Active AI element */
border: 1px solid var(--electric-lime);
```

---

## D. Component Inventory

| Component | File | Purpose | Key Props |
|-----------|------|---------|-----------|
| **MatchDashboard** | `MatchDashboard.jsx` | Main container, state orchestration | homeTeam, awayTeam, commentaryData, liveCommentary |
| **VideoCanvas** | `VideoCanvas.jsx` | Fan Lens video player with SVG tactical overlays | matchSession, onTacticalDetection, onCommentary |
| **PushToTalk** | `PushToTalk.jsx` | Voice input for match events | matchReady, onEventSubmit |
| **MicButton** | `MicButton.jsx` | Floating Q&A button (hold-to-talk) | onQuestionSubmit, isAiReady, isSplitScreenActive |
| **CommentaryFeed** | `CommentaryFeed.jsx` | Live commentary stream (Peter Drury-style) | messages, sendMatchEvent |
| **EventFeed** | `EventFeed.jsx` | Match events timeline (goals, cards, subs) | matchSession |
| **MatchInsight** | `MatchInsight.jsx` | Trivia cards, Q&A history | matchSession, initialTrivia |
| **Teleprompter** | `Teleprompter.jsx` | Commentator view with beat highlighting | notesData, liveDetection, onBeatChange |
| **CommentaryNotesViewer** | `CommentaryNotesViewer.jsx` | Fan view of pre-match notes | data, liveDetection |
| **ControlsTray** | `ControlsTray.jsx` | Settings bar (language, bias, excitement, knowledge) | homeTeam, awayTeam, onSettingsChange, onLanguageChange |
| **SplitScreen** | `SplitScreen.jsx` | Temporal navigation overlay for Q&A | answer, isActive, onDismiss |
| **TriviaCard** | `TriviaCard.jsx` | Animated trivia popups | text, source, confidence, displayDurationMs |

---

## E. Component Specifications

### ControlsTray Behavior

- **Auto-hide:** After 3s idle on desktop; always visible on touch devices
- **Hover reveal:** Slide up from bottom with 300ms ease
- **Tooltips:** Show once per control on first hover, persist to localStorage
- **Background:** Solid #1A1A1A with 1px #353535 top border

### Slider Interactions

| Slider | Range | Step | Labels | Track Color |
|--------|-------|------|--------|-------------|
| Bias | -1 to +1 | 0.01 | `{homeTeam.slice(0,3)}` ← → `{awayTeam.slice(0,3)}` | Lime gradient |
| Excitement | 0 to 1 | 0.01 | Calm ← → Hype | Lime gradient |
| Knowledge | 0 to 1 | 0.01 | Basic ← → Tactical | Gold gradient |

### MicButton States

| State | Background | Border | Animation |
|-------|------------|--------|-----------|
| Idle | #1A1A1A | #353535 | None |
| Hover | #1A1A1A | #CCFF00 | Border glow |
| Recording | #1A1A1A | #EF4444 | Pulse animation |
| Confirmation | #1A1A1A | #CCFF00 | Transcript popover |
| Processing | #1A1A1A | #CCFF00 | Rotating gradient ring |
| Disabled | #1A1A1A at 50% | #353535 | None |

**NO progress arc animation** — use simple pulse or rotating border instead.

### Teleprompter Beat Highlighting (Story 3.2)

- **Current beat:** Electric Lime background at 15%, 3px left border, ▶ marker
- **Next 3 beats:** Opacity 0.7 → 0.6 → 0.5 (data-offset attribute)
- **Previous beat:** Opacity 0.5
- **Auto-scroll:** Smooth 300ms animation to keep current at 30% from top
- **Hold mode:** Manual scroll during auto-scroll pauses; "Back to live" button appears
- **Background:** Solid #1A1A1A, NO glassmorphism

### VideoCanvas Overlays

- **Player dots:** Team-colored circles (home/away primary colors)
- **Ball marker:** Electric Lime circle with 1px border
- **Tactical label badge:** Solid #1A1A1A background, #353535 border, Space Grotesk label
- **Connection state:** Top-right corner, solid badge (Green/Amber/Red)

---

## F. State Indicators

### Live Badge

- **Connected:** Electric Lime circle, "LIVE" label in Space Grotesk, solid fill
- **Reconnecting:** Gold circle, "Reconnecting..." label
- **Disconnected:** Red circle, "Disconnected" label

### Loading States

- **Notes generation:** Progress bar (60% → 90%), agent status text in Space Grotesk
- **AI warming up:** MicButton disabled with tooltip "~20s ready"

### Error States

| Error | Trigger | UI Treatment |
|-------|---------|--------------|
| Permission denied | `NotAllowedError` | Red toast: "Microphone permission denied" |
| No speech | `NoSpeech` | Retry message in confirmation popover |
| Context overflow | LLM error | Graceful fallback to sampled frames |
| WebSocket fail | `onerror` | Connection indicator → disconnected |

### Confidence Gating

- **Trivia cards:** Display 5s if confidence ≥ 0.8, else 3s
- **Beat highlighting:** Skip if confidence < 0.7
- **Q&A auto-submit:** Confidence ≥ 0.9 skips confirmation; 0.7-0.9 shows 1s confirmation

---

## G. WebSocket Event Types (from `/ws/live`)

| Event Type | Payload | Client Action |
|------------|---------|---------------|
| `ready` | `{match_session, has_notes_store, qa_enhanced}` | Enable controls, show "Session ready" |
| `commentary` | `{text, source, gameState, beat_indices}` | Push to CommentaryFeed, highlight Teleprompter beat |
| `beat_highlight` | `{beatIndex, confidence, nextIndices}` | Auto-scroll Teleprompter, apply highlighting |
| `trivia_card` | `{text, source, confidence, display_duration_ms}` | Animate TriviaCard with confidence-based timing |
| `answer` | `{text, gameState, player_identification, overlay_coordinates}` | Trigger SplitScreen, render SVG overlay |
| `language_confirmed` | `{language}` | Update ControlsTray toggle |

---

## H. Interaction Patterns

### Keyboard Navigation

| Key | Action |
|-----|--------|
| Space | MicButton hold-to-talk |
| Arrow Left/Right | Bias slider adjustment |
| Arrow Up/Down | Excitement/Knowledge sliders |
| Escape | Cancel recording, close overlays |
| Tab | Cycle through interactive elements |

### Auto-Dismiss Timings

- **Trivia cards:** 3-5s based on confidence
- **SplitScreen overlay:** 8s auto-dismiss
- **Tooltips:** Persist after first hover (localStorage)
- **ControlsTray:** 3s idle before auto-hide (desktop only)

### Animation Guidelines

**DO NOT USE:**

- `backdrop-filter: blur()`
- `box-shadow` for glow effects
- `breathing` or `pulse` animations on borders
- Gradient backgrounds
- `transition` on decorative elements

**USE ONLY:**

- `opacity` transitions (300ms ease)
- `transform` for position changes
- `border-color` transitions for state changes
- Simple rotation for loading states

```css
/* Example: Trivia card fade */
.trivia-card {
  transition: opacity 300ms ease, transform 300ms ease;
}

/* Example: Active state */
.button-active {
  border-color: var(--electric-lime);
  background-color: var(--surface-hover);
}
```

---

## I. Design Rules — What To Avoid

### Anti-Patterns (AI-Generated Look)

- ❌ Glassmorphism / backdrop-blur
- ❌ Glow effects and drop shadows
- ❌ Breathing/pulsing animations
- ❌ Gradient backgrounds
- ❌ Large border-radius (>12px)
- ❌ Decorative elements without function
- ❌ "AI blue" or "tech purple" colors

### Approved Patterns (Broadcast Software)

- ✅ Solid color surfaces
- ✅ 1px solid borders
- ✅ Small radius (4-8px)
- ✅ Technical typography (Space Grotesk)
- ✅ Functional color usage (Lime = critical, Gold = highlight)
- ✅ Dense information layout
- ✅ Monochrome base with selective accent

---

## J. File Structure (for Implementation)

```
src/
├── components/
│   ├── ui/                    # Primitives (Button, Slider, Badge, Card)
│   │   ├── Button.tsx
│   │   ├── Slider.tsx
│   │   ├── Badge.tsx
│   │   └── Card.tsx
│   ├── VideoCanvas.tsx
│   ├── MicButton.tsx
│   ├── Teleprompter.tsx
│   ├── ControlsTray.tsx
│   ├── TriviaCard.tsx
│   ├── SplitScreen.tsx
│   ├── CommentaryFeed.tsx
│   ├── EventFeed.tsx
│   └── MatchInsight.tsx
├── hooks/
│   ├── useWebSocket.ts
│   ├── useBeatHighlight.ts
│   └── useSpeechRecognition.ts
├── lib/
│   ├── constants.ts           # Design tokens, color maps
│   └── utils.ts               # CN, formatting helpers
└── styles/
    └── globals.css            # CSS custom properties, animations
```

---

## K. Local Screen References

Saved Stitch screens for implementation reference:

| Screen | File | Description |
|--------|------|-------------|
| Fan Lens - Broadcast Pro | `.bmad/screens/fan-lens-broadcast.html` | Main live commentary view |
| Fan AI Temporal Replay | `.bmad/screens/fan-ai-temporal-replay.html` | Q&A split-screen overlay |
| Commentator Dashboard | `.bmad/screens/commentator-dashboard.html` | Teleprompter + notes view |
| Notes Generation Hub | `.bmad/screens/notes-generation-hub.html` | Pre-match notes interface |

---

## L. Acceptance Criteria

- [x] ControlsTray auto-hides on desktop after 3s idle, remains visible on touch
- [x] MicButton uses solid colors, no glassmorphism or glow effects
- [x] Teleprompter beat highlighting respects 0.7 confidence threshold
- [x] TriviaCard display duration varies by confidence (5s/3s)
- [x] All interactive elements have AAA contrast ratios
- [x] prefers-reduced-motion disables all animations except opacity transitions
- [x] WebSocket reconnection handled gracefully with state indicator
- [x] Keyboard navigation works for all controls (Tab, Enter, Space, Arrows, Escape)
- [x] NO backdrop-blur, NO glow effects, NO gradient backgrounds
- [x] Electric Lime used ONLY for critical states (Live, recording, active)
- [x] Gold used ONLY for narrative highlights (milestones, premium stats)
- [x] All borders are 1px solid #353535 (or Electric Lime for active AI)
- [x] All radius values are 4px base (small, technical)

---

## M. Stitch Project Reference

**Project ID:** `15768476927893272015`

**Design System:** Midnight Stadium

**Key Screens:**

- `0e1249c7972243869bbf480b2e4438d5` — Fan Lens - Broadcast Pro (main view)
- `7b7bc8487ca846928eb84f09aca47743` — Fan AI Temporal Replay (Q&A overlay)
- `bb2a756d425849f29403121aa5b8a083` — Refined Commentator Dashboard
- `bcd8df1f96e245d5b8b6612dc9c54db8` — Notes Generation Hub

**Design Theme Config:**

```yaml
colorMode: DARK
customColor: "#CCFF00"
overridePrimaryColor: "#CCFF00"
overrideSecondaryColor: "#FFD700"
overrideNeutralColor: "#1A1A1A"
roundness: ROUND_FOUR  # 4px base
bodyFont: INTER
headlineFont: INTER
labelFont: SPACE_GROTESK
```
