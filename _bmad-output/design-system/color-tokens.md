# Midnight Stadium Color Tokens

**Project:** PitchAI  
**Design System:** Midnight Stadium v3.0  
**Reference:** `.bmad/midnight-stadium-design.md`  
**Last Updated:** 2026-05-05

---

## Color Palette

### Background Colors

| Token | CSS Variable | Hex | Usage |
|-------|--------------|-----|-------|
| `bg-primary` | `--bg-primary` | #020617 | Page background (Slate 950) |
| `bg-surface` | `--bg-surface` | #0F172A | Secondary surfaces (Slate 900) |
| `bg-surface-secondary` | `--bg-surface-secondary` | #1A1A1A | Card/panel backgrounds |
| `bg-surface-hover` | `--bg-surface-hover` | #20201F | Hover states |
| `bg-surface-container` | `--bg-surface-container` | #2A2A2A | Container backgrounds |
| `bg-elevated` | `--bg-elevated` | #1E293B | Elevated surfaces (Slate 800) |

### Functional Accents (UX-DR24)

| Token | CSS Variable | Hex | Usage | NEVER For |
|-------|--------------|-----|-------|-----------|
| `accent-critical` | `--accent-critical` | #CCFF00 | Live badge, recording, AI active borders | Body text, decoration |
| `accent-narrative` | `--accent-narrative` | #FFD700 | Teleprompter beats, key highlights, milestones | Interactive states |
| `accent-data` | `--accent-data` | #FFFFFF | Dense data, headings, stats | Muted info |
| `accent-interactive` | `--accent-interactive` | #22D3EE | Focus rings, hover, selected states | Narrative elements |

### Semantic Colors

| Token | CSS Variable | Hex | Usage |
|-------|--------------|-----|-------|
| `success` | `--success` | #10B981 | Success states, connected indicators |
| `warning` | `--warning` | #F59E0B | Warning states, reconnecting indicators |
| `danger` | `--danger` | #EF4444 | Error states, disconnected, recording |

### Text Colors

| Token | CSS Variable | Hex | Contrast Ratio | Usage |
|-------|--------------|-----|----------------|-------|
| `text-primary` | `--text-primary` | #F1F5F9 | 14.5:1 on bg-primary | Primary text (AAA) |
| `text-secondary` | `--text-secondary` | #94A3B8 | 7.2:1 on bg-primary | Secondary text (AA) |
| `text-muted` | `--text-muted` | #64748B | 4.8:1 on bg-primary | Tertiary text |

### Border & Overlay

| Token | CSS Variable | Value | Usage |
|-------|--------------|-------|-------|
| `border` | `--border` | #353535 | 1px solid borders |
| `border-accent` | `--border-accent` | `--accent-interactive` | Focus rings, active states |
| `overlay-stroke` | `--overlay-stroke` | rgba(255, 255, 255, 0.9) | SVG overlay strokes |
| `overlay-shadow` | `--overlay-shadow` | rgba(0, 0, 0, 0.5) | Drop shadows |

---

## Usage Rules

### Two-Accent System (UX-DR24)

**Critical (Electric Lime #CCFF00):**
- Live recording indicator
- AI active borders
- Connection status (connected)
- Critical alerts

**Narrative (Gold #FFD700):**
- Teleprompter current beat highlight
- Key narrative moments
- Premium stats/milestones
- Historical references

**Interactive (Cyan #22D3EE):**
- Focus rings (2px)
- Hover states on buttons
- Selected chips/tabs
- Slider thumbs

### Color Diligence

> **Never use amber for interactive elements or cyan for narrative elements.**
> Two-accent system prevents meaning dilution.

---

## Accessibility

### WCAG 2.1 Compliance

| Requirement | Target | Status |
|-------------|--------|--------|
| Primary text contrast | 7:1+ (AAA) | ✅ 14.5:1 |
| Secondary text contrast | 4.5:1+ (AA) | ✅ 7.2:1 |
| Interactive element contrast | 3:1+ (AA) | ✅ 4.8:1 |
| Focus indicator visibility | 2px solid | ✅ Cyan 400 ring |

### Confidence Visualization (UX-DR21)

Confidence is **NEVER** communicated by color alone. Always paired with:
- Numeric badge (e.g., "0.87")
- Source attribution (e.g., "StatsBomb")
- Icon + text label

---

## Implementation

### CSS Custom Properties

```css
/* Import in index.css */
@import './design-tokens/tokens.css';

/* Usage in components */
.button {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
}

.button:hover {
  border-color: var(--accent-interactive);
}

.button:focus-visible {
  outline: 2px solid var(--accent-interactive);
}
```

### Tailwind Configuration

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'var(--bg-primary)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
        },
        accent: {
          critical: 'var(--accent-critical)',
          narrative: 'var(--accent-narrative)',
          interactive: 'var(--accent-interactive)',
        },
      },
    },
  },
}
```

---

## Component Examples

### MicButton States

| State | Border | Background | Animation |
|-------|--------|------------|-----------|
| Idle | `--border` | `--bg-surface` | None |
| Hover | `--accent-interactive` | `--bg-surface` | Glow |
| Recording | `--danger` | `--bg-surface` | Pulse |
| Processing | `--accent-critical` | `--bg-surface` | Rotating gradient |

### TriviaCard

```css
.trivia-card {
  background: var(--bg-surface-secondary);
  border-left: 3px solid var(--accent-narrative);
  color: var(--text-primary);
}
```

### Teleprompter Beat Highlight

```css
.beat-current {
  background: var(--accent-narrative-muted); /* 15% opacity */
  border-left: 3px solid var(--accent-narrative);
}
```

---

## Design Philosophy

**Midnight Stadium** is:
- Bloomberg Terminal meets F1 telemetry — functional, dense, professional
- Broadcast software aesthetic — every element serves a purpose
- High contrast — AAA accessibility, critical states pop
- Dark, immersive — feels like being in a stadium at night under the lights

**Midnight Stadium** is NOT:
- Glassmorphism / frosted glass
- Glow effects or drop shadows
- Breathing/pulsing animations (except for critical states)
- Gradient backgrounds
- "AI blue" or "tech purple"
- Playful with large rounded corners
