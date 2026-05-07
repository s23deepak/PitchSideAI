# Parallel Development Plan — Backend + Frontend Integration

**Date:** 2026-05-06  
**Goal:** Connect Stitch HTML designs to working backend features

---

## Current State Audit

### ✅ Backend Features (Already Implemented)

| Feature | Endpoint | Status |
|---------|----------|--------|
| WebSocket Session | `/ws/live` | ✅ Working |
| Trivia Cards | `type: "trivia_card"` | ✅ Broadcasting |
| Beat Highlighting | `type: "beat_highlight"` | ✅ Broadcasting |
| Commentary Stream | `type: "commentary"` | ✅ Broadcasting |
| Tactical Detections | `type: "tactical_detection"` | ✅ Broadcasting |
| Language Translation | `manager.store_language()` | ✅ Implemented |
| Q&A Answers | `type: "qa_answer"` | ✅ Broadcasting |
| Settings Update | `type: "settings_update"` | ⚠️ Received but not persisted |
| Video Streaming | `/ws/video/stream` | ✅ Working |

### ⚠️ Frontend Features (Need Connection)

| Feature | Component | Status |
|---------|-----------|--------|
| Navigation Links | LandingPage.jsx | ❌ Links to `#` (not `/dashboard`) |
| Settings Persistence | ControlsTray → Backend | ⚠️ Sent but not stored |
| Language Translation | ControlsTray → Backend | ⚠️ Sent but not stored |
| Beat Highlighting | Teleprompter | ✅ Listening via custom events |
| Trivia Cards | MatchInsight | ✅ Receiving from WebSocket |
| Q&A Split Screen | SplitScreen | ⚠️ Not wired to WebSocket |
| Notes Generation Hub | No route | ❌ Not implemented |

---

## Development Waves (Parallel Execution)

### Wave 1: Navigation + Settings (30 min)

**Frontend Tasks:**
1. Fix LandingPage nav links: `#` → `/dashboard`
2. Wire `settings_update` to WebSocket in MatchDashboard
3. Wire `language` change to WebSocket

**Backend Tasks:**
1. Handle `settings_update` message → store in `ConnectionManager._settings`
2. Handle `language` message → call `manager.store_language()`
3. Add logging for settings/language persistence

**Shared Contract:**
```python
# Backend stores per-session:
self._settings[session_id] = {"bias": 0, "excitement": 0.5, "knowledge": 0.5}
self._languages[session_id] = "en"  # or "es"
```

---

### Wave 2: Q&A Integration (45 min)

**Frontend Tasks:**
1. Wire MicButton `onQuestionSubmit` to WebSocket
2. Show split-screen when `qa_answer` received
3. Add loading state while AI processes

**Backend Tasks:**
1. Handle `type: "query"` message → route to QAAgent
2. Broadcast `type: "qa_answer"` with split-screen data
3. Add rate limiting (3 questions per minute)

**Shared Contract:**
```typescript
// Frontend sends:
{ type: "query", text: "What's the formation?", confidence: 0.9 }

// Backend responds:
{
  type: "qa_answer",
  question: "What's the formation?",
  answer: "Barcelona playing 4-3-3...",
  confidence: 0.85,
  display_duration_ms: 8000
}
```

---

### Wave 3: Notes Generation Hub (60 min)

**Frontend Tasks:**
1. Create `/notes` route with NotesGenerationHub component
2. Show pre-match research progress
3. Display generated notes in Teleprompter format

**Backend Tasks:**
1. Expose `GET /api/notes/{match_session}` endpoint
2. Stream SSE progress during notes generation
3. Cache generated notes for replay

**Shared Contract:**
```typescript
// Frontend polls:
GET /api/notes/barcelona-vs-real-madrid

// Backend returns:
{
  status: "building" | "ready" | "failed",
  progress: 0.65,
  notes: { /* full commentary notes */ }
}
```

---

### Wave 4: Commentator Dashboard Polish (45 min)

**Frontend Tasks:**
1. Ensure CommentatorLayout shows Teleprompter by default
2. Add "Show Notes" toggle for mobile
3. Wire ControlsTray to work in both views

**Backend Tasks:**
- No backend changes needed (uses same WebSocket)

---

### Wave 5: Fan Lens Broadcast Polish (30 min)

**Frontend Tasks:**
1. Ensure FanLensLayout shows all components (VideoCanvas, TriviaCards, MicButton)
2. Test responsive breakpoints (desktop, tablet, mobile)
3. Verify touch targets ≥44×44px

**Backend Tasks:**
- No backend changes needed (uses same WebSocket)

---

## File Changes Required

### Frontend (5 files)
| File | Change |
|------|--------|
| `frontend/src/pages/LandingPage.jsx` | Fix nav links: `#` → `/dashboard` |
| `frontend/src/components/MatchDashboard.jsx` | Wire settings/language to WebSocket |
| `frontend/src/components/MicButton.jsx` | Wire `onQuestionSubmit` to WebSocket |
| `frontend/src/pages/NotesPage.jsx` | CREATE (Notes Generation Hub) |
| `frontend/src/App.jsx` | Add `/notes` route |

### Backend (1 file)
| File | Change |
|------|--------|
| `api/server.py` | Add settings/language persistence, Q&A routing |

---

## Execution Strategy

### Option 1: Sequential (Safe, Slower)
1. Complete Wave 1 backend → test → Wave 1 frontend → test
2. Repeat for each wave

### Option 2: Parallel (Fast, Requires Coordination)
1. **You:** Backend changes (Wave 1-3)
2. **Me:** Frontend changes (Wave 1-3)
3. Merge and test together

### Option 3: Feature Flags (Safest for Parallel)
1. Add feature flags to backend: `ENABLE_SETTINGS_PERSISTENCE`, `ENABLE_QA_ROUTING`
2. Develop both sides independently
3. Flip flags when both ready

---

## Recommended: **Option 2 (Parallel)**

**You handle backend:**
- Wave 1: Settings/language persistence in `ConnectionManager`
- Wave 2: Q&A message routing to QAAgent
- Wave 3: Notes API endpoint

**I handle frontend:**
- Wave 1: Nav links + WebSocket wiring
- Wave 2: MicButton Q&A integration
- Wave 3: Notes Generation Hub page

**We merge when both sides complete their waves.**

---

## Success Criteria

After all waves complete:

1. ✅ Clicking "Fan Lens" navigates to working dashboard
2. ✅ Settings sliders persist across page reload
3. ✅ Language toggle switches commentary language
4. ✅ MicButton Q&A shows answers in split-screen
5. ✅ Notes Hub shows generated commentary notes
6. ✅ All components use Midnight Stadium tokens

---

## Next Action

**Choose one:**
1. **"Start Wave 1"** — I fix frontend nav + settings, you do backend persistence
2. **"Do all waves"** — I implement all frontend, you implement all backend
3. **"Just fix navigation"** — Minimal fix to get into dashboard

What's your preference?
