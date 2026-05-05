---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-05-04'
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/prd-validation-report.md"
  - "_bmad-output/planning-artifacts/ux-design-specification.md"
  - "_bmad-output/planning-artifacts/ux-design-directions.html"
  - "_bmad-output/brainstorming/brainstorming-session-2026-05-03.md"
  - ".context/streaming-vlm-research.md"
  - "ARCHITECTURE.md"
  - "AGENTS_ARCHITECTURE.md"
workflowType: 'architecture'
project_name: 'PitchAI'
user_name: 'Deepu'
date: '2026-05-04'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

The system spans 20 FRs across three pillars sharing one vision backbone:

- **Pillar 1 — Commentary Notes Engine (FR-01 to FR-06):** Multi-agent pipeline (7 agents, 3 phases) with progress callbacks over WebSocket. Dual-view rendering from single engine — full Markdown for Commentator Dashboard, 2-line trivia facts for Fan Lens. Vision-triggered note highlighting syncs teleprompter to match events. Pre-match generation from fixture input. Player identification via visual cues fused with lineup context.

- **Pillar 2 — Contextual Stream Q&A (FR-07 to FR-13):** Audio input via Browser Web Speech API (primary) with PushToTalk.jsx fallback. STT confidence-gated confirmation display (1.5s). Split-screen temporal navigation — live left, frozen frame with SVG overlays right. KV cache retention ≥ 120s for temporal grounding. Graceful fallback to static context when temporal nav unavailable. Auto-surfacing trivia cards (confidence > 0.6, fade 400ms in, display 5s, fade out). Same commentator voice for Q&A responses.

- **Pillar 3 — Cross-Language Commentary (FR-14 to FR-16):** Language toggle with < 3s switch, < 500ms audio gap. Meaning-preserving translation across languages (poetic register preserved, no cultural stereotype substitution). Trivia cards translate alongside commentary.

- **Shared / Platform (FR-17 to FR-20):** Three live-configurable commentary settings via sliders (Bias, Excitement, Knowledge Depth). Docker + React HF Space deployment with `VLLM_BASE_URL` Space secret. README YAML frontmatter for discoverability. Self-guided demo mode for community visitors.

**Non-Functional Requirements:**

| Category | NFRs | Key Metrics |
|----------|------|-------------|
| Latency | NFR-01 to NFR-05 | Q&A < 3.5s P95, language switch < 3s, cold start < 20s, commentary TTFT < 500ms, vision ≥ 5 FPS |
| Memory | NFR-06 to NFR-08 | HF Space container < 12GB RAM, MI300X VRAM < 60GB, KV cache ≥ 120s retention |
| Resilience | NFR-09 to NFR-10 | Fallback activation < 30s, endpoint configurable via single env var |
| Accuracy | NFR-11 | Player identification > 90% on known players |
| Deployment | NFR-12 | Single `git push` deployment |

**Scale & Complexity:**

- **Primary domain:** Real-time AI streaming + WebSocket-driven single-page application
- **Complexity level:** High — cascading dependency risk (vision backbone is SPOF across all three pillars), mixed workload orchestration (streaming prefill + on-demand decode + background batch on single GPU), 4-level fallback chain with documented capability loss per level
- **Estimated architectural components:** 12-15 major components spanning serving infrastructure (SGLang/vLLM), agent pipeline (7 agents), WebSocket state management, custom UI components (4 primary + SplitScreen), fallback chain orchestration, and deployment infrastructure

### Technical Constraints & Dependencies

1. **Single MI300X GPU (192GB HBM3):** All model inference — vision backbone, agent LLM, translation, potential TTS — must share this one device. VRAM budget capped at 60GB for models, leaving 132GB+ for KV cache expansion. No multi-GPU or CPU offload in scope.

2. **SGLang + StreamingVLM primary path, time-boxed at 1.5 days:** ROCm compatibility is the key unknown. StreamingVLM developed on NVIDIA H100 — custom attention kernels may need ROCm-compatible Flash Attention. If the ROCm port fails within 1.5 days, the system must degrade to the Custom KV Sliding Window fallback.

3. **Ranked Fallback Chain:**
   - Level 1: SGLang + StreamingVLM 7B (full capability)
   - Level 2: SGLang + Custom KV Sliding Window (loses StreamingVLM optimizations, retains temporal continuity)
   - Level 3: Pre-computed Vision Embeddings + vLLM (loses temporal scrub, Q&A degrades to static context)
   - Level 4: vLLM Frame-by-Frame (current baseline, no temporal continuity)

4. **Hugging Face Space (Docker + React):** Container RAM limited to 12GB before model loading. GPU models run exclusively on AMD droplet, not in Space container. Endpoint configurable via single `VLLM_BASE_URL` secret.

5. **6-day build window:** May 4-10, 2026. Day 1-2: environment + inference. Day 3-4: integration. Day 5: polish. Day 6: submit.

6. **Browser Web Speech API for audio:** Zero server-side STT latency. Recognition happens locally in browser. Football terminology correction layer (string map). PushToTalk.jsx + WebSocket binary audio as fallback.

7. **Existing codebase constraints:** FastAPI backend, React/Vite frontend, multi-agent architecture with BaseAgent, 3-layer stats fallback chain (StatsBomb → Firecrawl → FBref), WebSocket connection manager with GameState tracking, periodic commentary timer (60s).

### Cross-Cutting Concerns Identified

1. **KV Cache as shared resource:** The vision backbone's KV cache serves all three pillars — commentary note triggering, Q&A temporal grounding, and translation context. Cache sizing, eviction policy, and retention duration affect every feature. A single misconfiguration cascades.

2. **Confidence-gated progression pattern:** Five components (STT recognition, player identification, vision event detection, overlay rendering, teleprompter highlighting) all implement the same three-tier logic: high confidence → skip confirmation, medium → brief verification, low → reject/retry. This pattern must be consistent across the system.

3. **Graceful degradation at 4 levels:** Every component must define behavior at each fallback level. The UX must communicate degradation calmly ("Based on available footage") rather than alarming. Degraded modes are product states, not error states.

4. **Dual-view rendering from single engine:** Commentary notes engine produces two output formats (full Markdown + trivia facts) consumed by two different UI renderings (40% teleprompter + 5% corner cards). Same data, same WebSocket channel, different presentation logic.

5. **Mixed-workload GPU scheduling:** Streaming video prefill (compute-heavy, continuous), on-demand Q&A decode (latency-sensitive, sporadic), background commentary generation (batch, periodic). All three workload types compete for the same MI300X. Priorities and preemption must be designed.

6. **Demo provocation architecture:** In narrated demo mode, features surface at pre-planned moments. In Community Visitor mode, the UX alone must drive discovery — suggested question chips on first trivia card, always-visible controls tray, tooltips on first hover. Two different feature-surfacing strategies from the same codebase.

7. **WebSocket state as single source of truth:** All component state flows through `useWebSocket` hook. Reconnection with exponential backoff, state sync on reconnect, session management. Every component is a renderer of WebSocket state, not an independent state machine.

## Starter Template Evaluation

### Primary Technology Domain

Real-time AI streaming application with WebSocket-driven SPA. Existing codebase provides the application scaffold — the open architectural decisions are at the infrastructure layer.

### Established Technical Foundation

| Layer | Decision | Source |
|-------|----------|--------|
| Frontend framework | React 18 + Vite | Existing `frontend/` |
| Styling | Tailwind CSS + shadcn/ui (dark theme) | UX Design Spec |
| State management | `useWebSocket` hook with typed props | UX Design Spec |
| Backend framework | FastAPI + WebSocket (`/ws/live`) | Existing `api/server.py` |
| Agent architecture | 7 agents extending BaseAgent, 3-phase pipeline | Existing `agents/` |
| Stats retrieval | 3-layer chain: StatsBomb → Firecrawl → FBref | Existing `data_sources/factory.py` |
| Deployment target | Docker + Hugging Face Space | PRD FR-18 |
| GPU hardware | AMD MI300X (192GB HBM3), ROCm | Hackathon constraint |
| Base model | Qwen2.5-VL-7B-AWQ | Technical research |

### Open Infrastructure Decisions

**Serving Engine:**

| Option | Strengths | Risks |
|--------|-----------|-------|
| SGLang (primary) | RadixAttention for frame prefix reuse, lower TTFT, better streaming smoothness | Smaller community, less mature ROCm support |
| vLLM (fallback) | Mature ROCm support via `vllm-rocm`, already used in PitchAI, larger community | Higher TTFT, less prefix-sharing optimization |

**Streaming Vision Framework:**

| Option | Strengths | Risks |
|--------|-----------|-------|
| StreamingVLM (primary, 1.5-day time-box) | Designed for infinite video, same Qwen-VL family, compact KV-cache | NVIDIA H100 origin — ROCm port unproven |
| LiveVLM (alternative) | Training-free, works with off-the-shelf VLLMs, VSB + PaR | Built on LLaVA-OneVision, needs Qwen-VL port |
| Custom KV Sliding Window (fallback 2) | No external dependencies, full control | Loses StreamingVLM optimizations |
| Frame-by-Frame (fallback 4) | Already working in codebase | No temporal continuity |

### Selected Foundation

Based on the existing codebase, technical research, and 6-day hackathon constraint:

- **Serving engine:** SGLang primary, vLLM fallback (PRD Fallback Level 2-4)
- **Streaming vision:** StreamingVLM primary (1.5-day time-box), LiveVLM as backup experiment
- **Application scaffold:** Existing React/Vite + FastAPI codebase (no greenfield generate)
- **Deployment:** Docker + HF Space with `VLLM_BASE_URL` secret pointing to AMD droplet
- **Hardware assumption:** Single MI300X with ROCm; VRAM budget 60GB for models, 132GB+ for KV cache

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data Architecture: Structured Notes Store with deterministic lookup
- API & Communication: WebSocket protocol (existing, to be formalized)
- Infrastructure: Docker + HF Space deployment with GPU droplet endpoint

**Important Decisions (Shape Architecture):**
- Frontend: Custom component tree and state flow via `useWebSocket` hook (from UX spec)
- GPU Workload Scheduling: Priority-based prefill/decode sharing on single MI300X

**Deferred Decisions (Post-Hackathon):**
- Persistent storage for commentary notes (currently in-memory, per-session)
- FAISS / vector database for semantic retrieval (numpy cosine similarity sufficient for ~100 beats)
- Multi-language embedding pipeline
- Authentication and authorization (public HF Space for hackathon)

### Data Architecture

**Decision: Structured Notes Store with Deterministic Lookup + Raw Markdown Display**

Based on collaborative analysis (Advanced Elicitation + Party Mode review by Winston, Amelia, Mary, and Sally), the commentary notes output from the 7-agent pipeline is structured as follows:

```
NoteOrganizer → StructuredNotes (models/notes_store.py)
├── raw_markdown: str              → Teleprompter (WS broadcast, two display modes)
├── beats: List[NarrativeBeat]     → LookupTable (event_tag → beat_indices, O(1))
│   └── {text, event_tags, players, section, source, confidence}
├── lookup: Dict[str, List[int]]   → Pre-computed tag→beat mapping
└── index: Optional[numpy array]   → Cosine similarity fallback (stretch, ~3 lines)
```

**NarrativeBeat schema:**
- `text`: The narrative line (e.g., "Mbappé has scored 7 goals in his last 5 appearances...")
- `event_tags`: Normalized event labels (e.g., `["goal", "goal_scored", "attacking_play"]`)
- `players`: Player names mentioned (for `game_state` filtering)
- `section`: Which of the 5 notes pages this beat belongs to
- `source`: Data provenance (StatsBomb, Firecrawl, FBref)
- `confidence`: 0.0-1.0 (for trust-weighted highlighting)

**Retrieval Chain** (reuses `FallbackStatsRetriever._chain()` pattern from existing codebase):

1. Vision event detected (confidence > 0.6) → `tag_resolver.py` normalizes vision label to note tag vocabulary
2. Lookup table match — O(1) deterministic, covers ~80% of events
3. If no match → `game_state` active-player filter → numpy cosine similarity over beats (< 1ms for ~100 beats)
4. If still no match → full markdown context injected into LLM prompt (graceful degradation)

**Display Modes** (frontend-only toggle on same `raw_markdown` WebSocket data):

| Moment | Mode | Behavior |
|--------|------|----------|
| Pre-match review | Tabbed (5 sections) | Carlos reads critically, checks accuracy by section |
| Live match | Long-sheet (continuous scroll) | Carlos scans in < 1s, auto-scroll synced to match via vision triggers |

**Key Constraints:**
- No FAISS dependency — numpy dot product handles 100-beat search in < 1ms
- If embeddings are added later: separate CPU embedder (`all-MiniLM-L6-v2`, ~80MB) to avoid GPU contention with vision backbone
- `tag_resolver.py` is critical path — mismatched vocabularies cause silent fallback to full context with judge-visible latency
- `game_state` active-player filter applied between lookup and prompt injection to prevent stale notes after substitutions
- `source` field on every `NarrativeBeat` enables trust-building attribution on trivia cards (UX requirement)

**Integration Order** (from Amelia's review):
1. Add `NarrativeBeat` dataclass + `NotesStore` model in `models/notes_store.py`
2. Modify `NoteOrganizer` to return `NotesStore` with `raw_markdown` populated (backwards compatible via attribute accessor)
3. Wire lookup table into `LiveAgent.generate_live_commentary()` as optional `notes_store` parameter
4. Add numpy cosine similarity fallback only if Day 5 has slack

### API & Communication Patterns

**Decision: Extend existing WebSocket protocol with structured notes broadcast; state-snapshot reconnection; immediate settings application.**

**New Message Type — `notes_ready`:**

When the 7-agent pipeline completes pre-match generation, the server broadcasts metadata. Raw markdown and beats stay server-side (frontend receives commentary via existing broadcasts):

```json
{
  "type": "notes_ready",
  "beat_count": 100,
  "sections": ["match_info", "home_team", "away_team", "tactical", "historical"],
  "timestamp": "2026-05-04T..."
}
```

**WebSocket Reconnection:**

State snapshot approach for hackathon scope. On reconnect, server sends full `game_state` + last 3 commentary lines. No event replay infrastructure needed for a 5-minute demo session. Exponential backoff with jitter (from UX spec).

**Commentary Settings (FR-17):**

```json
{"type": "settings_update", "bias": 0.3, "excitement": 0.8, "knowledge_depth": 0.5}
```

Applied immediately on receive — server updates the prompt template, and the next commentary cycle (via `_periodic_commentary` or event trigger) uses the new settings. No queueing, no "apply" button.

**Complete WebSocket Protocol (formalized):**

| Direction | Message Type | Purpose |
|-----------|-------------|---------|
| Client → Server | `init` | Session setup (home_team, away_team, sport) |
| Client → Server | `match_event` | Manual event input (description text) |
| Client → Server | `tactical_detection` | Vision model analysis result |
| Client → Server | `query` | Fan Q&A text question |
| Client → Server | `settings_update` | Bias/excitement/knowledge sliders |
| Server → Client | `commentary` | Commentary text + `gameState` + `source` |
| Server → Client | `answer` | Q&A response text |
| Server → Client | `ready` | Session initialized confirmation |
| Server → Client | `notes_ready` | Pre-match notes generation complete (new) |
| Server → Client | `error` | Error with code + message |
| Server → Client | `state_snapshot` | Full state on reconnect (new) |

### Frontend Architecture

**Decision: Adopt UX spec component strategy with `useWebSocket` as single state source.**

The UX Design Specification (step 9, Component Strategy) defines 4 custom components fed by a single `useWebSocket` hook. This is adopted as the architecture standard:

```
useWebSocket (single state hook, typed props)
├── VideoCanvas     → Video + canvas overlay (5 FPS), integrated status dot
├── MicButton       → Hold-to-record, STT states, 15s timeout
├── MatchInsight    → TriviaCard + QuestionChips (merged), priority queue
├── Teleprompter    → Long-sheet/tabbed toggle, auto-scroll, hold mode
└── SplitScreen     → 60/40 Q&A split, SVG overlays, 300ms transitions
```

**State Flow:**
1. `useWebSocket` connects to `/ws/live`, receives all server broadcasts
2. Each component receives typed props derived from WebSocket state
3. Components are renderers, not state machines — no component-local polling
4. Reconnection handled in `useWebSocket`; components receive new state snapshot

**Implementation Phases** (from UX spec):

| Phase | Days | Components |
|-------|------|------------|
| Core | 1-2 | VideoCanvas, MicButton, `useWebSocket` hook |
| Fan Experience | 3-4 | MatchInsight, SplitScreen |
| Commentator Experience | 4-5 | Teleprompter (static mode first, auto-highlight second) |
| Polish | 5-6 | Animation tuning, accessibility, chaos testing |

**Design tokens:** Tailwind CSS dark theme (Slate 950 background), Amber 400 (narrative highlight), Cyan 400 (interactive), Inter + JetBrains Mono fonts, shadcn/ui for chrome components.

### Infrastructure & Deployment

**Decision: Docker multi-stage build → HF Space; GPU inference on separate AMD MI300X droplet; single `VLLM_BASE_URL` secret for endpoint configuration.**

**Docker Strategy:**

```
Dockerfile (multi-stage)
├── Stage 1: Frontend build (node, npm build → static dist/)
├── Stage 2: Backend (python:3.11-slim, FastAPI + uvicorn)
│   ├── COPY dist/ → serve static files
│   ├── COPY agents/ config/ data_sources/ models/ api/
│   └── HEALTHCHECK /health
└── Single container → HF Space (Docker SDK)
```

**GPU Endpoint Architecture:**

```
HF Space Container (12GB RAM limit)
├── React static files (nginx or FastAPI static mount)
├── FastAPI + WebSocket (/ws/live)
├── Agent pipeline (CPU-bound: stats retrieval, notes generation)
└── NO GPU models loaded

AMD MI300X Droplet (192GB HBM3)
├── SGLang + StreamingVLM (vision backbone)
├── Qwen2.5-VL-7B-AWQ (~7-9GB)
├── KV Cache buffer (~20-30GB)
├── Agent LLM context (~5-10GB)
└── Endpoint: http://<droplet-ip>:8000
```

Space container connects to GPU droplet via `VLLM_BASE_URL` secret. No model weights in the Space. Endpoint change requires Space restart (NFR-10: reconnect within 10s).

**Space Configuration:**

- `sdk: docker` (Dockerfile-based, not Gradio)
- `tags: [amd, amd-hackathon-2026, vllm, gradio]` (FR-19)
- README YAML frontmatter with setup instructions
- Self-guided demo mode with sample video + pre-generated notes (FR-20)

**GPU Workload Scheduling (Single MI300X):**

Three workload types compete for one GPU:

| Priority | Workload | Trigger | Budget |
|----------|----------|---------|--------|
| 1 (Highest) | Q&A Decode | Fan submits question | < 3.5s end-to-end |
| 2 | Streaming Prefill | Continuous video frames | 5 FPS minimum |
| 3 (Background) | Commentary Generation | 60s timer + event triggers | < 500ms TTFT |

SGLang's disaggregated prefill/decode handles priority 1 vs 2 naturally — decode can preempt prefill. Background commentary (priority 3) runs during gaps in streaming prefill. If StreamingVLM falls back to frame-by-frame (Level 4), all three workloads serialize — Q&A gets priority, prefill pauses during decode, commentary waits.

**Single Command Deploy (NFR-12):**

```bash
git push hf-space main
```

No manual SSH, no droplet-side config beyond initial SGLang endpoint startup.

## Implementation Patterns & Consistency Rules

### Naming Conventions

| Scope | Convention | Example |
|-------|-----------|---------|
| Python files | `snake_case` | `notes_store.py`, `tag_resolver.py` |
| Python classes | `PascalCase` | `NotesStore`, `NarrativeBeat` |
| Python functions/vars | `snake_case` | `get_notes_store()`, `beat_index` |
| React components | `PascalCase` | `Teleprompter.jsx`, `MatchInsight.jsx` |
| React hooks | `useCamelCase` | `useWebSocket` |
| WS message types | `snake_case` | `notes_ready`, `state_snapshot`, `settings_update` |
| WS message keys | `snake_case` in Python, `camelCase` in JS | `beat_count` → `beatCount` at bridge |
| REST endpoints | `/api/v{n}/{resource}` | `/api/v1/research` |

### Structural Conventions

```
models/          # Data structures (NarrativeBeat, NotesStore, GameState, GameEvent)
agents/          # Agent implementations (extend BaseAgent)
config/          # Sport configs, prompts
data_sources/    # Stats retrievers (factory pattern, 3-layer chain)
api/             # FastAPI server, WebSocket manager
frontend/src/components/  # React custom components
```

New `tag_resolver.py` goes in `models/` alongside `notes_store.py` — it operates on `NarrativeBeat` data and is not an independent agent.

### Format Standards

- **All WS broadcasts:** `{"type": "...", ...data, "timestamp": "ISO8601"}`
- **Error responses:** `{"type": "error", "code": "ERROR_CODE", "message": "..."}`
- **Progress callbacks:** `{"type": "progress", "agent": "PlayerResearch", "status": "running|complete|failed", "items": "22/25"}`
- **Date/time:** ISO 8601 strings throughout
- **Commentary always includes `gameState` object**
- **JSON bridge:** Python `snake_case` keys translated to JS `camelCase` at WebSocket boundary

### Confidence-Gated Progression

Applies uniformly to STT, vision event detection, player identification, and overlay rendering:

```python
def confidence_gate(value: float) -> str:
    if value > 0.9:  return "proceed"    # Skip confirmation
    if value >= 0.7: return "confirm"    # Brief verification (1.5s max)
    return "reject"                      # Auto-reject, prompt retry
```

### Retrieval Chain Pattern

Both `NotesStore.lookup()` and `FallbackStatsRetriever._chain()` use the same 3-layer pattern:

1. **Deterministic/tagged match** — O(1) lookup, no model call
2. **Semantic/embedding match** — lightweight (numpy cosine similarity), CPU-only
3. **Full context fallback** — LLM call, slowest, most capable

### Async Patterns

- **Parallel agents:** `asyncio.gather(*tasks, return_exceptions=True)`
- **Caching:** `@cache.cached("namespace", ttl=14400)` (4h TTL for stats)
- **Periodic tasks:** `asyncio.create_task(_periodic_commentary())` with cancellation on session close

### Game State Injection

```python
seed = f"{game_state.to_context_string()}\n\n{commentary_prompt}"
```

Always prepended to every commentary seed before calling `LiveAgent`. Never bypass.

### Agent Output Format

NoteOrganizer return type change (backwards compatible):

```python
# Old: async def execute(self, ...) -> str
# New: async def execute(self, ...) -> NotesStore
# Access raw markdown via notes_store.raw_markdown for backwards compat
```

### Enforcement Guidelines

**All agents MUST:**
- Extend `BaseAgent` and use `call_bedrock()` for LLM dispatch
- Include `gameState` in every commentary broadcast
- Use `asyncio.gather(return_exceptions=True)` for parallel agent execution
- Follow the 3-tier confidence gate for any user-facing AI output
- Emit progress callbacks in the standardized format
- Return `NotesStore` (not raw string) from the NoteOrganizer phase

**Pattern verification:**
- `ruff check` for Python style
- Existing WebSocket message format tests
- `NotesStore` type check at NoteOrganizer boundary

## Project Structure & Boundaries

### Complete Project Directory Structure

```
PitchAI/
├── api/
│   └── server.py                    # FastAPI + WS + ConnectionManager
│                                     #   Section-organized: routes, handlers, orchestration
├── agents/
│   ├── __init__.py
│   ├── base.py                      # BaseAgent (multi-backend dispatch)
│   ├── coordinator.py               # Agent execution order (3-phase pipeline)
│   ├── research_agent.py            # Pre-match research + Q&A
│   ├── vision_agent.py              # Frame analysis + tactical (imports streaming/)
│   ├── live_agent.py                # Live commentary + Q&A (imports models/notes_store)
│   └── commentary_agent.py          # Commentary generation
├── streaming/                       # Streaming vision infrastructure
│   ├── __init__.py
│   ├── factory.py                   # Streaming backend selection (SGLang/vLLM)
│   ├── sglang_client.py             # SGLang + StreamingVLM HTTP client
│   ├── frame_sampler.py             # Frame selection, FPS control, diversity scoring
│   └── kv_cache.py                  # KV cache window management, retention config
├── models/
│   ├── __init__.py
│   ├── game_state.py                # GameState, GameEvent, MatchPhase
│   ├── narrative_beat.py            # NarrativeBeat dataclass (pure data)
│   └── notes_store.py               # StructuredNotes + lookup + tag resolver
├── config/
│   ├── sports.py                    # Sport configs (6 sports)
│   └── prompts.py                   # Dynamic system prompts
├── data_sources/
│   ├── __init__.py
│   ├── factory.py                   # FallbackStatsRetriever (3-layer chain)
│   ├── statsbomb_retriever.py       # Historical exact-match
│   └── firecrawl_retriever.py       # Current-season scraping
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── hooks/
│       │   └── useWebSocket.js       # Single state hook (all component state)
│       └── components/
│           ├── VideoCanvas.jsx       # Video + canvas overlay + status dot
│           ├── MicButton.jsx         # Hold-to-record + STT states
│           ├── MatchInsight.jsx      # TriviaCard + QuestionChips merged
│           ├── Teleprompter.jsx      # Long-sheet/tabbed + auto-scroll
│           ├── SplitScreen.jsx       # 60/40 Q&A temporal navigation
│           ├── ControlsTray.jsx      # Language, Bias, Excitation, Knowledge
│           └── CommentaryFeed.jsx    # Live commentary text stream
├── scripts/
│   ├── generate_notes.py            # CLI: pre-match notes from fixture
│   └── deploy_hf.sh                 # Single-command HF Space deploy
├── Dockerfile                        # Multi-stage: frontend build + FastAPI
│                                     #   Build arg VLLM_BASE_URL for GPU endpoint
├── huggingface-space.yml             # HF Space metadata
├── requirements.txt
├── .env
└── .context/                         # Research docs (module_registry, conventions, etc.)
```

### Architectural Boundaries

**API Boundaries:**

| Boundary | Transport | Format |
|----------|-----------|--------|
| Frontend ↔ Backend | WebSocket `/ws/live` | JSON `{type, ...data, timestamp}` |
| Frontend ↔ Backend | REST `GET /health`, `/status` | JSON health response |
| Backend ↔ GPU Droplet | HTTP `/v1/chat/completions` | OpenAI-compatible API |
| Backend → Frontend (events) | SSE `/api/v1/events/stream` | Server-sent events, 3s poll |

**Component Boundaries:**

- `useWebSocket` hook is the single state boundary between server and all 7 React components
- Components receive typed props; never access WebSocket directly
- `VideoCanvas` owns the canvas draw loop (5 FPS); `SplitScreen` owns SVG overlay rendering
- `Teleprompter` and `MatchInsight` are independent renderers of the same structured notes data

**Service Boundaries:**

- `streaming/` is imported only by `agents/vision_agent.py` — vision agent depends on streaming infrastructure
- `models/notes_store.py` is imported by `agents/live_agent.py` and `api/server.py` — two consumers
- `data_sources/` is imported only by agents (not by `api/` directly)
- `config/` is imported everywhere — shared dependency, no boundary

**Data Boundaries:**

- Commentary notes live in-memory per WebSocket session (`NotesStore` instance)
- Match events persisted to DynamoDB (existing), scoped by `match_session` key
- KV cache lives on GPU droplet, not in Space container
- No cross-session data sharing (hackathon scope)

### Requirements to Structure Mapping

| Requirement Category | Primary Files |
|---------------------|---------------|
| FR-01 to FR-05 (Agent Pipeline) | `agents/coordinator.py`, `agents/research_agent.py`, `agents/commentary_agent.py`, `config/sports.py`, `data_sources/factory.py` |
| FR-06 (Player Identification) | `agents/vision_agent.py`, `streaming/frame_sampler.py`, `models/narrative_beat.py` |
| FR-07 to FR-13 (Q&A + Trivia) | `api/server.py`, `agents/live_agent.py`, `models/notes_store.py`, `frontend/src/components/MicButton.jsx`, `SplitScreen.jsx`, `MatchInsight.jsx` |
| FR-14 to FR-16 (Translation) | `agents/live_agent.py`, `config/prompts.py`, `frontend/src/components/ControlsTray.jsx` |
| FR-17 (Settings) | `api/server.py`, `frontend/src/components/ControlsTray.jsx`, `frontend/src/hooks/useWebSocket.js` |
| FR-18 to FR-20 (Deployment) | `Dockerfile`, `huggingface-space.yml`, `scripts/deploy_hf.sh` |
| Structured Notes (new) | `models/notes_store.py`, `models/narrative_beat.py` |
| Streaming Vision (new) | `streaming/sglang_client.py`, `streaming/frame_sampler.py`, `streaming/kv_cache.py`, `streaming/factory.py` |
| Stats Retrieval | `data_sources/factory.py`, `data_sources/statsbomb_retriever.py`, `data_sources/firecrawl_retriever.py` |

### Integration Points

**Internal Communication:**
- All backend-to-frontend state flows through WebSocket `/ws/live`
- Agent pipeline execution coordinated by `agents/coordinator.py`, progress broadcast via `ConnectionManager.broadcast()`
- Vision events trigger note lookup via `models/notes_store.py` → injected into `agents/live_agent.py` prompt

**External Integrations:**
- GPU inference: HTTP to SGLang droplet, configurable via `VLLM_BASE_URL` env var
- Stats data: StatsBomb API (historical), Firecrawl (current season), FBref (last resort)
- STT: Browser Web Speech API (client-side, no server integration)
- HF Space: Docker container, `sdk: docker`, Space secrets for `VLLM_BASE_URL`

**Data Flow:**
```
Video frames → streaming/frame_sampler.py → SGLang droplet → vision detections
                                                               ↓
7-agent pipeline → models/notes_store.py → api/server.py → WS broadcast → frontend components
                                                               ↓
Fan Q&A → agents/live_agent.py → models/notes_store.lookup() → LLM → WS answer broadcast
```

### File Organization Patterns

- **Flat packages until 5+ files** — `api/` stays single-file, `models/` stays 3 files, `config/` stays 2 files. Only `agents/` (6 files), `streaming/` (4 files), and `frontend/src/components/` (7 files) earn their directories.
- **Factory pattern for selectable backends** — `data_sources/factory.py` and `streaming/factory.py` follow the same pattern: select backend by config, return interface-conforming instance.
- **Pure data vs data+logic** — `models/narrative_beat.py` and `models/game_state.py` are pure dataclasses; `models/notes_store.py` adds retrieval logic. No separate subdirectories for hackathon scope.
- **Scripts for one-shot operations** — `scripts/generate_notes.py` (pre-match CLI) and `scripts/deploy_hf.sh` (deployment). Not importable; run directly.

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices work together — SGLang + StreamingVLM → Qwen2.5-VL-7B-AWQ on MI300X, React/Vite + Tailwind + shadcn/ui on HF Space, FastAPI + WebSocket bridging both. No version conflicts. No contradictory decisions.

**Pattern Consistency:** Three-tier confidence gate applies uniformly to 5 components (STT, vision detection, player ID, overlay rendering, teleprompter highlighting). Retrieval chain pattern (`deterministic → semantic → full context`) reused across NotesStore and FallbackStatsRetriever. Naming conventions are Python-native and React-standard throughout.

**Structure Alignment:** Streaming infrastructure isolated in `streaming/` with factory pattern matching `data_sources/`. Pure data classes separated from logic-bearing classes in `models/`. Frontend components are flat renderers consuming typed props from a single `useWebSocket` hook. All integration boundaries respected.

### Requirements Coverage Validation

**Functional Requirements (20/20 covered):**

| FR | Covered By | Status |
|----|-----------|--------|
| FR-01 to FR-05 (Agent Pipeline) | `agents/coordinator.py`, `data_sources/factory.py`, WS progress callbacks | Covered |
| FR-06 (Player Identification) | `agents/vision_agent.py`, `streaming/`, `models/narrative_beat.py` | Covered |
| FR-07 to FR-13 (Q&A + Trivia) | `SplitScreen`, `MicButton`, `MatchInsight`, `models/notes_store.py`, `agents/live_agent.py` | Covered |
| FR-14 to FR-16 (Translation) | `agents/live_agent.py`, `config/prompts.py`, `ControlsTray.jsx` | Covered |
| FR-17 (Settings) | WS `settings_update`, `ControlsTray.jsx`, prompt template injection | Covered |
| FR-18 to FR-20 (Deployment) | `Dockerfile`, `huggingface-space.yml`, `scripts/deploy_hf.sh` | Covered |

**Non-Functional Requirements (12/12 covered):**

| NFR Category | Addressed By | Status |
|-------------|-------------|--------|
| NFR-01-05 (Latency) | GPU priority scheduling, deterministic O(1) lookup, pre-loaded language prompts | Covered |
| NFR-06-08 (Memory) | VRAM budget 60GB, KV cache 20-30GB, Space container < 12GB, CPU embedder | Covered |
| NFR-09-10 (Resilience) | 4-level fallback chain, single `VLLM_BASE_URL` env var, 30s activation | Covered |
| NFR-11-12 (Accuracy, Deploy) | Confidence-gated player ID, `git push` single-command deploy | Covered |

### Implementation Readiness Validation

**Decision Completeness:** All critical decisions documented with rationale. Technology versions specified. Integration patterns defined. Performance budgets explicit and measurable.

**Structure Completeness:** Complete directory tree with 6 new files identified (`streaming/` package 4 files + `models/narrative_beat.py` + `models/notes_store.py`). All integration points mapped. Component boundaries defined.

**Pattern Completeness:** Naming conventions for Python and JavaScript documented. Format standards for all WebSocket message types specified. Confidence-gated progression standardized. Retrieval chain pattern reusable. Async patterns explicit.

### Gap Analysis Results

**No Critical Gaps.**

| Gap | Priority | Resolution |
|-----|----------|------------|
| `event_tags` taxonomy | Important → Resolved | 8 canonical tags defined. `tag_resolver` with 3-tier resolution: exact match → synonym/parent → substring → None (semantic fallback). `game_state` score-check gate for goal events. Taxonomy is ~40 lines of Python in `models/notes_store.py` |
| StreamingVLM ROCm port | Important → Mitigated | Time-boxed at 1.5 days. 4-level fallback chain documented with capability loss per level. Architecture supports all fallback levels without code change |

### Event Tags Taxonomy Contract

**Canonical Tags (8 for demo):**

`goal`, `yellow_card`, `red_card`, `substitution`, `foul`, `corner`, `free_kick_dangerous`, `offside`

**Resolution Order in `tag_resolver`:**
1. Exact canonical match
2. Synonym map match (vision-specific → canonical)
3. Parent tag match (child tag → parent)
4. Substring match (fuzzy bridge)
5. Return `None` → semantic/numpy fallback → full LLM context

**Safety Gate:** Before any "goal" tag fires, verify `game_state` score has changed. False goal calls are the highest-trust-cost failure mode.

### Architecture Completeness Checklist

**Requirements Analysis:**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions:**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns:**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure:**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — all 16 checklist items verified, all 20 FRs and 12 NFRs architecturally supported. The two identified risks (ROCm port, taxonomy) are both mitigated: ROCm via time-boxed fallback chain, taxonomy via concrete 8-tag design with 3-tier resolution.

**Key Strengths:**
- Three-pillar architecture sharing one vision backbone with unified KV cache
- Reuse of existing patterns (`FallbackStatsRetriever._chain()`, `BaseAgent`, WebSocket protocol)
- Structured Notes Store bridges pre-match knowledge and live-match retrieval with deterministic O(1) path
- Confidence-gated progression consistent across 5 components
- 4-level fallback chain with documented capability loss — degradation is designed, not accidental
- Single `VLLM_BASE_URL` env var for endpoint agility — no rebuild required

**Areas for Future Enhancement (Post-Hackathon):**
- FAISS or vector database for semantic search at scale (numpy sufficient for ~100 beats)
- Persistent notes storage (currently in-memory per session)
- Multi-language embedding pipeline for cross-lingual note retrieval
- Authentication and multi-tenancy for production deployment
- Reachy Mini physical integration

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure boundaries — `streaming/` imports only by `vision_agent`, `data_sources/` only by agents
- Refer to this document for all architectural questions
- Extend `BaseAgent` for any new agent; use `call_bedrock()` for LLM dispatch
- Always include `gameState` in commentary broadcasts
- Follow the 3-tier confidence gate for any user-facing AI output

**First Implementation Priority (Day 1-2):**
1. `models/narrative_beat.py` — NarrativeBeat dataclass
2. `models/notes_store.py` — StructuredNotes + lookup + tag resolver (including 8-tag taxonomy)
3. `streaming/sglang_client.py` — SGLang + StreamingVLM HTTP client
4. `streaming/frame_sampler.py` — Frame selection, FPS control
5. Modify `NoteOrganizer` to return `NotesStore` instead of raw string
6. Wire `NotesStore.lookup()` into `LiveAgent.generate_live_commentary()`