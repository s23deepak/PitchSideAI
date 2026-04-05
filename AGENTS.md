# PitchAI — Agent Guide

> For AI IDEs: Gemini CLI, Codex, OpenAI Agents, Cursor, Windsurf, Cline, Aider.
> Claude Code users: see `CLAUDE.md` (if present) or this file applies equally.

---

## Must-Read First

Before writing any code, read:
- `ARCHITECTURE.md` — system overview
- `AGENTS_ARCHITECTURE.md` — agent class hierarchy and method signatures
- `config/sports.py` — sport config (drives ALL agent behavior)
- `config/prompts.py` — dynamic prompt templates

---

## Project Overview

**PitchSide AI** is a multi-agent sports commentary and analysis system built around AWS Bedrock, with optional OpenAI-compatible local and self-hosted backends.

Core capabilities:
- Pre-match research briefs (ResearchAgent → RAG-indexed)
- Real-time frame/tactical analysis (VisionAgent → Nova Lite)
- Native clip-level video analysis on Bedrock and vLLM, with overlapping native-window retries and sampled-frame fallback when needed
- Live fan Q&A during matches (LiveAgent → Nova Sonic)
- **Running commentary** — event-driven + periodic (LiveAgent via WebSocket)
- **Live tactical analyst notes** — explicit `tactical_detection` messages broadcast before generated tactical commentary
- Play-by-play and post-match commentary (CommentaryAgent → Nova Pro)
- Peter Drury-style commentary notes (7-agent workflow via LangGraph + CrewAI)

---

## Architecture at a Glance

```
agents/
├── base.py                        # BaseAgent — extend this, never bypass
├── research_agent.py              # ResearchAgent (Nova Pro)
├── vision_agent.py                # VisionAgent (Nova Lite)
├── live_agent.py                  # LiveAgent (Nova Sonic)
├── commentary_agent.py            # CommentaryAgent (Nova Pro)
└── specialized_commentary/        # 7-agent notes workflow
    ├── player_research_agent.py
    ├── team_form_agent.py
    ├── historical_context_agent.py
    ├── weather_context_agent.py
    ├── matchup_analysis_agent.py
    ├── news_agent.py
    └── note_organizer_agent.py

config/
├── sports.py                      # SportConfig dataclass — single source of truth
├── prompts.py                     # SystemPrompts — dynamic, sport-aware
└── commentary_config.py           # NOTE_GENERATION, WORKFLOW, OUTPUT, DATA_RETRIEVAL

data_sources/
├── cache.py                       # TTL cache + @cache.cached() decorator
├── espn_retriever.py
├── weather_retriever.py
├── sports_specific_retriever.py
└── wikipedia_retriever.py

workflows/
├── commentary_notes_workflow.py   # LangGraph state machine
├── crewai_config.py               # CrewAI agent roles and tasks
└── orchestration_bridge.py        # Bridge: CrewAI/LangGraph ↔ WorkflowOrchestrator

api/
└── server.py                      # FastAPI — ConnectionManager, /ws/live, scoped /api/v1/events/stream

frontend/src/components/
├── CommentaryFeed.jsx             # Live commentary panel + manual event input
├── CommentaryNotesViewer.jsx      # Markdown + Tactical Brief + structured JSON tabs
├── EventFeed.jsx                  # DynamoDB event feed (SSE, not polling)
├── TacticalOverlay.jsx            # Frame upload or video clip upload → sends tactical_detection on confidence > 0.6
└── ...                            # Other components
```

---

## Critical Rules

### DO
- **Always extend `BaseAgent`** — it provides `call_bedrock()`, error handling, logging, and retry
- **Always use `config/sports.py`** — never hardcode sport-specific strings in agents
- **Use `@cache.cached("namespace", ttl=3600)`** for any data retrieval that can be cached
- **Use `asyncio.gather(..., return_exceptions=True)`** for parallel agent execution
- **Log to DynamoDB** via `tools.dynamodb_tool.write_event()` for structured event tracking
- **Add new sports** by updating `SportConfig` in `config/sports.py` only — agents adapt automatically

### DON'T
- Don't call Bedrock directly — use `self.call_bedrock()` from BaseAgent
- Don't hardcode sport names, formations, tactical labels, or positions in agent logic
- Don't mix LangGraph state management with CrewAI coordination — they have distinct roles
- Don't skip the orchestration bridge — all CrewAI/LangGraph workflows must route through `WorkflowOrchestrator`
- Don't bypass backend abstraction — Bedrock, Ollama, OpenAI, and vLLM must all route through `BaseAgent`

---

## Model Assignments

| Agent | Model | Why |
|---|---|---|
| ResearchAgent | Nova Pro | Deep text reasoning |
| VisionAgent | Nova Lite | Low-latency image analysis |
| LiveAgent | Nova Sonic | Real-time audio/text |
| CommentaryAgent | Nova Pro | Broadcast-quality generation |
| Specialized commentary agents | Nova Pro | Note synthesis |

---

## Workflow Patterns

### Adding a New Agent
1. Create file in `agents/` or `agents/specialized_commentary/`
2. Extend `BaseAgent`
3. Implement `async execute(...)` as the primary entry point
4. Add sport-aware prompts via `SystemPrompts` in `config/prompts.py`
5. Register with orchestrator in `api/server.py`

### Adding a New Data Source
Follow the ESPN retriever pattern:
1. Create `data_sources/<name>_retriever.py`
2. Add TTL cache with `@cache.cached()`
3. Include mock fallback for when APIs are unavailable
4. Inject into `orchestration_bridge.py`

### Adding a New Sport
Only touch `config/sports.py`:
```python
class SportType(str, Enum):
    NEW_SPORT = "new_sport"

SPORTS_CONFIG[SportType.NEW_SPORT] = SportConfig(
    sport_type=SportType.NEW_SPORT,
    display_name="New Sport",
    tactical_labels=[...],
    key_metrics=[...],
    research_topics=[...],
    team_positions=[...]
)
```
All agents adapt automatically. No other changes needed.

---

### Running Commentary Session

The `/ws/live` WebSocket runs a full bidirectional session once a match is started:

```
Client → {"type":"init","home_team":"...","away_team":"...","sport":"..."}
Server → {"type":"ready",...}

Client → {"type":"match_event","description":"Haaland scores! 34'"}
Server → {"type":"commentary","text":"...","source":"event","timestamp":"..."}  (broadcast to all tabs)

Client → {"type":"tactical_detection","analysis":{"tactical_label":"High Press",...}}
Server → {"type":"commentary","text":"Analyst note: ...","source":"detection","timestamp":"..."}
Server → {"type":"commentary","text":"...","source":"analysis","timestamp":"..."}

Client → {"type":"query","text":"Who is leading?"}
Server → {"type":"answer","text":"...","timestamp":"..."}  (reply to sender only)

Server → {"type":"commentary","source":"timer",...}  (every 60 s, automatic)
```

Vision detections now send an explicit analyst note when `confidence > 0.6`, followed by generated tactical commentary for the same session. DynamoDB event reads are scoped by a deterministic `match_session` key so event feeds stay match-specific.
When `LLM_BACKEND=bedrock`, or when `LLM_BACKEND=vllm` with a video-capable `VLLM_VISION_MODEL`, `VisionAgent` can analyze uploaded video bytes natively. If a full vLLM clip exceeds the context window, the backend retries the clip as overlapping native-video windows before falling back to sampled frames. Ollama and other unsupported backends still receive sampled frames as a temporal fallback, so video uploads remain functional in local development.

---

### Build / Run / Test

```bash
# Backend
cd /home/deepu/PitchAI
source .venv/bin/activate
uvicorn api.server:app --reload

# Frontend
cd frontend && npm run dev

# Commentary notes workflow
POST /api/v1/commentary/prepare-notes
{
  "home_team": "Manchester City",
  "away_team": "Liverpool",
  "sport": "soccer"
}

# Test running commentary
# 1. Load UI → fill teams → Generate Commentary Notes (sets matchReady)
# 2. WebSocket opens automatically to /ws/live
# 3. Upload a frame or short clip in TacticalOverlay → analyst note and tactical commentary fire if confidence > 0.6
# 4. Type a match event in CommentaryFeed input → commentary fires immediately
# 5. Wait 60 s → periodic commentary fires automatically
# 6. Open EventFeed → SSE connection at /api/v1/events/stream (visible in DevTools)
```

---

## Performance Targets

| Operation | Target |
|---|---|
| Frame analysis | 2–3s (Nova Lite) |
| Research brief | 5–10s (Nova Pro) |
| Live query | 2–4s |
| Running commentary (per event) | 3–5s end-to-end |
| Periodic commentary interval | 60 s (configurable) |
| Commentary notes workflow | 30–60s end-to-end |
| EventFeed SSE push latency | ≤3 s |
| Max concurrent tasks | 20 (orchestrator limit) |
| Cache hit rate | ~60% (1hr TTL) |

---

## Think → Act → Reflect

Before writing code on tasks involving agent behaviour, prompts, or workflow changes:
1. **Think**: Read the relevant `config/sports.py` and `config/prompts.py` first
2. **Act**: Make the smallest change that solves the problem
3. **Reflect**: Does it work for all sports, not just the one being tested?

---

*Architecture Version: 2.0 | Stack: Python 3.12, FastAPI, AWS Bedrock, LangGraph, CrewAI*
