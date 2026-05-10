# PitchAI — Code Conventions

Confirmed patterns in use across the codebase. Follow these exactly.

---

## Language & Runtime

- Python 3.12, async/await throughout the backend
- FastAPI for API layer
- React + Vite + Tailwind CSS for frontend (JSX, not TSX)
- AWS Bedrock as primary LLM backend; Ollama/OpenAI/vLLM supported locally
- Mixed local backend pattern is supported: commentary-notes agents can use Ollama while vision/video uses vLLM via env overrides

---

## Agent Conventions

### Always extend BaseAgent
```python
from agents.base import BaseAgent

class MyAgent(BaseAgent):
    async def execute(self, *args, **kwargs):
        ...
```

### Always call LLMs via `self.call_bedrock()`
Never call `boto3` or the Anthropic SDK directly inside an agent.
```python
response = await self.call_bedrock(prompt, max_tokens=1000)
```

### Always use sport config for sport-specific data
```python
from config.sports import get_sport_config

config = get_sport_config(self.sport)
labels = config.tactical_labels   # never hardcode ["High Press", "Counter Attack"]
metrics = config.key_metrics
```

### Always log events to DynamoDB via `log_event()`
```python
self.log_event("tactical_detection", observation, {
    "label": "High Press",
    "confidence": 0.92,
    "sport": self.sport
})
```

---

## Data Retrieval Conventions

### Use the factory, never instantiate retrievers directly
```python
from data_sources.factory import get_retriever, get_fbref_retriever

retriever = get_retriever(sport)          # returns singleton
fbref = get_fbref_retriever()             # returns singleton
```

### Cache all data fetches with the decorator
```python
from data_sources.cache import DataCache

cache = DataCache()

@cache.cached("player_stats", ttl=3600)
async def fetch_player_data(player_name: str) -> dict:
    ...
```

### Prefer `cache.py` over `data_cache.py`
`data_sources/data_cache.py` is a legacy lighter-weight duplicate. Use `data_sources/cache.py`.

---

## Parallel Execution

### Use `asyncio.gather` with `return_exceptions=True` for parallel agents
This prevents one failed agent from cascading into others.
```python
results = await asyncio.gather(
    agent_a.execute(...),
    agent_b.execute(...),
    agent_c.execute(...),
    return_exceptions=True
)
# Check each result: isinstance(r, Exception) → handle gracefully
```

---

## Configuration Conventions

### Import config values from `config.py` (root)
```python
import config
model_id = config.BEDROCK_NOVA_PRO_MODEL_ID
aws_region = config.AWS_REGION
```

Backend override vars to preserve when editing runtime config:
```python
config.LLM_BACKEND
config.COMMENTARY_NOTES_LLM_BACKEND
config.VISION_LLM_BACKEND
```

### Import commentary pipeline config from the package
```python
from config.commentary_config import NOTE_GENERATION, WORKFLOW, OUTPUT, DATA_RETRIEVAL

model_id = NOTE_GENERATION.model_ids["organizer"]
timeout = WORKFLOW.agent_timeout_seconds
```

### Never hardcode model IDs, timeouts, or concurrency limits
Always reference `config.py` or `config/commentary_config.py`.

### Per-agent backend routing lives in `agents/base.py`
- `VISION_LLM_BACKEND` overrides the backend for `VisionAgent`
- `COMMENTARY_NOTES_LLM_BACKEND` overrides the backend for the 7 specialized commentary-notes agents
- If an override is unset, the agent falls back to `LLM_BACKEND`

### Native video retries are server-managed
- `api/server.py` should treat video analysis as a three-step path: full native clip first, overlapping native-video windows on vLLM context overflow, then sampled-frame fallback
- Keep these runtime knobs aligned between `config/defaults.py`, `config/__init__.py`, `config.py`, and `.env` when editing video behavior:
    - `NATIVE_VIDEO_WINDOW_SECONDS`
    - `NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS`
    - `NATIVE_VIDEO_MAX_WINDOWS`

---

## Prompts

### All prompts go through `config/prompts.py`
```python
from config.prompts import SystemPrompts

prompt = SystemPrompts.research_brief_prompt(home_team, away_team, sport)
```

### Never write prompt strings inside agent files
If a prompt doesn't exist yet, add it to `config/prompts.py` as a `@staticmethod`.

---

## Error Handling

### Use the typed exception hierarchy from `core/exceptions.py`
```python
from core.exceptions import AgentExecutionError, ModelAPIError

raise AgentExecutionError("research_agent", detail=str(e))
```

### Graceful degradation pattern for agents
```python
try:
    result = await self.call_bedrock(prompt)
except Exception as e:
    self.log_event("error", str(e), {"stage": "bedrock_call"})
    result = self._fallback_response()   # always define a fallback
```

---

## Logging

### Get loggers from `core/logging.py`
```python
from core.logging import get_logger

logger = get_logger(__name__)
logger.log_event("frame_analyzed", "Soccer tactical detection", {"confidence": 0.9})
logger.log_performance("vision_agent.analyze_frame", duration_ms=2300, success=True)
```

Never use `print()` or bare `logging.getLogger()`.

---

## API / FastAPI

### All request/response models are Pydantic classes in `api/server.py`
```python
class CommentaryNotesRequest(BaseModel):
    home_team: str
    away_team: str
    sport: str = "soccer"
    venue: Optional[str] = None
```

### Rate limit check must run before every endpoint
```python
@app.post("/api/v1/my-endpoint")
async def my_endpoint(request: MyRequest, client_id: str = Header(None)):
    await rate_limit_check(client_id)
    ...
```

---

## Adding New Things

### New sport
Only touch `config/sports.py` — add to `SportType` enum and `SPORTS_CONFIG` dict. Zero agent changes required.

### New agent
1. Extend `BaseAgent` in `agents/` or `agents/specialized_commentary/`
2. Add `AgentRole` in `workflows/crewai_config.py`
3. If part of commentary pipeline: add to `CommentaryNotesWorkflow` execution phases
4. Register handler in `api/server.py`

### New data source (stats retriever)
1. Create retriever in `data_sources/` implementing the 5-method interface: `get_player_season_stats`, `get_team_season_stats`, `get_tactical_profile`, `get_team_match_log`, `get_head_to_head_matches`
2. Add `is_available` property that checks the required env vars/dependencies
3. Add `DataCache` with appropriate TTL (4 h for historical, 1 h for live)
4. Tag all returned dicts with `"data_source": "<source-name>"`
5. Insert the retriever into the `FallbackStatsRetriever._chain()` order in `data_sources/factory.py`
6. Register in `data_sources/__init__.py` imports + `__all__`

### New API endpoint
1. Add Pydantic request model in `api/server.py`
2. Include `await rate_limit_check(client_id)`
3. Handle errors using `get_error_response()` from `core/exceptions.py`

---

## Live Match State (`models/game_state.py`)

### One GameState per WebSocket session
```python
from models.game_state import GameState

game_state = GameState(home_team=home_team, away_team=away_team)
```

### Always inject context into commentary seeds
```python
context_prefix = game_state.to_context_string()
# → "MATCH STATE: City 2-1 Liverpool | 67' (2nd Half)\nRecent: 34' GOAL..."
```

### Always include gameState in every broadcast
```python
await manager.broadcast(session_id, {
    "type": "commentary",
    "text": commentary,
    "gameState": game_state.to_dict(),
})
```

### update_from_detection never modifies the score
- `update_from_event(description)` — parses goals, cards, subs, explicit scores
- `update_from_detection(analysis)` — updates minute from `timestamp_ms` only

---

## Data Retrieval Chain

### Stats retrievers are source-tagged
All stats dicts include `"data_source": "statsbomb" | "firecrawl" | "fbref"`.
Propagate this field when writing to the player profile database:
```python
source = stats.get("data_source", "fbref")
```

### StatsBomb is for historical data only
StatsBomb returns empty for seasons not in its free catalog (exact-match). This is intentional — do not add a "most recent available" fallback. If the season is absent, the chain falls to Firecrawl.

### Required env vars per layer
| Layer | Env vars |
|---|---|
| Firecrawl | `FIRECRAWL_API_KEY` |
| FBref direct | none (may 403 in some environments) |

### Use `ConnectionManager` to broadcast to all clients in a session
```python
# In api/server.py — module-level singleton
await manager.connect(workflow_id, websocket)     # on connect
await manager.broadcast(workflow_id, message)     # sends to all tabs in session
await manager.send(websocket, message)            # sends to this client only
manager.disconnect(workflow_id, websocket)        # on disconnect
```

### Tactical detections are explicit WebSocket messages
When a frame analysis crosses the confidence threshold, the frontend should send a `tactical_detection` message instead of only converting the insight into a generic `match_event`. The server broadcasts one `detection` analyst note and may follow it with an `analysis` commentary item seeded from the same detection.

### Video uploads always send both native and fallback payloads
`frontend/src/components/TacticalOverlay.jsx` sends the original clip bytes plus sampled frames in the same request. The backend decides whether the response path is `full_clip`, `windowed`, or `sampled_frames`, so keep the server-side fallback chain authoritative.

### DynamoDB event reads are match-scoped
Use `build_match_session_key(home_team, away_team, sport)` in the backend, and the equivalent frontend slug builder, whenever you need to write or fetch live events. Avoid falling back to the legacy shared `active_match` partition unless you explicitly want unscoped behavior.

### Accept both text and binary frames with `websocket.receive()`
```python
msg = await websocket.receive()        # returns {"type": ..., "text"/"bytes": ...}
if msg.get("text"):
    data = json.loads(msg["text"])
    # dispatch on data["type"]: "match_event", "query", etc.
elif msg.get("bytes"):
    await agent.stream_audio(msg["bytes"])
```

### Start per-session background tasks and always cancel them
```python
periodic_task = asyncio.create_task(_periodic_commentary(workflow_id, agent))
try:
    ...
finally:
    periodic_task.cancel()     # always cancel in finally block
    manager.disconnect(workflow_id, websocket)
```

---

## SSE (Server-Sent Events) Pattern

### Use `StreamingResponse` with an async generator
```python
@app.get("/api/v1/events/stream")
async def events_stream(request: Request, n: int = 20):
    async def generator():
        last_id = None
        while True:
            if await request.is_disconnected():
                break
            events = await get_recent_events(n)
            newest_id = events[0].get("id") if events else None
            if newest_id and newest_id != last_id:
                last_id = newest_id
                yield f"data: {json.dumps(events)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

### Frontend: use `EventSource`, not `fetch` + `setInterval`
```js
const es = new EventSource(`${BACKEND}/api/v1/events/stream?n=30`)
es.onmessage = (e) => setEvents(JSON.parse(e.data) || [])
es.onerror = () => setConnected(false)   // EventSource auto-reconnects
return () => es.close()                  // cleanup on unmount
```

---

## What to Ignore

| File/Directory | Status |
|---|---|
| `tools/firestore_tool.py` | Inactive — legacy GCP code |
| `tools/search_tool.py` | Inactive — superseded by Tavily |
| `data_sources/goal_retriever.py` | Stub — ESPN used instead |
| `data_sources/cricbuzz_retriever.py` | Stub — returns empty data |
| `data_sources/data_cache.py` | Legacy — use `cache.py` |
