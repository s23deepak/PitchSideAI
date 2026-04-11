# PitchAI — Module Registry

Semantic index of every module. 2-3 sentences per entry.

---

## agents/

**`agents/base.py`**
Abstract base class for all agents. Provides `call_bedrock()` with multi-backend LLM dispatch (Bedrock, Ollama, OpenAI, vLLM), a hallucination guardrail injected into every prompt, JSON parsing, text chunking, and structured DynamoDB event logging. It also resolves per-agent backend overrides so commentary-notes agents can run on Ollama while `VisionAgent` runs on vLLM. All agents in the system extend `BaseAgent` — never call Bedrock or parse LLM responses directly.

**`agents/research_agent.py`**
Builds comprehensive pre-match research briefs with Nova Pro and indexes them into RAG. For live queries it routes specific question types (manager, captain, injuries, signings) to grounded data sources (Wikipedia wikitext, ESPN roster, Tavily search) before falling back to free-form RAG retrieval. Entry point: `build_match_brief(home_team, away_team)` and `answer_live_query(query)`.

**`agents/vision_agent.py`**
Analyzes JPEG video frames and short uploaded clips for tactical patterns using the active vision backend with sport-specific prompts. Returns structured JSON (`tactical_label`, `confidence`, `actionable_insight`) and logs high-confidence detections (>0.6) to DynamoDB. Supports raw bytes, base64 input, full native Bedrock or vLLM video clips, overlapping native-video window retries for larger vLLM clips, and sampled multi-frame fallback analysis.

**`agents/live_agent.py`**
Manages a real-time match session for fan Q&A and live commentary. Composes `ResearchAgent` for context-aware factual answers and DynamoDB for recent events. Audio streaming is stubbed for future Nova Sonic speech-to-speech integration.

**`agents/commentary_agent.py`**
Generates professional match commentary at every stage: live segments, tactical breakdowns, player insights, match narratives, predictions, and post-match summaries. Uses Nova Pro with dynamically generated, sport-aware prompts. Logs all generated artefacts to DynamoDB.

---

## agents/specialized_commentary/

**`agents/specialized_commentary/player_research_agent.py`**
Researches full squad profiles for both teams by combining ESPN rosters, FBref season stats, and Wikipedia biographies fetched in parallel (up to 25 players per team). Synthesizes per-player multi-source data with Nova Pro into concise playing-style profiles. The most API-intensive agent — caching is critical here.

**`agents/specialized_commentary/team_form_agent.py`**
Analyses recent W/D/L form, goals scored/conceded, and home/away performance splits for both teams using ESPN and football-data.org. Produces a Nova Pro-synthesized comparative form assessment covering momentum, tactical trends, and likely match narrative. Output feeds into the NoteOrganizer.

**`agents/specialized_commentary/historical_context_agent.py`**
Builds H2H records from football-data.org (ESPN fallback) and fetches current narrative storylines via Tavily web search. Composes a 4-5 sentence historical context narrative with Nova Pro, classifying the H2H pattern (one-sided / balanced / highly competitive) to inform commentary tone.

**`agents/specialized_commentary/weather_context_agent.py`**
Retrieves match-day weather and 3-hour forecast for the venue via `WeatherDataRetriever`. Generates a Nova Sonic narrative covering how temperature, wind, and humidity will affect match flow and tactical decisions. Returns both raw conditions and a sport-specific impact assessment.

**`agents/specialized_commentary/matchup_analysis_agent.py`**
Identifies up to 5 critical 1v1 player battles from two lineups using real FBref season stats. Also produces a positional strength comparison across defence/midfield/attack zones and infers structural vulnerabilities from lineup composition. Depends on player data from `PlayerResearchAgent` completing first.

**`agents/specialized_commentary/news_agent.py`**
Aggregates current team news, injury reports, and lineup status by combining ESPN news feeds with Tavily search, deduplicating items, and synthesising a Nova Lite summary per team. Infers lineup confirmation status (confirmed / predicted / reported) from search evidence. Identifies critical pre-match updates that most affect commentary.

**`agents/specialized_commentary/note_organizer_agent.py`**
Final synthesis agent — takes all six preceding agent outputs and produces a 5-page Peter Drury-style commentary document in both Markdown and structured JSON. Organises content across four sections: Match Info + Lineups, Home Team Analysis, Away Team Analysis, Tactical/Historical/Weather. This is the terminal node of the workflow.

---

## config/

**`config/sports.py`**
Single source of truth for all sport-specific data: tactical labels, key metrics, team positions, research topics, and tactical visual definitions for 5 sports (Soccer, Cricket, Basketball, Rugby, Tennis). All agents call `get_sport_config(sport)` — this is the mechanism that makes the system sport-agnostic. Adding a new sport requires only updating this file.

**`config/prompts.py`**
Generates all LLM prompt templates dynamically from `SportConfig` data. Every prompt is sport-aware — the same method returns cricket-appropriate language for cricket and soccer-appropriate language for soccer. No agent contains hardcoded prompt strings.

**`config/commentary_config.py`**
Centralised typed config for the commentary notes pipeline using four dataclasses: `NOTE_GENERATION` (model IDs, temperatures, player counts), `WORKFLOW` (timeouts, concurrency), `OUTPUT` (format, embedding options), `DATA_RETRIEVAL` (cache TTLs, retries). All values can be overridden via environment variables.

**`config/defaults.py`**
Stores all non-secret application defaults as module-level constants: Bedrock model IDs, server host/port, default LLM backend choice, per-agent backend override vars, Ollama/OpenAI/vLLM connection details, dedicated vLLM vision model selection, rate limiting, concurrency, and sampling parameters. Committed to version control; overridden by `.env` at runtime via `config.py`.

**`config.py`** *(root-level)*
Runtime configuration entry-point. Imports defaults from `config/defaults.py` then overlays secrets (AWS credentials, OpenSearch endpoint, DynamoDB table, Redis, API keys) from `.env` via python-dotenv. It now exposes `COMMENTARY_NOTES_LLM_BACKEND` and `VISION_LLM_BACKEND` in addition to the default `LLM_BACKEND`. Everything imports config values from here.

---

## models/

**`models/game_state.py`**
Live match state machine for WebSocket sessions. `MatchPhase` enum (`PRE_MATCH`, `FIRST_HALF`, `HALF_TIME`, `SECOND_HALF`, `FULL_TIME`), `GameEvent` dataclass (minute, event_type, description, team, player, timestamp), and `GameState` class that tracks score, minute, phase, and last-50 events. `update_from_event(description)` parses regex patterns for goals, cards, subs, explicit scores (e.g. "2-1"), and phase changes. `update_from_detection(analysis)` updates only the match minute from vision timestamps — never modifies score. `to_context_string()` produces a compact prompt-ready string; `to_dict()` returns a JSON-serialisable broadcast payload. Both are injected into every commentary seed so the LLM is always state-aware.

---

## data_sources/

**`data_sources/factory.py`**
Singleton factory for all data source clients. `get_retriever(sport)` routes to `CricbuzzRetriever` for cricket and `ESPNDataRetriever` for all other sports. `get_fbref_retriever()` now returns a `FallbackStatsRetriever` singleton implementing a 3-layer chain: **StatsBomb → Firecrawl → FBref direct**. A shared `_chain()` helper iterates retrievers in order and returns the first non-empty result. Also provides `get_statsbomb_retriever()`, `get_football_data_retriever()`, and `get_search_service()` singletons.

**`data_sources/base.py`**
Structural Protocol (duck-typed interface) defining the 7-method contract for all sport-specific retrievers: `get_match_context`, `get_team_squad`, `get_recent_form`, `get_player_stats`, `get_head_to_head`, `get_team_news`, `get_injuries`. New retrievers must satisfy this interface.

**`data_sources/cache.py`**
TTL-based in-memory cache with namespace+identifier keying and an `@cache.cached("namespace", ttl=N)` decorator. Wrap any async data-fetching function with this decorator to cache results and skip redundant API calls. All production retrievers use this.

**`data_sources/espn_retriever.py`**
Fetches live data from ESPN's unofficial public API (no key required) for rosters, form, news, injuries, and H2H across soccer, basketball, NFL, MLB, and NHL. Maintains a hard-coded `TEAM_ID_CACHE` for common clubs; falls back to live search for unknown teams. Primary retriever for all non-cricket sports.

**`data_sources/fbref_retriever.py`**
Wraps the `soccerdata` library to scrape FBref for structured player and team statistics (goals, assists, xG, xAG, pass%, dribbles, tackles). Supports the five major European leagues via `LEAGUE_ALIASES` and normalises pandas MultiIndex columns to stable snake_case strings. Used as the last-resort fallback in `FallbackStatsRetriever`; may still return 403 errors in some environments.

**`data_sources/statsbomb_retriever.py`**
Retriever backed by the `statsbombpy` free event dataset. Mirrors the FBrefRetriever interface. Uses **exact-match season resolution only** — returns empty (falls to next layer) if the requested season is not in StatsBomb's free catalog, preventing stale historical data being returned for current-season queries. Aggregates per-player stats (goals, assists, xG, shots, tackles) from raw event rows. Cache TTL: 4 hours. Available leagues: La Liga 2004–2021, Champions League, World Cup, Bundesliga 2023/24.

**`data_sources/firecrawl_retriever.py`**
Retriever backed by the Firecrawl web scraping API (`FIRECRAWL_API_KEY`). Handles JavaScript rendering, anti-bot countermeasures, and proxy rotation automatically. Searches FBref/Sofascore for current-season player stats and BBC Sport/FBref for match logs. Parses clean markdown tables returned by the API with `_parse_markdown_table()` and maps columns to canonical stat keys via `_PLAYER_STAT_MAP`. Primary source for current-season data.

**`data_sources/football_data_retriever.py`**
Queries football-data.org REST API v4 for league standings with home/away splits, H2H records, squad details, and top scorers. Includes a built-in rate limiter (1s sleep, 10 req/min free tier) and a hard-coded team-name-to-ID lookup for major European clubs.

**`data_sources/tavily_search_service.py`**
Wraps the Tavily AI search API with TTL caching, graceful no-key fallback, and sport-specific query builders for news, storylines, managers, signings, and lineups. Primary real-time web search service used across all agents. Also exposes a LangChain-compatible `TavilySearchResults` tool.

**`data_sources/weather_retriever.py`**
Fetches match-day weather and hourly forecast for a venue using Tavily web search. Parses numeric values from natural-language responses via regex, and provides sport-specific impact context (wind affects passing in soccer, bowling in cricket).

**`data_sources/wikipedia_retriever.py`**
Returns structured player biographies (career summary, nationality, achievements, playing style) using Tavily search as the primary source with 24-hour caching, falling back to the `wikipedia` Python package.

**`data_sources/sports_specific_retriever.py`**
Composition layer that aggregates FBref, football-data.org, and Tavily into higher-level queries: soccer lineups/formations, tactical patterns, transfer news, and standings. Not a primary data source — delegates to specialist retrievers.

**`data_sources/cricbuzz_retriever.py`**
Stub `BaseRetriever` implementation for cricket. All methods return empty/placeholder data, satisfying the Protocol so agents and the factory work without errors. Actual Cricbuzz API integration is a future TODO.

**`data_sources/goal_retriever.py`**
Stub retriever for soccer via Goal.com. Currently returns placeholders. The factory falls back to `ESPNDataRetriever` for soccer until this is implemented.

---

## workflows/

**`workflows/commentary_notes_workflow.py`**
LangGraph-style state machine orchestrating the 7-agent commentary notes pipeline. Defines `CommentaryNotesState` as the complete workflow state and executes agents in parallel phases (research/form/weather/news together, matchup after, organiser last). Entry point: `CommentaryNotesWorkflow.prepare_notes(match_info)`.

**`workflows/crewai_config.py`**
Defines CrewAI role personas (role, goal, backstory, tools list) for all seven specialized agents and maps them to task definitions with expected inputs and outputs. The `CREW_CONFIG` dict is consumed by the `OrchestratorBridge` when submitting tasks.

**`workflows/orchestration_bridge.py`**
Adapter bridging the `CommentaryNotesWorkflow` to the `WorkflowOrchestrator` for concurrency control and rate limiting. Translates CrewAI task submissions into orchestrator task IDs, polls for results, and accumulates outputs back into `CommentaryNotesState`.

---

## orchestration/

**`orchestration/engine.py`**
Central multi-agent workflow engine managing a prioritised task queue, `asyncio.Semaphore` concurrency control (default 10), agent handler dispatch, message routing, and error/retry handling. `get_orchestrator()` returns the module-level singleton. Register agent handlers here before submitting tasks.

**`orchestration/types.py`**
Shared type definitions: `AgentType` enum, `WorkflowState` enum, `WorkflowContext` (match info + brief + RAG context + tactical detections), `AgentMessage` (inter-agent comms with priority), `TaskResult` (outcome + timing + retry count).

---

## core/

**`core/logging.py`**
Production structured logging via `structlog` and `python-json-logger`. `AppLogger` (returned by `get_logger()`) provides `log_event()`, `log_error()`, and `log_performance()` for field-rich structured output. Use this everywhere — never `print()`.

**`core/concurrency.py`**
Token-bucket rate limiter with async lock support. `RateLimiter` manages per-client `TokenBucket` instances and raises `RateLimitError` when limits are exceeded. Used by the FastAPI server for per-client request-per-minute enforcement.

**`core/exceptions.py`**
Typed exception hierarchy rooted at `PitchSideAIException`. Subtypes: `ConfigurationError`, `AgentExecutionError`, `WorkflowExecutionError`, `RateLimitError`, `ModelAPIError`, `RAGError`, `TimeoutError`. `get_error_response()` converts any exception to a JSON-serialisable API dict.

---

## rag/

**`rag/__init__.py`**
Full RAG implementation using Amazon OpenSearch Serverless with AWS SigV4 auth. Supports four retrieval strategies — semantic (k-NN vector), keyword (BM25), hybrid (RRF), and cross-encoder reranking — with multi-backend embedding generation (Bedrock Titan, Ollama, OpenAI, vLLM). Falls back to in-memory keyword search when OpenSearch is unconfigured.

---

## api/

**`api/server.py`**
Production FastAPI application with CORS, GZip, rate limiting, and lifespan-managed connections. Houses `ConnectionManager` (tracks WebSocket connections per `session_id`, broadcasts to all clients in a session) and `_periodic_commentary()` (background asyncio task generating commentary every 60 s). After `init`, creates a `GameState(home_team, away_team)` per session. Every `match_event` and `tactical_detection` updates the game state and injects `game_state.to_context_string()` into the commentary seed; all broadcasts include `"gameState": game_state.to_dict()` so clients can render the live scoreline. The video endpoint follows a three-step path: full native clip, overlapping native-video windows on vLLM context overflow, then sampled-frame fallback, and returns `analysis_path` plus native-video status fields. Exposes 6 HTTP endpoints, an SSE stream (`GET /api/v1/events/stream`) and a bidirectional WebSocket (`/ws/live`) that accepts `match_event`, `tactical_detection`, and `query` text frames in addition to binary audio.

---

## tools/

**`tools/dynamodb_tool.py`**
Writes structured match events (tactical detections, commentary, Q&A, player insights) to DynamoDB and retrieves recent events via a GSI sorted by timestamp. Includes `build_match_session_key(home_team, away_team, sport)` so events can be partitioned per match instead of the legacy shared `active_match` key. Operations are gated behind `LLM_BACKEND == "bedrock"` so they are no-ops in local development.

**`tools/vector_store.py`**
Embeds text and upserts documents into Amazon OpenSearch with k-NN vector search. Provides `upsert_match_notes()` for indexing research briefs and `retrieve_relevant_context()` for RAG retrieval. Uses an in-memory list fallback when OpenSearch is not configured.

**`tools/search_tool.py`** *(inactive)*
Legacy Google Search grounding tools using the Gemini API. Predates the Tavily-based search service and is no longer wired into the active agent pipeline.

**`tools/firestore_tool.py`** *(inactive)*
Legacy Firestore event storage from the original GCP architecture. Superseded by `dynamodb_tool.py`. Retained but not called by any active code.

---

## frontend/src/

**`frontend/src/App.jsx`**
Root React component managing all top-level state. Opens a WebSocket to `/ws/live` when `matchReady` becomes true or when a tactical upload needs live commentary, collects incoming `commentary` messages into `liveCommentary` state (newest-first, capped at 100), and exposes both `sendMatchEvent(description)` and `sendTacticalDetection(analysis)` to children. Passes those handlers to `TacticalOverlay` and `CommentaryFeed`.

**`frontend/src/components/CommentaryFeed.jsx`** *(new)*
Scrollable live commentary panel showing each message with source icon, source chip, relative timestamp, and the triggering event label. Tactical uploads now appear here first as `Analyst Note` items sourced from `detection`, followed by generated `analysis` commentary. Includes a text input at the bottom — submission calls `sendMatchEvent()` which sends a `match_event` frame over the open WebSocket.

**`frontend/src/components/EventFeed.jsx`**
Displays recent DynamoDB match events. Replaced 30 s `setInterval` polling with a persistent `EventSource` connection to `/api/v1/events/stream`; shows `● live` / `○ reconnecting...` status. The server pushes updates every 3 s.

**`frontend/src/components/TacticalOverlay.jsx`**
Handles frame and video upload for VisionAgent analysis. For video uploads it sends the original clip bytes plus sampled fallback frames, allowing Bedrock and video-capable vLLM deployments to use full native video first, then overlapping native windows on vLLM context overflow, while other backends fall back automatically. After a successful analysis, it calls `setDetection(data.analysis)` and, if `confidence > 0.6`, sends the full result over the WebSocket as `tactical_detection` so the backend can emit an immediate analyst note and then tactical commentary seeded from the same detection.

