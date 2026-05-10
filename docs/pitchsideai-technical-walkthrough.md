# Building PitchSideAI: A Technical Walkthrough of an AI Football Broadcast Companion

Live football is a hard environment for AI products because the useful answer is almost never just a stat. A commentator might need the historical context behind a rivalry, a fan might want to know why a tactical shift matters, and a broadcast producer might need that insight at the exact moment the game changes.

PitchSideAI was built around that idea: turn match footage, pre-match research, live game state, and natural-language Q&A into one broadcast companion. The project combines a React/Vite frontend, a FastAPI backend, a multi-agent research workflow, WebSocket-driven live sessions, and a vision-language serving path designed for vLLM and AMD ROCm-capable infrastructure.

This walkthrough explains how the system was put together, the main technical decisions, and the pieces that make the demo feel like a real live-sports product rather than a generic chatbot.

## The Product Shape

The first design decision was to split the app into three connected experiences:

1. **Fan Lens Broadcast**: a full-screen viewing mode with scoreboard state, automatic trivia cards, voice Q&A, and split-screen answers.
2. **Commentator Dashboard**: a production-style workspace with video on one side and a teleprompter of generated narrative beats on the other.
3. **Notes Generation Hub**: a pre-match preparation surface where the user enters two teams and runs the agentic research pipeline.

All three views share the same underlying match session. That matters because the app is not just generating isolated responses. It is maintaining context: teams, score, match minute, phase, commentary settings, language preference, generated notes, and the latest tactical vision analysis.

At a high level, the system looks like this:

```text
React / Vite frontend
  Fan Lens Broadcast
  Commentator Dashboard
  Notes Generation Hub
        |
        | HTTP, SSE, WebSocket
        v
FastAPI backend
  /api/v1/commentary/prepare-notes
  /api/v1/frame/analyze
  /api/v1/video/analyze
  /api/v1/video/qa
  /ws/live
        |
        v
Agents, data retrievers, RAG, game state, notes store
        |
        v
LLM / VLM backends
  vLLM
  Qwen vision-language models
  optional OpenAI / Bedrock-compatible paths
```

The core implementation lives in `api/server.py`, `workflows/commentary_notes_workflow.py`, `agents/`, `models/`, `data_sources/`, `streaming/`, and `frontend/src/`.

## Backend Foundation: FastAPI as the Live Match Hub

The backend is a FastAPI application that does three jobs:

- Serve request/response APIs for research, frame analysis, video analysis, and Q&A.
- Maintain long-lived live match sessions through `/ws/live`.
- Stream long-running agent progress back to the browser with server-sent events.

The most important backend abstraction is the `ConnectionManager` in `api/server.py`. It tracks active WebSocket connections by session, stores generated `NotesStore` objects, keeps Q&A runners warm, remembers commentary settings, and broadcasts updates to every connected tab.

That lets a Fan Lens view and a Commentator Dashboard stay synchronized. When the server receives a match event or tactical detection, it can update game state once and fan the resulting commentary, trivia, or teleprompter highlight out to all clients in the same session.

The live WebSocket protocol is intentionally small. The client sends messages such as:

```json
{"type":"init","home_team":"Arsenal","away_team":"Chelsea","sport":"soccer"}
{"type":"settings_update","bias":0,"excitement":0.7,"knowledge_depth":0.8}
{"type":"language_switch","language":"es"}
{"type":"match_event","description":"Goal by Saka 34'"}
{"type":"tactical_detection","analysis":{"tactical_label":"High Press","confidence":0.82}}
{"type":"query","text":"Why is Arsenal pressing so high?"}
```

The server responds with normalized events:

```json
{"type":"ready","session_id":"soccer#arsenal#vs#chelsea"}
{"type":"commentary","text":"...","gameState":{...}}
{"type":"trivia_card","text":"...","source":"notes"}
{"type":"beat_highlight","beat_index":3,"confidence":0.86}
{"type":"answer","answer":"...","overlay_coordinates":{...}}
```

That protocol became the backbone of the app. Everything interactive in the frontend eventually maps to one of those message types.

## Pre-Match Intelligence: The Seven-Agent Notes Pipeline

The most important "agentic" part of PitchSideAI is the commentary notes workflow in `workflows/commentary_notes_workflow.py`.

Before a match starts, the app needs more than a generic team summary. It needs structured broadcast material: team form, player profiles, recent news, head-to-head history, weather context, key tactical matchups, and narrative beats that can be surfaced later during live play.

The workflow is organized around a shared `CommentaryNotesState` object. Each agent writes its output into that state, and the final organizer synthesizes the outputs into a `NotesStore`.

The optimized flow is:

```text
1. Initialize
   - Fetch match schedule and venue when missing.

2. Parallel research phase
   - NewsAgent
   - WeatherContextAgent
   - HistoricalContextAgent
   - PlayerResearchAgent
   - TeamFormAgent

3. Dependent tactical phase
   - MatchupAnalysisAgent waits for player research.

4. Synthesis
   - CommentaryNoteOrganizerAgent turns all outputs into markdown and narrative beats.
```

The key lesson here was dependency management. Some work can run immediately: news, weather, history, and team form only need team names or venue context. Matchup analysis, however, needs player lists, so it has to wait for squad research. Running every independent branch with `asyncio.gather()` made the pipeline much faster without making the final synthesis less reliable.

The frontend consumes this pipeline over SSE from `/api/v1/commentary/prepare-notes`. That gives users a live progress feed instead of a frozen loading screen:

```text
Fetching match schedule and venue...
Running parallel research phase...
Initial context gathered
Squads researched
Team form analyzed
Analyzing key matchups...
Synthesizing commentary notes...
Commentary notes ready
```

That progress stream is a small UX detail, but it changes how the product feels. The user can see the agents working, and long-running research becomes understandable instead of mysterious.

## Data Retrieval: Round-Robin Sources With Rate Limits

The agents need sports data, but football data sources vary a lot in coverage, authentication, rate limits, and reliability. PitchSideAI wraps them behind `MultiSourceRetriever` in `data_sources/multi_source_retriever.py`.

The retriever initializes available sources lazily:

- ESPN for fixtures, squads, and general match context.
- FootballData.org for authenticated football data when an API key is available.
- Transfermarkt for player profiles and market-value-style context.
- OneVersusOne for premium player metrics when credentials are configured.
- Firecrawl as a fallback for current web context.

Each source gets its own rate limiter, and calls are distributed with round-robin selection and failover. This keeps the agents from depending on a single fragile provider. It also makes local development practical because the app can still run with only a subset of optional API keys.

## NotesStore: Turning Research Into Live Lookup

Raw markdown is useful for humans, but the live product needs structured lookup. If a vision model detects a corner, a red card, or a dangerous free kick, the app should quickly find the relevant pre-written narrative beats.

That is why the final notes are stored in `models/notes_store.py` as a `NotesStore`:

```text
NotesStore
  raw_markdown
  beats: List[NarrativeBeat]
  lookup: Dict[event_tag, List[beat_index]]
```

On initialization, the store builds an O(1) lookup table from canonical event tags to narrative beat indices. A `TagResolver` normalizes labels from the vision model using exact matches, synonyms, and word-boundary matching.

There is also a safety gate for goals. A vision model might describe a "goal chance" or "goalmouth scramble", but the app should not treat that as a real goal unless the score has changed. The resolver can compare previous and current score totals before allowing the canonical `goal` tag through.

That small guardrail is important in live sports. False positives are not just incorrect; they break trust immediately.

## Live Game State: Score, Minute, Phase, and Event Timeline

The `GameState` model in `models/game_state.py` gives each WebSocket session a lightweight match brain.

It parses free-text event descriptions like:

```text
Kickoff
Goal by Haaland 34'
Yellow card for Rice 58'
Second half begins
Full-time whistle
```

From those messages it updates:

- home and away score
- match minute
- match phase
- recent event timeline
- active players and recent touches when available

The server includes `gameState` in commentary broadcasts, which means the frontend does not have to infer score or phase from text. The LLM also gets a compact match-state string when generating commentary, so its responses are grounded in the current state of the match.

This split is deliberate: deterministic parsing handles the scoreboard and timeline, while the model handles language, explanation, and narrative.

## Vision and Video: A Hardware-Aware Fallback Chain

The project was built for the AMD Developer Hackathon, so the vision path needed to be serious about GPU serving. The app supports a streaming backend factory in `streaming/factory.py` with a two-level fallback chain:

```text
Level 1: StreamingVLM
  - Best for high-memory GPU sessions such as MI300X-class deployments.
  - Designed for temporal continuity and streaming video understanding.

Level 2: vLLM frame-by-frame
  - Practical local and demo fallback.
  - Uses Qwen vision-language models through an OpenAI-compatible vLLM endpoint.
```

The backend exposes both frame and video analysis endpoints:

- `/api/v1/frame/analyze`
- `/api/v1/video/analyze`
- `/api/v1/video/qa`

For video-capable backends, the server first attempts native video analysis. If a vLLM context-length error occurs, it retries with overlapping native-video windows. If that still fails or the backend does not support native video, it falls back to sampled frames.

That fallback strategy was one of the most practical engineering choices in the project. It lets the same product target powerful AMD GPU infrastructure while still remaining demoable on smaller machines.

## Q&A: Combining Voice, Vision Context, and Notes

Fan Lens includes a hold-to-ask interaction. The target experience is simple: the user watches the match, holds the mic, asks a question, and gets an answer without leaving the video.

Under the hood, Q&A combines several layers:

- Browser voice capture or typed fallback.
- Live WebSocket session context.
- Precomputed `NotesStore` material.
- Latest tactical vision context.
- Player identification context when available.
- LLM response generation through the configured backend.

The Q&A path is not just "send text to model." It is session-aware. If the notes pipeline has already generated player and matchup research, the Q&A agent can answer with richer context. If a recent vision detection exists, the answer can refer to what is happening on screen.

The frontend displays answers in a split-screen overlay so the video remains part of the interaction instead of being replaced by a chat panel.

## Frontend: Broadcast UI Instead of Chat UI

The React frontend is organized around product surfaces rather than model endpoints:

```text
frontend/src/pages/
  LandingPage.jsx
  FanLensBroadcast.jsx
  CommentatorDashboard.jsx
  NotesGenerationHub.jsx

frontend/src/components/
  VideoCanvas.jsx
  MicButton.jsx
  Teleprompter.jsx
  TriviaCard.jsx
  SplitScreen.jsx
  ControlsTray.jsx
  TopNavBar.jsx

frontend/src/contexts/
  LiveSessionContext.jsx
```

The frontend design system is called Midnight Stadium. It uses a dark broadcast-style palette with electric lime and gold accents, defined in `frontend/src/design-tokens/tokens.css`.

The key frontend decision was to avoid making the app feel like a dashboard wrapped around a video. In Fan Lens mode, the video owns the screen. AI features appear as overlays: scoreboard pill, trivia cards, controls tray, mic button, and answer panel.

The Commentator Dashboard uses a different layout because its user has a different job. It prioritizes a teleprompter, tactical brief, and live commentary feed. The same backend events power both views, but the UI translates those events into different workflows.

## Deployment: Docker, Hugging Face Spaces, and External Inference

PitchSideAI is packaged for Hugging Face Spaces using the Docker SDK. The Docker build compiles the frontend and serves it alongside the FastAPI backend in one container.

The main runtime variables are:

```env
LLM_BACKEND=vllm
VLLM_BASE_URL=http://localhost:8001
VLLM_MODEL=Qwen/Qwen2.5-3B-Instruct
VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct-AWQ
AUDIO_VLLM_BASE_URL=http://localhost:8001
AUDIO_MODEL=Qwen/Qwen2-Audio-7B-Instruct
VITE_BACKEND_URL=http://localhost:8000
```

For deployment, the Space can keep the web app lightweight while pointing `VLLM_BASE_URL` at a GPU inference endpoint. That separation is useful because web serving and model serving have very different resource profiles.

The repository also includes Kubernetes and production deployment notes for a larger version with multiple backend replicas, DynamoDB event storage, OpenSearch RAG, Redis caching, and Bedrock-compatible model paths.

## Validation and Reliability Work

For a live demo, the product has to degrade gracefully. The validation work focused on:

- frontend build success
- Docker build readiness
- health checks
- WebSocket drop handling
- GPU fallback timing
- audio Q&A latency
- language switching
- cold start behavior
- browser compatibility

The validation report records local targets such as sub-3.5-second audio Q&A, sub-500ms commentary time-to-first-token, 5-7 FPS vision processing, and fallback activation under 30 seconds.

Those numbers are not the final word for every deployment, but they gave the project a concrete reliability target during development.

## What I Would Improve Next

The current architecture gets the end-to-end product working, but there are clear next steps:

- Make the LangGraph integration fully real instead of keeping the graph builder as a future-facing hook.
- Persist `NotesStore` and live session state outside process memory for multi-replica deployments.
- Add stronger source attribution in generated commentary notes.
- Improve player identification with richer lineup, kit, and positional context.
- Run longer benchmark suites against AMD MI300X infrastructure with ROCm-native model serving.
- Add production observability dashboards around WebSocket sessions, agent timings, and VLM fallback rates.

## Takeaways

The biggest lesson from building PitchSideAI was that live AI products need structure around the model. The model is important, but the product works because deterministic state, agent workflow boundaries, source-aware retrieval, fallback infrastructure, and broadcast-specific UI all cooperate.

PitchSideAI is not just an LLM answering football questions. It is a match session that prepares before kickoff, watches during play, remembers what has happened, retrieves the right context, and presents the result in the language of a live broadcast.

That is the difference between a sports chatbot and an AI broadcast companion.
