# AGENTS.md — PitchSideAI Development Conventions

## Project Overview

PitchSideAI is an AI football broadcast companion for the AMD Developer Hackathon (May 4–10, 2026).
Real-time commentary notes, live tactical vision Q&A, and Fan Lens broadcast mode.

**Quick Start:**
```bash
cd /home/deepu/PitchSideAI
source .venv/bin/activate

# Backend
python -m uvicorn api.server:app --reload --port 8000

# Frontend
cd frontend && npm run dev   # http://localhost:5173
```

---

## Agent Routing

| Task | Use Agent |
|---|---|
| FastAPI endpoints, WebSocket, agents/, workflows/, data_sources/ | `backend-engineer` |
| React components, design tokens, context, layouts | `frontend-engineer` |
| Feature spanning both frontend + backend | `fullstack-engineer` |
| Before any PR or story completion | `code-review-specialist` |
| After ANY UI file change | `ui-design-auditor` (proactive) |
| E2E API contract verification | `integrator-qa` |
| New UI screens from scratch | `ui-generator` → `ui-evaluator` → `frontend-engineer` |
| Playwright visual tests for core UI flows | `frontend-test-agent` |
| 7-agent notes pipeline bugs / slowness | `pipeline-debugger` |
| StatsBomb / ESPN / Transfermarkt data issues | `sports-domain-expert` |
| Docker, HF Space, vLLM server, environment config | `devops-agent` |

---

## Design System

**Midnight Stadium v3.0** — canonical source: `frontend/src/design-tokens/tokens.css`
Screen references now live in the React layouts and Playwright coverage.

| Token | Value |
|---|---|
| Background | `#131313` |
| Surface | `#1a1a1a` |
| Surface raised | `#222222` |
| Primary / Electric Lime | `#CCFF00` |
| Gold | `#FFD700` |
| Text primary | `#FFFFFF` |
| Text secondary | `#A0A0A0` |
| Danger | `#FF4444` |

**Fonts:** Inter (UI body), Space Grotesk (headings/display)
**Grid:** 4px base unit
**FORBIDDEN CSS:** gradient buttons, frosted glass/backdrop-filter, glowing orbs, colored card borders, `background: linear-gradient` on surfaces, centered-everything layouts, gradient text

---

## Architecture Quick Reference

### LLM Backend
Set `LLM_BACKEND` in `.env`:
- `openai` — cloud (gpt-4o-mini)
- `vllm` — local/self-hosted default (Qwen2.5/Qwen2.5-VL via `VLLM_BASE_URL`)

`COMMENTARY_NOTES_LLM_BACKEND` overrides for notes agents only.
`VISION_LLM_BACKEND` overrides for vision agents only.

### Vision Pipeline (Level 1→4 fallback chain)
- Level 1: StreamingVLM — requires MI300X/H100 (192GB VRAM). **Not available on consumer GPU.**
- Level 2: SGLang KV sliding window — activate by setting `SGLANG_BASE_URL`. Code-complete.
- Level 3: Not implemented — falls through to Level 4 automatically.
- Level 4: vLLM frame-by-frame at `VLLM_BASE_URL` — **active path on consumer hardware.**

Endpoint: `POST /ws/video/streaming` with `use_fallback_chain=True`

### WebSocket `/ws/live`
Single state bus per session. Client messages: `init`, `settings_update`, `language_switch`,
`match_event`, `tactical_detection`, `query`.
Server messages: `ready`, `status`, `commentary`, `trivia_card`, `beat_highlight`, `answer`, `error`.

### Notes Pipeline
7 agents in 3 sequential rounds. Agents: PlayerResearch, TeamForm, HistoricalContext,
WeatherContext, News, MatchupAnalysis, NoteOrganizer.
Endpoint: `POST /api/v1/commentary/prepare-notes` (SSE stream).

### Data Sources (round-robin)
ESPN → FootballData.org → Transfermarkt → OneVersusOne → Firecrawl
StatsBomb: **historical only** (La Liga 2004–2021, UCL, World Cup, Bundesliga 2023/24).

---

## Known Issues (Active Sprint)

1. **`call_llm` async blocking** — `agents/base.py` used to call boto3 synchronously.
   Now uses `_call_openai_compatible` for all backends. Confirm no blocking I/O remains.

2. **LiveSessionContext missing setters** — `FanLensBroadcast.jsx` destructures
   `setLiveCommentary` / `setDetection` — these must be exported from context.

3. **Duplicate WS management** — `App.jsx` AND `LiveSessionContext.jsx` both manage WebSocket.
   The `/dashboard` route uses App.jsx's local WS; `/live` routes use LiveSessionContext.

4. **CommentatorLayout.tsx orphaned** — exists but not imported by CommentatorDashboard.jsx.

5. **Fan Lens visual gaps** — scoreboard overlay, language toggle pill, vignette missing.

6. **`@/components/ui/Tabs` missing** — imported by TabbedLivePage.tsx but doesn't exist.

---

## File Layout (key paths)

```
api/server.py                    # FastAPI app — all endpoints + WS handlers
agents/base.py                   # BaseAgent: call_llm() dispatch, guardrail
agents/qa_agent.py               # Q&A agent (Epic 2, 46 unit tests)
workflows/commentary_notes_workflow.py  # 7-agent 3-round orchestration
models/game_state.py             # GameState: score, minute, phase, event log
data_sources/factory.py          # MultiSourceRetriever: 5-source round-robin
streaming/factory.py             # Fallback chain Level 1→4
frontend/src/contexts/LiveSessionContext.jsx  # WS state + SSE stream
frontend/src/pages/              # FanLensBroadcast, CommentatorDashboard, NotesGenerationHub
frontend/src/layouts/            # FanLensLayout.tsx, CommentatorLayout.tsx
frontend/src/design-tokens/tokens.css # Design system authority
frontend/src/layouts/                 # Core screen layout references
```

---

## Development Conventions

- All code changes validated by the relevant agent from `.Codex/agents/`
- UI changes: always run `ui-design-auditor` after, `frontend-test-agent` to verify
- No Bedrock/boto3 — use openai/vllm backends only
- No placeholder statistics in LLM prompts — enforced by guardrail in `agents/base.py`
- `asyncio.gather()` for parallel agent execution — never block the event loop
- `game_state.to_context_string()` prepended to every commentary LLM prompt
- Cache TTL patterns: stats 30min, historical 4h, squad 1h
