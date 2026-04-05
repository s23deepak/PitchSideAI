# PitchAI — Codebase Structure Map

Last updated: April 2026

---

## Top-Level Layout

```
PitchAI/
├── agents/                        # All agent implementations
│   └── specialized_commentary/    # 7-agent Peter Drury notes pipeline
├── api/                           # FastAPI server + endpoints
├── config/                        # Typed config package (dataclasses + sport definitions)
├── config.py                      # Runtime config entry-point (loads .env over defaults)
├── config_prod.py                 # Production variant of runtime config
├── core/                          # Shared infrastructure: logging, concurrency, exceptions
├── data_sources/                  # Data retrievers, factory, and TTL cache
├── frontend/                      # React + Vite + Tailwind UI
│   └── src/components/            # 6 components: CommentaryFeed, CommentaryNotesViewer,
│                                  #   EventFeed, MatchNotes, PushToTalk, TacticalOverlay
├── orchestration/                 # WorkflowOrchestrator engine + shared types
├── rag/                           # OpenSearch-backed RAG (semantic/keyword/hybrid)
├── tools/                         # External service integrations (DynamoDB, vector store)
├── workflows/                     # LangGraph state machine + CrewAI config + bridge
├── k8s/                           # Kubernetes manifests
├── AGENTS.md                      # Agent guide for all AI IDEs
├── AGENTS_ARCHITECTURE.md         # Agent class hierarchy + method signatures
└── ARCHITECTURE.md                # System overview
```

---

## Agent Layer (`agents/`)

```
agents/
├── base.py                        # BaseAgent ABC — all agents extend this
├── research_agent.py              # ResearchAgent: pre-match briefs + grounded live Q&A
├── vision_agent.py                # VisionAgent: frame analysis + full/native-window/fallback video tactics (Nova Lite)
├── live_agent.py                  # LiveAgent: session mgmt + real-time Q&A (Nova Sonic)
├── commentary_agent.py            # CommentaryAgent: live/tactical/post-match text (Nova Pro)
└── specialized_commentary/
    ├── player_research_agent.py   # 25-player squad profiles via ESPN + FBref + Wikipedia
    ├── team_form_agent.py         # W/D/L form + home/away splits + Nova Pro synthesis
    ├── historical_context_agent.py# H2H records + Tavily storylines → narrative
    ├── weather_context_agent.py   # Match-day weather → sport-specific impact
    ├── matchup_analysis_agent.py  # 1v1 battles + positional strength comparison
    ├── news_agent.py              # Injuries/suspensions via ESPN + Tavily
    └── note_organizer_agent.py    # Final 5-page Markdown + structured JSON notes + tactical_brief
```

**Execution model**: `specialized_commentary` agents run in parallel groups:
- Group 1 (parallel): PlayerResearch, TeamForm, Weather, News, Historical
- Group 2 (after Group 1): Matchup (needs player data)
- Group 3 (after Group 2): NoteOrganizer (synthesis)

---

## Configuration Layer (`config/`)

```
config/
├── sports.py           # SportConfig dataclass + SPORTS_CONFIG dict (5 sports)
│                       # Single source of truth for tactical labels, metrics, positions
├── prompts.py          # SystemPrompts — dynamic prompt generation from SportConfig
├── commentary_config.py# 4 config dataclasses: DATA_RETRIEVAL, NOTE_GENERATION,
│                       #   OUTPUT, WORKFLOW — all env-var overridable
└── defaults.py         # Non-secret defaults: model IDs, server params, rate limits
```

**Rule**: Never hardcode sport strings in agents — always call `get_sport_config(sport)`.

**Backend routing**:
- `LLM_BACKEND` sets the default backend for all agents
- `COMMENTARY_NOTES_LLM_BACKEND` overrides the 7-agent notes workflow
- `VISION_LLM_BACKEND` overrides `VisionAgent` for frame/video analysis
- Native-video retry tuning is controlled by `NATIVE_VIDEO_WINDOW_SECONDS`, `NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS`, and `NATIVE_VIDEO_MAX_WINDOWS`

---

## Data Sources Layer (`data_sources/`)

```
data_sources/
├── factory.py                    # Singleton factory: get_retriever(sport) → BaseRetriever
├── base.py                       # BaseRetriever Protocol (7-method interface)
├── cache.py                      # TTL cache + @cache.cached("ns", ttl=N) decorator
├── data_cache.py                 # Lightweight duplicate (legacy) — prefer cache.py
├── espn_retriever.py             # ESPN unofficial API: squads, form, news, H2H
├── fbref_retriever.py            # FBref via soccerdata: player/team stats, xG, xAG
├── football_data_retriever.py    # football-data.org API v4: standings, H2H, squads
├── tavily_search_service.py      # Tavily AI search: news, storylines, managers, lineups
├── weather_retriever.py          # Match-day weather + forecast via Tavily search
├── wikipedia_retriever.py        # Player bios via Tavily + wikipedia package
├── sports_specific_retriever.py  # Composition layer: lineups, tactics, transfers
├── cricbuzz_retriever.py         # Cricket stub (satisfies Protocol; not yet implemented)
└── goal_retriever.py             # Goal.com stub (satisfies Protocol; ESPN used instead)
```

**Factory routing**: `get_retriever("cricket")` → `CricbuzzRetriever`, all others → `ESPNDataRetriever`.

---

## Workflows Layer (`workflows/`)

```
workflows/
├── commentary_notes_workflow.py   # LangGraph-style state machine
│                                  # CommentaryNotesState dataclass + WorkflowPhase enum
│                                  # Orchestrates 7 agents across 4 phases
├── crewai_config.py               # AgentRole dataclasses (role, goal, backstory, tools)
│                                  # CREW_CONFIG + TASK_DEFINITIONS for all 7 agents
└── orchestration_bridge.py        # Adapter: workflow ↔ WorkflowOrchestrator
│                                  # Translates tasks into orchestrator submissions
```

**Layer responsibilities**:
- LangGraph: state + execution order + phase transitions
- CrewAI: agent personas + task definitions
- Bridge: submits to `WorkflowOrchestrator` for concurrency/rate control

---

## Orchestration Engine (`orchestration/`)

```
orchestration/
├── engine.py    # WorkflowOrchestrator: task queue, asyncio.Semaphore, agent dispatch
│               # get_orchestrator() — module-level singleton
└── types.py     # AgentType, WorkflowState, WorkflowContext, AgentMessage, TaskResult
```

---

## Core Infrastructure (`core/`)

```
core/
├── logging.py      # AppLogger (structlog) + get_logger()
├── concurrency.py  # TokenBucket rate limiter + get_rate_limiter()
└── exceptions.py   # Typed exception hierarchy + get_error_response()
```

---

## RAG Layer (`rag/`)

```
rag/
└── __init__.py     # AdvancedRAGRetriever: semantic/keyword/hybrid/rerank strategies
                    # Amazon OpenSearch Serverless with SigV4; in-memory fallback
                    # get_rag_retriever() — singleton factory
```

---

## Tools (`tools/`)

```
tools/
├── dynamodb_tool.py    # write_event() + get_recent_events() — AWS DynamoDB
│                       # Gated on LLM_BACKEND == "bedrock" (no-op in local dev)
├── vector_store.py     # upsert_match_notes() + retrieve_relevant_context()
│                       # OpenSearch k-NN; in-memory fallback when unconfigured
├── search_tool.py      # Legacy Google/Gemini grounding tools (inactive)
└── firestore_tool.py   # Legacy GCP Firestore tool (inactive — superseded by DynamoDB)
```

---

## API Layer (`api/`)

```
api/
└── server.py    # FastAPI app with lifespan, CORS, GZip, rate limiting
                 # ConnectionManager — tracks WS connections per session_id, broadcasts
                 # _periodic_commentary() — asyncio task, fires every 60 s per session
                 # /api/v1/video/analyze tries: full native clip -> windowed native clip -> sampled frames
                 # Response includes native_video_enabled, native_video_used, analysis_path, fallback_reason
                 # Endpoints:
                 #   GET  /health  GET  /status
                 #   POST /api/v1/research
                 #   POST /api/v1/frame/analyze
                 #   POST /api/v1/video/analyze
                 #   POST /api/v1/query
                 #   POST /api/v1/commentary/prepare-notes
                 #   GET  /api/v1/events          (JSON, fetch-based)
                 #   GET  /api/v1/events/stream   (SSE push, 3 s interval)
                 # WebSocket /ws/live:
                 #   Client sends: init | match_event | tactical_detection | query (text) | audio (binary)
                 #   Server sends: commentary (broadcast) | answer (targeted)
```

---

## Frontend (`frontend/src/`)

```
src/
├── App.jsx                            # Root app — WebSocket lifecycle, liveCommentary state,
│                                      #   sendMatchEvent(), sendTacticalDetection(), wsRef
├── components/
│   ├── CommentaryFeed.jsx             # Live commentary panel + analyst-note cards + manual input
│   ├── CommentaryNotesViewer.jsx      # Renders Markdown/Tactical Brief/JSON commentary notes output
│   ├── EventFeed.jsx                  # DynamoDB event feed — SSE (not polling)
│   ├── MatchNotes.jsx                 # Match notes card
│   ├── PushToTalk.jsx                 # Audio interface for LiveAgent WebSocket
│   └── TacticalOverlay.jsx           # Frame upload → sends tactical_detection on confidence > 0.6
```

---

## Key Cross-Cutting Concerns

| Concern | Where |
|---|---|
| LLM dispatch (Bedrock/Ollama/OpenAI/vLLM) | `agents/base.py` → `BaseAgent.call_bedrock()` |
| Per-agent backend overrides | `agents/base.py` → `_resolve_backend()` using `COMMENTARY_NOTES_LLM_BACKEND` and `VISION_LLM_BACKEND` |
| Sport parameterisation | `config/sports.py` → `get_sport_config()` |
| Caching | `data_sources/cache.py` → `@cache.cached()` |
| Rate limiting | `core/concurrency.py` + `api/server.py` |
| Structured logging | `core/logging.py` → `get_logger()` |
| Event persistence | `tools/dynamodb_tool.py` |
| Vector search | `rag/__init__.py` + `tools/vector_store.py` |
| Error types | `core/exceptions.py` |
| WebSocket session management | `api/server.py` → `ConnectionManager` |
| Running commentary broadcast | `api/server.py` → `_periodic_commentary()` + `ConnectionManager.broadcast()` |
| Real-time event push (frontend) | `api/server.py` `/api/v1/events/stream` → `EventFeed.jsx` `EventSource` |
