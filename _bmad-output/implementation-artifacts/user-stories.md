# PitchAI UI Implementation — User Stories & Acceptance Criteria

**Design System:** Midnight Stadium v3.0  
**Reference:** Stitch Project `15768476927893272015`  
**Local Screens:** `.bmad/screens/*.html`

---

## MCP Tools for Automated Verification

Before starting implementation, add these MCP servers to enable automated visual testing:

```bash
# Puppeteer for browser automation (REQUIRED for visual verification)
claude mcp add puppeteer npx -y @modelcontextprotocol/server-puppeteer

# Sequential Thinking for complex component logic (RECOMMENDED)
claude mcp add sequential-thinking npx -y @modelcontextprotocol/server-sequential-thinking

# Fetch for external docs (OPTIONAL)
claude mcp add fetch uvx mcp-server-fetch
```

### How Claude Uses These Tools

**After implementing each component:**

> "Use Puppeteer to open `http://localhost:5173`, navigate to the MatchDashboard, and verify:
> - VideoCanvas renders at 16:9 aspect ratio
> - MicButton is positioned 16px from bottom-right corner
> - ControlsTray has all 5 controls (Language, Bias, Excitement, Knowledge, View toggle)
> - All borders are 1px solid #353535
> - Take a screenshot and compare against `.bmad/screens/fan-lens-broadcast.html`"

**For interactive states:**

> "Use Puppeteer to simulate hover on the MicButton and verify the border changes to #CCFF00. Then simulate a 15-second hold and verify the border animates to #EF4444 with pulse animation."

---

## Epic 1: Landing Page

### Story 1.1 — Hero Section

**As a** potential user  
**I want** to see a compelling hero that explains PitchAI's value  
**So that** I understand what the product does within 5 seconds

**Reference:** `.bmad/screens/pitchai-landing-page.html`

**Acceptance Criteria:**
- [ ] Hero headline uses 48px Inter ExtraBold
- [ ] Tagline uses 24px Inter Bold, text-secondary color
- [ ] Primary CTA uses Electric Lime (#CCFF00) background
- [ ] Secondary CTA uses transparent background with Electric Lime border
- [ ] Both CTAs have 4px radius
- [ ] Background is solid #131313 (no gradients)
- [ ] **Puppeteer verifies:** All elements visible, correct font sizes, correct colors

---

### Story 1.2 — Features Section

**As a** evaluator  
**I want** to see key features highlighted  
**So that** I can assess if PitchAI meets my needs

**Reference:** `.bmad/screens/pitchai-landing-page.html`

**Acceptance Criteria:**
- [ ] Feature cards use #1A1A1A background
- [ ] 1px solid #353535 borders
- [ ] Icons use Electric Lime or Gold (functional, not decorative)
- [ ] Feature titles use Space Grotesk Bold
- [ ] Feature descriptions use Inter Regular
- [ ] **Puppeteer verifies:** Cards align in grid, no overflow, borders render correctly

---

### Story 1.3 — Demo CTA

**As a** interested visitor  
**I want** a clear path to try the product  
**So that** I can start using PitchAI immediately

**Reference:** `.bmad/screens/pitchai-landing-page.html`

**Acceptance Criteria:**
- [ ] CTA section uses high contrast (Electric Lime or Gold accent)
- [ ] Button is prominent, minimum 48px height
- [ ] Clear action text ("Start Commentary" or similar)
- [ ] **Puppeteer verifies:** Button is clickable, leads to correct route

---

## Epic 2: Core Broadcast Dashboard

### Story 2.1 — MatchDashboard Container

**As a** commentator or fan  
**I want** a clean, information-dense layout  
**So that** I can follow the match without distraction

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] Header is sticky, 60px height, solid #131313 background
- [ ] Match title uses Inter Bold, 24px
- [ ] 3-column grid for bottom section (Commentary, Events, Insights)
- [ ] Each column minimum 300px width
- [ ] ControlsTray fixed at bottom, 56px height
- [ ] **Puppeteer verifies:** Layout matches reference HTML, no horizontal scroll

---

### Story 2.2 — VideoCanvas with Tactical Overlays

**As a** viewer  
**I want** to see the match with tactical analysis overlays  
**So that** I understand player positioning and key moments

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] Video maintains 16:9 aspect ratio
- [ ] SVG overlays: player dots (team colors), ball marker (Electric Lime)
- [ ] Label badges use Space Grotesk, solid #1A1A1A background
- [ ] Connection badge in top-right (Live/Reconnecting/Disconnected)
- [ ] **Puppeteer verifies:** Overlays render on top of video, correct z-index

---

### Story 2.3 — MicButton (Hold-to-Talk Q&A)

**As a** viewer  
**I want** to ask questions about the match  
**So that** I can get AI-powered answers about key moments

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] 48px circular button, bottom-right positioning (16px from edges)
- [ ] 6 states implemented:
  - Idle: #1A1A1A bg, #353535 border
  - Hover: #CCFF00 border glow
  - Recording: #EF4444 border, pulse animation
  - Confirmation: #CCFF00 border, transcript popover
  - Processing: #CCFF00 rotating ring
  - Disabled: 50% opacity
- [ ] Space key triggers hold-to-talk
- [ ] Tooltip on first hover (persisted to localStorage)
- [ ] **Puppeteer verifies:** Each state renders correctly on trigger

---

### Story 2.4 — ControlsTray

**As a** user  
**I want** to customize the commentary experience  
**So that** it matches my preferences

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] Fixed bottom position, 56px height
- [ ] Solid #1A1A1A background, 1px solid #353535 top border
- [ ] Auto-hide after 3s idle (desktop), always visible (touch)
- [ ] 5 controls:
  - Language toggle (EN | ES)
  - Bias slider (-1 to +1, team abbreviations)
  - Excitement slider (0-1, Calm ← → Hype)
  - Knowledge slider (0-1, Basic ← → Tactical)
  - View toggle (Fan Lens | Commentator)
- [ ] Sliders have custom gradient tracks (Lime/Gold)
- [ ] Tooltips on first hover
- [ ] **Puppeteer verifies:** All controls present, sliders respond to input, auto-hide works

---

## Epic 3: Commentator Dashboard

### Story 3.1 — Teleprompter with Beat Highlighting

**As a** commentator  
**I want** to see my notes with current beat highlighting  
**So that** I know where I am in the script

**Reference:** `.bmad/screens/commentator-dashboard.html`

**Acceptance Criteria:**
- [ ] Tabbed mode (5 sections) + long-sheet mode
- [ ] Current beat: 15% Electric Lime bg, 3px left border, ▶ marker
- [ ] Next 3 beats: opacity 0.7 → 0.6 → 0.5
- [ ] Auto-scroll keeps current beat at 30% from top (300ms ease)
- [ ] Hold mode: manual scroll during pauses
- [ ] "Back to live" button appears when user scrolls manually
- [ ] Confidence gate: skip highlighting if < 0.7
- [ ] **Puppeteer verifies:** Highlighting applies to correct beat, auto-scroll position accurate

---

### Story 3.2 — Notes Generation Hub

**As a** commentator  
**I want** to generate pre-match notes  
**So that** I'm prepared before going live

**Reference:** `.bmad/screens/notes-generation-hub.html`

**Acceptance Criteria:**
- [ ] Team selection inputs
- [ ] Stats retrieval indicators (3-layer chain: StatsBomb → Firecrawl → FBref)
- [ ] Progress bar during generation (60% → 90%)
- [ ] Agent status text in Space Grotesk
- [ ] Notes preview with edit capability
- [ ] **Puppeteer verifies:** Progress bar animates, status text updates

---

## Epic 4: Fan Lens Features

### Story 4.1 — CommentaryFeed

**As a** fan  
**I want** to see live commentary streaming in  
**So that** I can follow the match narrative

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] Messages scroll automatically (newest at bottom)
- [ ] Peter Drury-style narrative text
- [ ] Source attribution (e.g., "via LiveAgent")
- [ ] Timestamps in Space Grotesk, muted color
- [ ] **Puppeteer verifies:** New messages append correctly, auto-scroll works

---

### Story 4.2 — EventFeed

**As a** fan  
**I want** to see match events in a timeline  
**So that** I can track goals, cards, and subs

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] Events displayed chronologically
- [ ] Icons for event types (goal, card, sub)
- [ ] Team colors for event markers
- [ ] Minute displayed in Space Grotesk
- [ ] **Puppeteer verifies:** Events render in correct order, icons visible

---

### Story 4.3 — MatchInsight (Trivia/Q&A)

**As a** fan  
**I want** to see trivia cards and Q&A history  
**So that** I learn interesting facts about the match

**Reference:** `.bmad/screens/fan-lens-broadcast.html`

**Acceptance Criteria:**
- [ ] TriviaCard animates in (300ms fade)
- [ ] Display duration: 5s if confidence ≥ 0.8, else 3s
- [ ] Source attribution visible
- [ ] Confidence indicator (subtle)
- [ ] Q&A history list below
- [ ] **Puppeteer verifies:** Card dismisses after correct duration, fade animation works

---

## Epic 5: Q&A Overlay

### Story 5.1 — SplitScreen Temporal Replay

**As a** viewer  
**I want** to see the moment I asked about  
**So that** I understand the context of the answer

**Reference:** `.bmad/screens/fan-ai-temporal-replay.html`

**Acceptance Criteria:**
- [ ] Overlay appears on `answer` WebSocket event
- [ ] 8s auto-dismiss countdown visible
- [ ] Video section shows key moment replay
- [ ] Answer section displays AI response
- [ ] Player identification highlighted
- [ ] SVG overlay coordinates applied if provided
- [ ] Background is solid (no blur)
- [ ] Animation: fade in/out only (no scale, no slide)
- [ ] **Puppeteer verifies:** Overlay appears, countdown ticks, auto-dismiss at 8s

---

## Epic 6: Accessibility & Quality

### Story 6.1 — Keyboard Navigation

**As a** keyboard-only user  
**I want** to navigate the entire UI without a mouse  
**So that** I can use all features

**Acceptance Criteria:**
- [ ] Tab cycles through all interactive elements
- [ ] Enter/Space activates buttons
- [ ] Arrow keys adjust sliders
- [ ] Escape dismisses overlays and cancels recording
- [ ] Focus indicators visible (Electric Lime outline)
- [ ] **Puppeteer verifies:** Full keyboard navigation works without mouse

---

### Story 6.2 — Reduced Motion

**As a** user with vestibular disorders  
**I want** animations to be minimized  
**So that** I can use the interface without discomfort

**Acceptance Criteria:**
- [ ] `prefers-reduced-motion` media query detected
- [ ] All animations reduced to 0.01ms except opacity transitions
- [ ] TriviaCard still fades in/out (opacity only)
- [ ] MicButton pulse replaced with static border
- [ ] Auto-scroll becomes instant jump
- [ ] **Puppeteer verifies:** With reduced-motion preference, animations disabled

---

### Story 6.3 — Contrast Ratios

**As a** user with low vision  
**I want** sufficient text contrast  
**So that** I can read all content

**Acceptance Criteria:**
- [ ] Primary text: 7:1+ contrast (AAA)
- [ ] Secondary text: 4.5:1+ contrast (AA)
- [ ] Interactive elements: 3:1+ against background
- [ ] Electric Lime text only on dark backgrounds
- [ ] **Puppeteer verifies:** (Manual check with contrast analyzer tool)

---

## Definition of Done (Per Component)

Each component is complete when:

1. ✅ **Visual Match:** Matches `.bmad/screens/*.html` reference exactly
2. ✅ **Puppeteer Verified:** Browser automation confirms:
   - Correct colors (hex values match)
   - Correct spacing (4px grid)
   - Correct fonts (Inter, Space Grotesk)
   - Correct borders (1px solid #353535)
   - Interactive states work (hover, active, disabled)
3. ✅ **Keyboard Nav:** Tab, Enter, Space, Arrows, Escape all work
4. ✅ **Reduced Motion:** Respects `prefers-reduced-motion`
5. ✅ **No Forbidden Patterns:** No blur, glow, gradients, large radius
6. ✅ **TypeScript Types:** All props typed, no `any`
7. ✅ **Unit Tests:** Vitest tests for logic (WebSocket, state, timers)

---

## Implementation Order

1. **Landing Page** (Epic 1) — Entry point, sets visual tone
2. **MatchDashboard Container** (Story 2.1) — Main layout shell
3. **VideoCanvas** (Story 2.2) — Central visual element
4. **MicButton** (Story 2.3) — Core Q&A interaction
5. **ControlsTray** (Story 2.4) — Settings and customization
6. **Teleprompter** (Story 3.1) — Commentator-critical feature
7. **CommentaryFeed + EventFeed + MatchInsight** (Epic 4) — Fan content
8. **SplitScreen** (Story 5.1) — Q&A overlay
9. **Accessibility** (Epic 6) — Polish and compliance

---

## Quick Reference: Puppeteer Commands

```typescript
// Example Puppeteer verification script
const page = await browser.newPage();
await page.goto('http://localhost:5173');

// Verify MicButton exists and has correct styles
const micButton = await page.$('.mic-button');
const styles = await micButton.evaluate(el => {
  const computed = window.getComputedStyle(el);
  return {
    width: computed.width,
    height: computed.height,
    borderRadius: computed.borderRadius,
    borderColor: computed.borderColor,
  };
});

console.assert(styles.width === '48px', 'MicButton width incorrect');
console.assert(styles.height === '48px', 'MicButton height incorrect');
console.assert(styles.borderRadius === '50%', 'MicButton should be circular');

// Verify hover state
await micButton.hover();
await page.waitForTimeout(300);
const hoverStyles = await micButton.evaluate(el => 
  window.getComputedStyle(el).borderColor
);
console.assert(hoverStyles === 'rgb(204, 255, 0)', 'Hover border should be Electric Lime');
```
