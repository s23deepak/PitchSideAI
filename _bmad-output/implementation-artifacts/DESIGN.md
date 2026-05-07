# PitchAI UI Implementation Guide

**Design System:** Midnight Stadium  
**Reference:** Stitch Project `15768476927893272015`  
**Local Screens:** `.bmad/screens/*.html`

---

## Implementation Requirement

**All UI components MUST be built based on the reference HTML files in `.bmad/screens/`.** These are the authoritative visual specifications exported from Google Stitch.

### Reference Files

| File | Component | Use For |
|------|-----------|---------|
| `.bmad/screens/pitchai-landing-page.html` | Landing Page | Hero section, feature showcase, CTA |
| `.bmad/screens/fan-lens-broadcast.html` | Fan Lens View | Main broadcast layout, VideoCanvas, 3-column grid |
| `.bmad/screens/fan-ai-temporal-replay.html` | Q&A Overlay | SplitScreen temporal navigation, answer display |
| `.bmad/screens/commentator-dashboard.html` | Commentator View | Teleprompter with beat highlighting, notes panel |
| `.bmad/screens/notes-generation-hub.html` | Notes Interface | Pre-match notes generation UI |

**Open these HTML files in a browser to see the exact visual design.** Do not guess colors, spacing, or layouts — copy them exactly from the reference.

---

## Design Tokens

### Colors (CSS Custom Properties)

```css
:root {
  /* Surface Colors - SOLID, no effects */
  --surface-primary: #131313;
  --surface-secondary: #1A1A1A;
  --surface-hover: #20201F;
  --surface-container: #2A2A2A;
  --surface-border: #353535;

  /* Functional Accents */
  --electric-lime: #CCFF00;
  --electric-lime-dim: #ABD600;
  --gold: #FFD700;
  --crisp-white: #FFFFFF;

  /* Text */
  --text-primary: #E5E2E1;
  --text-secondary: #C4C9AC;
  --text-muted: #8E9379;

  /* Semantic */
  --success: #10B981;
  --warning: #F59E0B;
  --danger: #EF4444;
}
```

### Typography

```css
/* Import fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&family=Space+Grotesk:wght@500;700&display=swap');

/* Font families */
--font-inter: 'Inter', system-ui, sans-serif;
--font-space: 'Space Grotesk', monospace, sans-serif;

/* Type scale */
--text-display-xl: 48px/1.1 Inter Bold (800), -0.02em tracking;
--text-headline-lg: 32px/1.2 Inter Bold (700);
--text-headline-md: 24px/1.2 Inter Bold (700);
--text-body-lg: 18px/1.5 Inter Regular (400);
--text-body-md: 16px/1.5 Inter Regular (400);
--text-label-caps: 12px/1 Space Grotesk Bold (700), uppercase, 0.1em tracking;
--text-data-mono: 14px/1.4 Space Grotesk Medium (500);
```

### Spacing (4px Grid)

```css
--space-xs: 4px;
--space-sm: 8px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;
```

### Border Radius

```css
--radius-sm: 4px;    /* buttons, chips */
--radius-md: 8px;    /* cards */
--radius-lg: 12px;   /* containers */
--radius-full: 9999px;
```

---

## Component Specifications

### Landing Page

**Structure:**
```html
<main class="landing-page">
  <!-- Hero Section -->
  <section class="hero">
    <h1>PitchAI</h1>
    <p class="tagline">AI-powered live sports commentary</p>
    <button class="cta-primary">Start Commentary</button>
    <button class="cta-secondary">Learn More</button>
  </section>

  <!-- Features Section -->
  <section class="features">
    <!-- Feature cards with icons -->
  </section>

  <!-- Demo Section -->
  <section class="demo">
    <!-- Embedded preview or video -->
  </section>
</main>
```

**Styling:**
- Background: `#131313` (solid)
- Hero headline: 48px Inter ExtraBold, white
- Tagline: 24px Inter Bold, text-secondary color
- CTA Primary: Electric Lime bg, black text, 4px radius
- CTA Secondary: Transparent bg, Electric Lime border
- Feature cards: `#1A1A1A` bg, 1px solid border

**See:** `pitchai-landing-page.html` for exact layout

---

### MatchDashboard (Main Container)

**Layout:**
```
┌────────────────────────────────────────────┐
│ Header (sticky, 60px)                      │
├────────────────────────────────────────────┤
│ VideoCanvas (16:9 aspect)                  │
│ + PushToTalk                               │
│ + MicButton (floating bottom-right)        │
├────────────────────────────────────────────┤
│ 3-Column Grid (300px min-height each)      │
│ [CommentaryFeed][EventFeed][MatchInsight] │
├────────────────────────────────────────────┤
│ Notes Panel (collapsible)                  │
├────────────────────────────────────────────┤
│ ControlsTray (fixed bottom, auto-hide)     │
└────────────────────────────────────────────┤
```

**See:** `fan-lens-broadcast.html` for exact layout

---

### VideoCanvas

**Structure:**
```html
<div class="video-canvas">
  <video /> <!-- 16:9 aspect -->
  <svg class="tactical-overlay">
    <!-- Player dots (team colors) -->
    <!-- Ball marker (Electric Lime) -->
    <!-- Label badges (Space Grotesk) -->
  </svg>
  <div class="connection-badge">
    <!-- Live/Reconnecting/Disconnected -->
  </div>
</div>
```

**Styling:**
- Background: `#131313`
- Border: `1px solid #353535`
- Radius: `8px`
- Tactical label: Solid `#1A1A1A` bg, Space Grotesk text

**See:** `fan-lens-broadcast.html` for overlay positioning

---

### MicButton (48px Floating)

**States:**

```css
.mic-button {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #1A1A1A;
  border: 1px solid #353535;
  position: absolute;
  bottom: 16px;
  right: 16px;
}

/* Idle */
.mic-button--idle { }

/* Hover */
.mic-button--hover {
  border-color: #CCFF00;
}

/* Recording */
.mic-button--recording {
  border-color: #EF4444;
  animation: pulse 1.5s infinite;
}

/* Confirmation */
.mic-button--confirmation {
  border-color: #CCFF00;
}

/* Processing */
.mic-button--processing {
  border: 2px solid #CCFF00;
  animation: rotate 1s linear infinite;
}

/* Disabled */
.mic-button--disabled {
  opacity: 0.5;
}
```

**Interaction:** Hold-to-talk (Space key)

**See:** `fan-lens-broadcast.html` for exact positioning

---

### ControlsTray

**Structure:**
```html
<div class="controls-tray">
  <!-- Language Toggle: EN | ES -->
  <button class="lang-toggle">EN</button>
  
  <!-- Bias Slider: -1 to +1 -->
  <div class="slider">
    <label>{homeTeam[0:3]}</label>
    <input type="range" min="-1" max="1" step="0.01" />
    <label>{awayTeam[0:3]}</label>
  </div>
  
  <!-- Excitement Slider: 0 to 1 -->
  <div class="slider">
    <label>Calm</label>
    <input type="range" min="0" max="1" step="0.01" />
    <label>Hype</label>
  </div>
  
  <!-- Knowledge Slider: 0 to 1 -->
  <div class="slider">
    <label>Basic</label>
    <input type="range" min="0" max="1" step="0.01" />
    <label>Tactical</label>
  </div>
  
  <!-- View Toggle -->
  <button class="view-toggle">Fan Lens</button>
</div>
```

**Styling:**
- Position: `fixed bottom-0 left-0 right-0`
- Height: `56px`
- Background: `#1A1A1A` solid
- Border-top: `1px solid #353535`
- Auto-hide: 3s idle (desktop), always visible (touch)

**See:** `fan-lens-broadcast.html` for slider styling

---

### Teleprompter

**Structure:**
```html
<div class="teleprompter">
  <div class="tabs">
    <!-- 5 section tabs -->
  </div>
  <div class="content">
    <div class="beat beat--current">
      <span class="marker">▶</span>
      Current beat text...
    </div>
    <div class="beat beat--next" data-offset="1">
      Next beat...
    </div>
  </div>
  <button class="back-to-live">Back to live</button>
</div>
```

**Beat Highlighting:**
```css
.beat--current {
  background: rgba(204, 255, 0, 0.15);
  border-left: 3px solid #CCFF00;
  opacity: 1;
}

.beat--next[data-offset="1"] { opacity: 0.7; }
.beat--next[data-offset="2"] { opacity: 0.6; }
.beat--next[data-offset="3"] { opacity: 0.5; }
```

**Auto-scroll:** Keep current beat at 30% from top, 300ms ease

**See:** `commentator-dashboard.html` for exact layout

---

### TriviaCard

**Structure:**
```html
<div class="trivia-card" data-confidence="0.85">
  <div class="content">
    <p class="text">Trivia question or insight...</p>
    <span class="source">Source name</span>
  </div>
  <div class="confidence-indicator">
    <!-- Visual confidence display -->
  </div>
</div>
```

**Styling:**
- Background: `#1A1A1A` solid
- Border: `1px solid #353535`
- Radius: `8px`
- Padding: `16px`
- Display duration: 5s (≥0.8), 3s (<0.8)

**Animation:**
```css
.trivia-card {
  animation: fadeIn 300ms ease, fadeOut 300ms ease;
  animation-fill-mode: forwards;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes fadeOut {
  from { opacity: 1; }
  to { opacity: 0; }
}
```

**See:** `fan-lens-broadcast.html` for card styling

---

### SplitScreen (Q&A Overlay)

**Structure:**
```html
<div class="split-screen-overlay">
  <div class="overlay-content">
    <div class="video-section">
      <!-- Key moment replay -->
    </div>
    <div class="answer-section">
      <p class="answer-text">AI answer...</p>
      <div class="player-identification">
        <!-- Highlighted player -->
      </div>
    </div>
  </div>
  <div class="countdown">8s</div>
</div>
```

**Styling:**
- Auto-dismiss: 8s
- Background: Solid overlay (no blur)
- Animation: Fade in/out only

**See:** `fan-ai-temporal-replay.html` for exact layout

---

## Forbidden Patterns

**DO NOT USE:**

```css
/* No glassmorphism */
backdrop-filter: blur(12px); /* FORBIDDEN */

/* No glow effects */
box-shadow: 0 0 20px rgba(204, 255, 0, 0.5); /* FORBIDDEN */

/* No breathing animations */
@keyframes breathe { ... } /* FORBIDDEN */

/* No gradient backgrounds */
background: linear-gradient(...); /* FORBIDDEN */

/* No large radius */
border-radius: 24px; /* FORBIDDEN (max 12px except full) */
```

---

## Approved Patterns

**USE ONLY:**

```css
/* Solid surfaces */
background: #1A1A1A;

/* 1px solid borders */
border: 1px solid #353535;

/* Simple opacity transitions */
transition: opacity 300ms ease;

/* Transform for position */
transition: transform 300ms ease;

/* Border color for states */
border-color: #CCFF00;
```

---

## Accessibility Requirements

### Contrast Ratios

- Primary text: 7:1+ (AAA)
- Secondary text: 4.5:1+ (AA)
- Interactive elements: 3:1+ against background

### Keyboard Navigation

```javascript
// Tab order must be logical
// Enter/Space activates buttons
// Arrows adjust sliders
// Escape dismisses overlays
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
  /* Except opacity */
  .fade-element {
    transition: opacity 300ms ease;
  }
}
```

---

## File Structure

```
frontend/src/
├── components/
│   ├── LandingPage.tsx         ← Hero, features, CTA
│   ├── MatchDashboard.tsx      ← Main container
│   ├── VideoCanvas.tsx         ← Video + overlays
│   ├── MicButton.tsx           ← 48px floating Q&A
│   ├── ControlsTray.tsx        ← Settings bar
│   ├── Teleprompter.tsx        ← Beat highlighting
│   ├── CommentaryFeed.tsx      ← Live stream
│   ├── EventFeed.tsx           ← Match events
│   ├── MatchInsight.tsx        ← Trivia/Q&A
│   ├── TriviaCard.tsx          ← Animated cards
│   └── SplitScreen.tsx         ← Q&A overlay
├── hooks/
│   ├── useWebSocket.ts
│   ├── useBeatHighlight.ts
│   └── useSpeechRecognition.ts
├── lib/
│   ├── constants.ts            ← Design tokens
│   └── utils.ts
└── styles/
    └── globals.css             ← CSS custom properties
```

---

## Quality Checklist

Before marking any component as complete:

- [ ] Matches reference HTML exactly (colors, spacing, layout)
- [ ] Uses correct fonts (Inter for body, Space Grotesk for labels)
- [ ] No forbidden patterns (blur, glow, gradients)
- [ ] All interactive states defined (idle, hover, active, disabled)
- [ ] Keyboard navigation works
- [ ] AAA contrast ratios verified
- [ ] prefers-reduced-motion supported
- [ ] Solid colors only (no glassmorphism)
- [ ] 1px solid borders (#353535 or Electric Lime for active)
- [ ] 4px base radius (small, technical feel)

---

## Quick Start

```bash
# 1. Open reference in browser
open .bmad/screens/pitchai-landing-page.html    # Landing page
open .bmad/screens/fan-lens-broadcast.html      # Main dashboard
open .bmad/screens/commentator-dashboard.html   # Teleprompter view

# 2. Inspect colors and spacing in browser DevTools

# 3. Create component matching reference exactly
# DO NOT improvise - copy what you see
```

---

**Remember:** The HTML files in `.bmad/screens/` are the source of truth. If this document conflicts with what you see in the reference files, **follow the reference files**.
