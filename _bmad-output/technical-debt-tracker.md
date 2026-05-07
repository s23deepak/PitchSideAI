# PitchAI Technical Debt Tracker

**Generated:** 2026-05-05  
**Updated:** 2026-05-05 (Epic 5/6 reorganization)  
**Source:** Epic 4 Retrospective (AI-4.2)  
**Purpose:** Track deferred findings from Epics 1-4 and prioritize for hackathon demo

---

## Epic Reorganization (2026-05-05)

**Epic 5** is now **UI/UX Revamp — Midnight Stadium Redesign** (12 stories, 4 waves)  
**Epic 6** is now **Production Hardening & Deployment Validation** (6 stories, 2 waves)

Deferred findings from Epic 4 are now tracked in **Epic 6 stories**:
- AI-4.4 → Story 6.1 (HF Space Deployment)
- AI-1.2, AI-4.3 → Story 6.3 (WebSocket Schema Audit)
- AI-2.1 → Story 6.4 (Pre-Computed Q&A Documentation)
- AI-3.1 → Story 6.2 (Settings Persistence)
- AI-3.3 → Story 6.5 (Translation Quality Review)
- AI-4.2 → Story 6.6 (Technical Debt Cleanup)

---

## Summary

| Severity | Count | Must Fix Before Demo? |
|----------|-------|----------------------|
| Critical | 0 | N/A |
| High | TBD | Yes |
| Medium | TBD | If time permits |
| Low | TBD | No |

---

## Deferred Findings by Story

### Story 4.1: Docker Build & HF Space Deployment

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 4.1-D1 | Font stack anti-pattern (Inter duplicated) | Low | Clean up CSS font stack | Frontend | Deferred |
| 4.1-D2 | Aggressive motion reduction (0.01ms may cause issues) | Low | Test with actual screen readers | Dana | Deferred |
| 4.1-D3 | Missing CSP headers for static serving | Medium | Add Content-Security-Policy header | Charlie | Deferred |
| 4.1-D4 | 8 shadcn/ui components not evidenced in diff | Low | Components exist per story 4.3 file | Deepu | Dismissed |

### Story 4.2: Self-Guided Demo Mode & Landing Page

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 4.2-D1 | Duplicate dependencies in package.json | Low | Verify class-variance-authority and tailwind-merge are required | Frontend | Dismissed |
| 4.2-D2 | Missing `gradio` tag in HF Space YAML | Low | Not required for Docker SDK spaces | Deepu | Dismissed |
| 4.2-D3 | Typography scale incomplete | Low | Scale IS complete (xs through 3xl) | Deepu | Dismissed |
| 4.2-D4 | Keyboard navigation: existing components need tabIndex audit | High | App-wide accessibility audit (Story 5.2) | Dana+Elena | **Wave 1** |
| 4.2-D5 | Focus management inconsistent across components | High | Implement useFocusManagement hook | Elena | **Wave 1** |
| 4.2-D6 | Confidence badges not paired with color everywhere | Medium | Audit all confidence displays | Dana | Wave 2 |

### Story 4.3: Design Tokens, Accessibility & Visual Polish

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 4.3-D1 | Confidence always paired with numeric badge — UI components ready, app-wide update needed | High | Audit all 5 confidence-gated components | Dana | **Wave 1** |
| 4.3-D2 | Graceful degradation messages implemented — UI components ready, app-wide update needed | High | Add calm indicators to all error states | Elena | **Wave 1** |
| 4.3-D3 | Amber 400 used for narrative moments — verify no interactive elements use it | Medium | CSS lint rule for color usage | Charlie | Wave 2 |
| 4.3-D4 | Cyan 400 reserved for interactive — audit for false positives | Medium | Manual audit + documentation | Dana | Wave 2 |

### Story 4.4: Latency, Fallback & Cross-Browser Validation

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 4.4-D1 | Memory budget validation (NFR-6 to NFR-8) not implemented | High | Requires HF Space deployment — run scripts/benchmark_latency.py | Deepu | **Wave 1** |
| 4.4-D2 | Player ID accuracy (NFR-11) not implemented | High | Requires HF Space deployment — vision model test | Deepu | **Wave 1** |
| 4.4-D3 | Cross-browser test script uses simulations not real browsers | Medium | Add Playwright/Selenium for real browser automation | Elena | Wave 2 |
| 4.4-D4 | VALIDATION_REPORT.md sections incomplete | High | Requires actual benchmark runs on deployed Space | Deepu | **Wave 1** |
| 4.4-D5 | Fallback capability tests always succeed — simulation by design | Low | Known limitation — tests verify logic, not GPU behavior | Dana | Deferred |
| 4.4-D6 | STT timeout test uses 0.5s not 15s | Low | Known limitation acknowledged in comment | Dana | Deferred |
| 4.4-D7 | Queue size magic number (3) | Low | Pre-existing design choice — document in constants | Elena | Deferred |
| 4.4-D8 | No external dependency failure testing | Low | Simulation isolates logic by design | Dana | Deferred |
| 4.4-D9 | No rate limit handling tested | Low | Pre-existing test gap | Dana | Deferred |
| 4.4-D10 | No race condition testing | Medium | Pre-existing gap — add concurrent test scenarios | Charlie | Wave 3 |
| 4.4-D11 | No concurrent WebSocket connection tests | Medium | Pre-existing gap — add multi-client test | Charlie | Wave 3 |
| 4.4-D12 | No shared state corruption tests | Medium | Pre-existing gap | Charlie | Wave 3 |
| 4.4-D13 | Sequential benchmark execution | Low | Pre-existing design — parallelize if needed | Dana | Deferred |
| 4.4-D14 | JSON output not tested | Low | Pre-existing test gap | Dana | Deferred |
| 4.4-D15 | No type validation on measurements | Low | Type hints present, runtime validation not in scope | Charlie | Deferred |
| 4.4-D16 | P95/P99 index calculation edge case for n=1 | Low | Works correctly, just statistically meaningless | Dana | Deferred |
| 4.4-D17 | Timezone-aware datetime comparison with historical naive timestamps | Low | Potential future issue, not caused by current diff | Charlie | Deferred |
| 4.4-D18 | Division by zero in FPS calculation | Low | Already handled with guard at line 251 | Dana | Dismissed |
| 4.4-D19 | Import may be unused elsewhere | Low | False alarm — timezone IS used in all 5 locations | Charlie | Dismissed |

---

## Epic 1-3 Deferred Findings (Retroactively Captured)

### Epic 1: Core Streaming & Notes Intelligence

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 1-D1 | 3-tier confidence gating not documented (binary threshold used) | Medium | Document pattern in conventions.md | Charlie | Wave 2 |
| 1-D2 | WebSocket message schemas inconsistent (gameState inclusion) | Medium | Audit and standardize (Story 5.6) | Dana | **Wave 1** |
| 1-D3 | No integration tests for 3-layer stats fallback chain | Low | Add integration tests | Elena | Wave 3 |

### Epic 2: Fan Q&A — Ask & Understand

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 2-D1 | Pre-computed Q&A pairs generation not documented | Medium | Document in Story 5.7 | Charlie | Wave 2 |
| 2-D2 | No calm degradation message for low-confidence player ID | Low | Add uniform degradation pattern | Elena | Wave 3 |
| 2-D3 | No integration test for Q&A end-to-end latency with real STT+LLM | High | Add integration test (Story 5.4) | Dana | **Wave 1** |

### Epic 3: Commentator Dashboard & Personalization

| ID | Finding | Severity | Recommended Fix | Owner | Status |
|----|---------|----------|-----------------|-------|--------|
| 3-D1 | Commentary settings not persisted to localStorage | Medium | Add persistence (Story 5.3) | Charlie | Wave 2 |
| 3-D2 | Teleprompter mode switching (Tabbed vs. Long-Sheet) not explicit | Low | Add mode indicator UI | Elena | Wave 3 |
| 3-D3 | Spanish translation quality not validated by native speaker | High | Human review (Story 5.8) | Alice | **Wave 1** |

---

## Wave 1 Critical Items (Must Fix Before Demo)

These items will cause demo failure or broken UX if not addressed:

1. **4.2-D4/D5** — App-wide accessibility audit (Story 5.2)
2. **4.3-D1/D2** — Confidence badges + graceful degradation rollout (Story 5.2)
3. **4.4-D1/D2/D4** — HF Space deployment validation (Story 5.4)
4. **1-D2/5.6** — WebSocket schema audit (Story 5.6)
5. **2-D3** — Q&A integration test (Story 5.4)
6. **3-D3** — Translation quality review (Story 5.8)
7. **5.5** — Story status hygiene (update 4.1, 4.2, 4.3 to done)

---

## Action Plan

**Wave 1 (Critical — Before Demo):**
- [ ] Story 5.1: Create this tracker ✅ Complete
- [ ] Story 5.4: Deploy HF Space, run validation scripts
- [ ] Story 5.5: Update sprint-status.yaml ✅ Complete
- [ ] Story 5.2: Accessibility audit + fixes
- [ ] Story 5.6: WebSocket schema audit
- [ ] Story 5.8: Translation review

**Wave 2 (High — For Polish):**
- [ ] Story 5.3: Commentary settings persistence
- [ ] Story 5.7: Pre-computed Q&A documentation
- [ ] 4.3-D3/D4: Color usage audit
- [ ] 1-D1: Document 3-tier confidence pattern

**Wave 3 (Nice-to-Have):**
- [ ] 4.4-D10/D11/D12: Race condition + concurrent tests
- [ ] 2-D1: Pre-computed Q&A documentation
- [ ] 1-D3: Stats fallback integration tests
- [ ] 3-D2: Teleprompter mode indicator

---

## Notes

- **Critical** = Demo will fail without fix
- **High** = Should fix for polish, but demo can proceed
- **Medium** = Nice-to-have, fix if time permits
- **Low** = Documented for future work

**Last Updated:** 2026-05-05  
**Next Review:** After Story 5.4 deployment validation
