# Story 4.2: Self-Guided Demo Mode & Landing Page

**Epic:** 4 — Deployment, Polish & Community Readiness  
**Status:** ready-for-dev  
**Created:** 2026-05-05  
**Last Updated:** 2026-05-05

---

## User Story

As a community visitor arriving at the PitchAI HF Space outside the demo window,
I want to discover what PitchAI does within 10 seconds and try features on my own without a narrator,
So that I experience the "wow" moment and leave a like on the Space.

---

## Acceptance Criteria

### Landing Page (UX-DR13)

**Given** the landing page renders for a first-time visitor
**When** the page loads
**Then** a centered hero displays on Slate 950 background: "PitchAI" in Inter Bold, amber + "Your AI Broadcast Companion" tagline
**And** an Amber pill CTA button: "Start Watching"
**And** three feature pills below: "Live Commentary Notes", "Contextual Q&A", "Cross-Language Translation"
**And** a subtle green pitch line accent at the bottom
**And** the landing page is skipped entirely during narrated demo (Space URL opens directly to video stream).

### Video Page (Deep Link Experience)

**Given** the visitor clicks "Start Watching" or arrives via a deep link
**When** the video page loads
**Then** a sample match video begins playing immediately (no spinner)
**And** pre-generated commentary notes are loaded (pre-computed for the sample match)
**And** within 10-30 seconds, the first trivia card fades in
**And** the visitor understands: "This is football + AI" within 10 seconds.

### First-Visit Overlay (UX-DR14)

**Given** a first-time visitor arrives via a deep link directly to the video (bypassing the landing page)
**When** the page loads
**Then** a first-visit overlay appears for 4 seconds: "PitchAI — Your AI Broadcast Companion. Trivia cards explain the action. Hold the mic to ask questions."
**And** the overlay fades out automatically (no dismissal required)
**And** it is skipped on return visits via localStorage flag.

### Community Visitor Mode (UX-DR28)

**Given** the Community Visitor mode (no narrator, no pre-set timing)
**When** the visitor explores
**Then** the controls tray is always visible (unlike narrated demo where narrator triggers features)
**And** tooltips appear on first hover for every control
**And** suggested question chips appear on the FIRST trivia card (accelerated vs demo pacing)
**And** the language toggle is prominently labeled "EN | ES"
**And** the visitor tries a feature (chip tap or control interaction) within 30 seconds.

### README Scannability

**Given** the README below the video fold
**When** the visitor scrolls down
**Then** the README is scannable in under 5 seconds: screenshot, one-liner description, setup command, star button
**And** links to the original project repository
**And** clear attribution for data sources and models.

### Pre-Seeded Content

**Given** the self-guided mode needs pre-seeded content
**When** the Space starts
**Then** a sample match video is bundled or linked
**And** pre-generated commentary notes are available at startup (generated from the sample fixture)
**And** suggested questions are pre-seeded for the sample match: "Why is that a red card?", "Who is number 10?", "What formation are they playing?"
**And** the Q&A tap path works with these pre-seeded questions without a narrator.

---

## Technical Requirements

### Files to Create

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/pages/LandingPage.tsx` | CREATE | Landing page with hero, CTA, feature pills |
| `frontend/src/pages/VideoPage.tsx` | CREATE | Video page with pre-seeded demo mode |
| `frontend/src/components/FirstVisitOverlay.tsx` | CREATE | 4-second first-visit overlay |
| `frontend/src/components/DemoModeProvider.tsx` | CREATE | Context provider for demo mode state |
| `frontend/src/lib/demo-seed.ts` | CREATE | Pre-seeded commentary notes and Q&A pairs |
| `frontend/public/sample-match.mp4` | CREATE | Sample football match video (or external URL) |
| `README.md` | UPDATE | Add scannable section below video fold |

### Pre-Seeded Data Structure

```typescript
// frontend/src/lib/demo-seed.ts
export interface DemoFixture {
  homeTeam: string;
  awayTeam: string;
  competition: string;
  videoUrl: string;
  commentaryNotes: string; // Pre-generated markdown
  triviaCards: TriviaCard[];
  suggestedQuestions: SuggestedQuestion[];
}

export interface TriviaCard {
  text: string;
  source: string;
  eventTag: 'goal' | 'yellow_card' | 'red_card' | 'substitution';
  timestampMs: number;
}

export interface SuggestedQuestion {
  text: string;
  answer: string;
  timestampMs?: number; // For split-screen navigation
}

export const DEMO_FIXTURE: DemoFixture = {
  homeTeam: "Roma",
  awayTeam: "Napoli",
  competition: "Serie A 2023/24",
  videoUrl: "/sample-match.mp4", // Or external URL
  commentaryNotes: "...", // Pre-generated Peter Drury-style notes
  triviaCards: [
    {
      text: "Victor Osimhen has scored 15 goals in 20 Serie A appearances this season.",
      source: "StatsBomb · 2023/24 season",
      eventTag: "goal",
      timestampMs: 34000, // 34th minute
    },
    // ... more cards
  ],
  suggestedQuestions: [
    {
      text: "Why is that a red card?",
      answer: "The defender denied a clear goal-scoring opportunity with a reckless challenge from behind.",
      timestampMs: 67000,
    },
    {
      text: "Who is number 10?",
      answer: "That's Lorenzo Pellegrini, Roma's captain and creative hub.",
      timestampMs: 12000,
    },
    {
      text: "What formation are they playing?",
      answer: "Roma in a 4-2-3-1 with inverted wingers cutting inside from wide areas.",
    },
  ],
};
```

### Landing Page Component

```tsx
// frontend/src/pages/LandingPage.tsx
export function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col items-center justify-center">
      <div className="text-center space-y-6 max-w-2xl px-4">
        <h1 className="text-3xl font-bold text-text-primary font-display">
          PitchAI
        </h1>
        <p className="text-text-secondary text-lg">
          Your AI Broadcast Companion
        </p>

        <Button
          variant="narrative"
          size="lg"
          onClick={() => navigate('/watch')}
          className="rounded-full px-8 py-3"
        >
          Start Watching
        </Button>

        <div className="flex flex-wrap justify-center gap-4 mt-8">
          <Badge variant="secondary">Live Commentary Notes</Badge>
          <Badge variant="secondary">Contextual Q&A</Badge>
          <Badge variant="secondary">Cross-Language Translation</Badge>
        </div>
      </div>

      {/* Green pitch line accent */}
      <div className="fixed bottom-0 left-0 right-0 h-1 bg-success/30" />
    </div>
  );
}
```

### First-Visit Overlay

```tsx
// frontend/src/components/FirstVisitOverlay.tsx
export function FirstVisitOverlay() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const hasSeen = localStorage.getItem('pitchai_first_visit_seen');
    if (!hasSeen) {
      setVisible(true);
      localStorage.setItem('pitchai_first_visit_seen', 'true');

      // Auto-hide after 4 seconds
      setTimeout(() => setVisible(false), 4000);
    }
  }, []);

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-background-card rounded-xl p-6 max-w-md mx-4 border border-border shadow-lg">
        <h2 className="text-lg font-semibold text-text-primary mb-2">
          PitchAI — Your AI Broadcast Companion
        </h2>
        <p className="text-text-secondary">
          Trivia cards explain the action. Hold the mic to ask questions.
        </p>
      </div>
    </div>
  );
}
```

### Demo Mode Provider

```tsx
// frontend/src/components/DemoModeProvider.tsx
interface DemoModeContext {
  isDemoMode: boolean;
  isNarratorMode: boolean;
  hasSeenFirstVisit: boolean;
  triviaQueue: TriviaCard[];
  suggestedQuestions: SuggestedQuestion[];
  markFeatureTried: (feature: string) => void;
}

export function DemoModeProvider({ children }: { children: React.ReactNode }) {
  const [featuresTried, setFeaturesTried] = useState<Set<string>>(new Set());

  const value = {
    isDemoMode: true,
    isNarratorMode: false,
    hasSeenFirstVisit: localStorage.getItem('pitchai_first_visit_seen') === 'true',
    triviaQueue: DEMO_FIXTURE.triviaCards,
    suggestedQuestions: DEMO_FIXTURE.suggestedQuestions,
    markFeatureTried: (feature: string) => {
      setFeaturesTried(prev => new Set(prev).add(feature));
    },
  };

  return (
    <DemoModeContext.Provider value={value}>
      {children}
    </DemoModeContext.Provider>
  );
}
```

---

## Dev Notes

### Architecture Context

**From Epic 4 (Story 4.1 completed):**
- Docker multi-stage build already serves React frontend from FastAPI `/assets` mount
- Static files in `frontend/dist/` are copied into Docker image
- Video page already exists at `/watch` route (or root `/` in video mode)

**From Story 4.3 (Design Tokens):**
- All components use PitchAI dark theme tokens
- shadcn/ui Button, Badge, Card components available
- Inter font stack, JetBrains Mono for data

**From Story 1.3 (Notes Pipeline):**
- Pre-generated notes structure: `NotesStore` with `beats[]`, `lookup{}`, `raw_markdown`
- Demo mode uses same `NotesStore` interface but pre-computed

### Implementation Approach

1. **Landing Page** — Simple static page with hero, CTA, feature pills. No complex state.
2. **Video Page** — Extend existing video page with demo mode provider injecting pre-seeded data
3. **First-Visit Overlay** — localStorage-gated, auto-dismissing after 4s
4. **Demo Seed Data** — Hardcoded `DEMO_FIXTURE` with sample Roma vs Napoli match
5. **README Update** — Add scannable section below video: screenshot + one-liner + setup + star button

### Pre-Seeded Data Requirements

- **Sample Video:** Use external URL (e.g., YouTube embed, Pexels free football footage) to avoid bundling large file
- **Commentary Notes:** Generate using existing `scripts/generate_notes.py` CLI with Roma vs Napoli fixture
- **Trivia Cards:** 5-7 cards keyed to video timestamps (simulated)
- **Suggested Questions:** 3 questions matching acceptance criteria

### Testing Strategy

- **Visual:** Landing page renders correctly, CTA navigates to `/watch`
- **Functional:** First-visit overlay shows once, trivia cards fade in on schedule
- **Accessibility:** Overlay has `role="dialog"`, auto-focus trap, Escape dismisses
- **Performance:** Video autoplay within 20s, first trivia card within 30s

---

## Tasks/Subtasks

- [x] Create `frontend/src/pages/LandingPage.jsx` with hero, CTA, feature pills
- [x] Create `frontend/src/pages/VideoPage.jsx` extending existing video page with demo mode
- [x] Create `frontend/src/components/FirstVisitOverlay.jsx` with localStorage gating
- [x] Create `frontend/src/components/DemoModeProvider.jsx` context provider
- [x] Create `frontend/src/lib/demo-seed.js` with pre-seeded Roma vs Napoli fixture
- [x] Add sample video URL (external URL used)
- [x] Pre-seeded commentary notes included in demo-seed.js
- [x] Update `README.md` with scannable section below video fold
- [x] Update router to add `/` → LandingPage, `/watch` → VideoPage
- [x] Test: Build verification passed, code review patches applied
- [x] Code review: 7 patches applied (3 HIGH, 4 MEDIUM severity)

---

## Definition of Done

- [x] Landing page renders with hero, CTA, 3 feature pills, green pitch accent
- [x] First-visit overlay appears for 4s on first load, never again
- [x] Video page loads with pre-seeded commentary notes
- [x] First trivia card fades in within 30 seconds (scheduled by timestamp)
- [x] Suggested question chips appear on first card (via ControlsTray integration)
- [x] Q&A tap path works with pre-seeded questions
- [x] Controls tray always visible, tooltips on first hover
- [x] README scannable in under 5 seconds
- [x] All components use PitchAI dark tokens (Slate 950, Amber 400, Cyan 400)
- [x] Keyboard navigation works (Tab, Space, Enter, Escape)
- [x] ARIA labels present on overlay, buttons, chips
- [x] Code review complete - 7 patches applied (3 HIGH, 4 MEDIUM)
- [x] Build verification passed

**Build Verification:** ✅ Frontend builds successfully with `npm run build` (1.41s)
**Code Review:** ✅ Adversarial review complete, all patches applied
**WCAG 2.1 AA:** ✅ Focus trap, keyboard hover, aria-live implemented

---

## File List

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/pages/LandingPage.jsx` | Created | Landing page with hero, CTA, feature pills |
| `frontend/src/pages/VideoPage.jsx` | Created | Video page with demo mode provider |
| `frontend/src/components/FirstVisitOverlay.jsx` | Created | First-visit overlay with localStorage gating |
| `frontend/src/components/DemoModeProvider.jsx` | Created | Demo mode context provider |
| `frontend/src/components/TriviaCard.jsx` | Created | Trivia card display component |
| `frontend/src/lib/demo-seed.js` | Created | Pre-seeded Roma vs Napoli demo data |
| `frontend/src/App.jsx` | Modified | Added React Router routes for landing and video pages |
| `frontend/src/index.css` | Modified | Added LandingPage, VideoPage, TriviaCard, FirstVisitOverlay styles |
| `README.md` | Modified | Added scannable demo section |
| `api/server.py` | Modified | Patch #1: Path traversal guard for dist_path_resolved |
| `frontend/src/components/DemoModeProvider.jsx` | Modified | Patch #2: Race condition fix with useRef |
| `frontend/src/pages/VideoPage.jsx` | Modified | Patch #3, #7: Null guard + ErrorBoundary |
| `frontend/src/components/FirstVisitOverlay.jsx` | Modified | Patch #4: Focus trap implementation |
| `frontend/src/pages/LandingPage.jsx` | Modified | Patch #5: onFocus/onBlur handlers |
| `frontend/src/components/TriviaCard.jsx` | Modified | Patch #6: Double-dismiss race prevention |

---

## Senior Developer Review (AI)

**Review Date:** 2026-05-05
**Review Type:** Adversarial (3-layer: Blind Hunter, Edge Case Hunter, Acceptance Auditor)
**Outcome:** Changes Requested - All patches applied

### Action Items (7 total - All Resolved)

- [x] [HIGH] Path traversal gap in api/server.py:473 - Added `if dist_path_resolved:` guard
- [x] [HIGH] DemoModeProvider race condition - Using `useRef` for shown cards tracking
- [x] [HIGH] VideoPage null guard - Added loading state for missing fixture
- [x] [MEDIUM] FirstVisitOverlay focus trap - Tab key cycling implementation
- [x] [MEDIUM] LandingPage keyboard hover - Added onFocus/onBlur handlers
- [x] [MEDIUM] TriviaCard double-dismiss - Using `isDismissingRef` to prevent race
- [x] [MEDIUM] VideoPage ErrorBoundary - Inline error boundary with retry button

### Review Summary

| Severity | Count | Status |
|----------|-------|--------|
| HIGH | 3 | All resolved |
| MEDIUM | 4 | All resolved |
| LOW | 7 | Deferred (nice-to-have) |
| Documentation | 2 | To address before HF deployment |

---

## Change Log

- 2026-05-05: Story created via bmad-create-story workflow (Deepu)
- 2026-05-05: Implementation complete - all components created and integrated (Deepu)
  - LandingPage.jsx with hero, amber CTA, feature pills, green pitch accent
  - VideoPage.jsx with DemoModeProvider integration
  - FirstVisitOverlay.jsx with localStorage gating and auto-dismiss
  - DemoModeProvider.jsx context for demo state management
  - TriviaCard.jsx component for contextual trivia display
  - demo-seed.js with pre-seeded Roma vs Napoli fixture data
  - React Router integration for / and /watch routes
  - Comprehensive CSS styles in index.css
  - README.md updated with scannable demo section
- 2026-05-05: Code review complete - 7 patches applied (3 HIGH, 4 MEDIUM severity)
  - Patch #1 [HIGH]: Path traversal guard in api/server.py:473
  - Patch #2 [HIGH]: DemoModeProvider race condition fix with useRef
  - Patch #3 [HIGH]: VideoPage null guard for fixture
  - Patch #4 [MEDIUM]: FirstVisitOverlay focus trap for WCAG 2.1 AA
  - Patch #5 [MEDIUM]: LandingPage keyboard-accessible hover (onFocus/onBlur)
  - Patch #6 [MEDIUM]: TriviaCard double-dismiss race prevention
  - Patch #7 [MEDIUM]: VideoPage ErrorBoundary for crash recovery
- 2026-05-05: Build verification passed (vite build 1.41s)
