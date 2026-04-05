# Architecture & Implementation Guide

## System Overview

PitchSide AI v2.0 is a production-grade, enterprise-level sports AI platform built around Amazon Bedrock's Nova models, with optional Ollama, OpenAI, and vLLM backends behind the same agent interface. The system implements advanced multi-agent orchestration, high-concurrency handling, and intelligent RAG strategies.

## Core Components

### 1. **Orchestration Layer** (`/orchestration`)

Manages multi-agent workflows with state management and concurrency control.

```
orchestration/
├── __init__.py
├── types.py          # Type definitions (WorkflowContext, AgentType, etc.)
├── engine.py         # WorkflowOrchestrator - main orchestration engine
```

**Key Features:**
- Async task queue with priority handling
- Workflow state tracking
- Error handling and retries
- Concurrency limiting via semaphore

**Usage:**
```python
orchestrator = get_orchestrator(max_concurrent=20)
workflow_id = await orchestrator.start_workflow(context)
task_id = await orchestrator.submit_task(workflow_id, agent_type, action, payload)
result = orchestrator.get_task_result(task_id)
```

### 2. **Advanced RAG System** (`/rag`)

Implements multiple retrieval strategies for intelligent context management.

```
rag/
├── __init__.py       # AdvancedRAGRetriever with multiple strategies
```

**RAG Strategies:**
- **Semantic**: Pure vector similarity with embeddings
- **Keyword**: BM25 full-text search
- **Hybrid**: Combined semantic + keyword with deduplication
- **Cross-Encoder**: Reranking with cross-encoder scoring

**Usage:**
```python
retriever = get_rag_retriever()
docs = await retriever.retrieve(query, strategy=RAGStrategy.HYBRID, top_k=5)
```

### 3. **Concurrency & Rate Limiting** (`/core/concurrency.py`)

Production-grade concurrency control patterns.

**Components:**
- **TokenBucket**: Token bucket algorithm for rate limiting
- **RateLimiter**: Per-client rate limiting
- **ConnectionPool**: Connection pool with retry logic
- **CircuitBreaker**: Graceful degradation on failures

**Usage:**
```python
limiter = get_rate_limiter(RateLimitConfig(requests_per_minute=100))
allowed, error = await limiter.check_rate_limit(client_id)

pool = get_connection_pool(max_connections=100)
result = await pool.execute_with_retry(coro, max_retries=3)

cb = CircuitBreaker(failure_threshold=5)
await cb.call(bedrock_api_call())
```

### 4. **Observability** (`/core`)

Production logging and monitoring infrastructure.

**Components:**
- **structured logging** with JSON output
- **AppLogger**: Application-specific logger
- **Error handling**: Custom exception hierarchy

**Usage:**
```python
logger = get_logger(__name__)
logger.log_event("event_name", {"key": "value"})
logger.log_performance("operation", duration_ms, success)
```

### 5. **Updated API Server** (`/api/server.py`)

FastAPI backend integrated with orchestration and advanced features.

**Key Endpoints:**
- `GET /health` - Health check
- `GET /status` - System metrics
- `POST /api/v1/research` - Pre-match research
- `POST /api/v1/frame/analyze` - Tactical analysis
- `POST /api/v1/video/analyze` - Full native video on Bedrock/vLLM, overlapping native-window retry on vLLM context overflow, sampled-frame fallback elsewhere
- `POST /api/v1/query` - Advanced Q&A with RAG
- `GET /api/v1/events` - Fetch recent DynamoDB events (JSON)
- `GET /api/v1/events/stream` - SSE stream of DynamoDB events scoped by `match_session` (push, 3 s poll)
- `WebSocket /ws/live` - Bidirectional live match session

**WebSocket `/ws/live` Protocol:**

| Direction | Message |
|---|---|
| Client → Server | `{"type":"init","home_team":"...","away_team":"...","sport":"..."}` |
| Client → Server | `{"type":"match_event","description":"Haaland scores! 34'"}` |
| Client → Server | `{"type":"tactical_detection","analysis":{"tactical_label":"High Press",...}}` |
| Client → Server | `{"type":"query","text":"Who scored?"}` |
| Client → Server | Binary audio bytes (future Nova Sonic integration) |
| Server → Client | `{"type":"commentary","text":"...","source":"event\|timer\|detection\|analysis","timestamp":"..."}` |
| Server → Client | `{"type":"answer","text":"...","timestamp":"..."}` |
| Server → Client | `{"type":"ready","message":"..."}` |

**ConnectionManager:** Tracks active WebSocket connections per `workflow_id` (session). `broadcast(session_id, msg)` fans out to all connected tabs.

**Event Scoping:** DynamoDB writes and reads are partitioned by a deterministic `match_session` key derived from sport + home team + away team, so the SSE event feed no longer mixes unrelated matches.

**Periodic Commentary:** After session init, a background `asyncio.Task` (`_periodic_commentary`) fires `LiveAgent.generate_live_commentary()` every 60 s, seeded from recent DynamoDB events, and broadcasts the result to all session clients.

**Middleware:**
- CORS middleware (production-configured)
- GZip compression
- Rate limiting via dependency injection
- Error handling with proper HTTP codes

## Running Commentary Pipeline

### Event Sources → Commentary Flow

```
[TacticalOverlay] → confidence > 0.6 → /ws/live (text "tactical_detection") ─────┐
[TacticalOverlay video upload] → full native clip → native windows on overflow → sampled frames ─┤
[CommentaryFeed input] → user types match event → /ws/live (text "match_event") ──┼─► server
[Periodic timer, 60 s] → _periodic_commentary task ─────────────────────────────────┘
                                                                                     │
                                     tactical_detection ─► analyst note broadcast ───┤
                                     tactical_detection ─► LiveAgent.generate_live_commentary()
                                     match_event/timer  ─► LiveAgent.generate_live_commentary()
                                                                                     │
                                                    ConnectionManager.broadcast()
                                                                                     │
                            {"type":"commentary","source":"detection|analysis|event|timer",...}
                                                                                     │
                                                    App.jsx → liveCommentary state
                                                                                     │
                                                   CommentaryFeed + Tactical Brief UI
```

### SSE Event Feed

```
DynamoDB (write_event, scoped by match_session) ──→ /api/v1/events/stream?match_session=... ──→ EventSource (EventFeed.jsx)
                                                   3 s poll / push                                   real-time browser update
```

### Three Commentary Triggers

| Trigger | Source | Threshold |
|---|---|---|
| Vision detection analyst note | `TacticalOverlay` uploads frame | `confidence > 0.6` |
| Video clip analysis | `POST /api/v1/video/analyze` | Native Bedrock or vLLM video when available, otherwise sampled frames |
| Vision detection commentary | Generated after `tactical_detection` is received | Detection must include insight/observation |
| Manual event | User types in `CommentaryFeed` input | Any non-empty text |
| Periodic timer | `_periodic_commentary` background task | Every 60 s |

---

## High Concurrency Architecture

### Request Flow with Concurrency

```
Client Request
    ↓
[CORS Middleware]
    ↓
[GZip Middleware]
    ↓
[Rate Limiter] ← Limited to 100 req/min per client
    ↓
[Request Handler]
    ↓
[Orchestration Engine] ← Max 20 concurrent tasks
    ├─→ [Task 1 - Semaphore]
    ├─→ [Task 2 - Semaphore]
    └─→ [Task N - Semaphore]
    ↓
[RAG Retriever] ← Multiple search strategies
    ↓
[Connection Pool] ← Reuses connections, retries
    ↓
[AWS Bedrock] ← Circuit breaker protection
    ↓
[Response]
```

### Concurrency Guarantees

1. **Per-client rate limiting**: 100 req/min with 10-token burst
2. **Global task limit**: Max 20 concurrent orchestrated tasks
3. **Connection pooling**: Reuses connections, max 100 concurrent
4. **Timeout protection**: 300s default timeout per task
5. **Circuit breaker**: Fails gracefully if Bedrock API has issues

## Multi-Agent Orchestration Flow

### Workflow Lifecycle

```
1. start_workflow(context)
   ├─ Create unique workflow ID
   ├─ Store context in orchestrator.workflows
   └─ Return workflow_id

2. submit_task(workflow_id, agent, action, payload)
   ├─ Create task message
   ├─ Add to priority queue
   └─ Return task_id

3. process_task_queue() [worker]
   ├─ Get task from queue
   ├─ Acquire semaphore slot
   ├─ Execute handler with timeout
   ├─ Handle errors and retries
   └─ Store result

4. get_task_result(task_id)
   ├─ Return TaskResult with status
   ├─ Includes execution_time_ms
   └─ May include error details

5. finalize_workflow(workflow_id)
   ├─ Set final state (COMPLETED/FAILED)
   ├─ Record end_time
   └─ Clean up resources
```

### Agent Types & Handlers

```python
class AgentType(str, Enum):
    RESEARCH = "research"      # Nova Pro - Deep analysis
    VISION = "vision"          # Nova Lite - Frame analysis
    LIVE = "live"              # Nova Sonic - Audio
    COMMENTARY = "commentary"  # Custom - Commentary generation
```

Each agent is registered with a handler:
```python
orchestrator.register_agent_handler(
    AgentType.RESEARCH,
    research_agent.build_brief
)
```

## RAG Strategy Selection

### Strategy Recommendations

| Strategy | Use Case | Speed | Accuracy |
|----------|----------|-------|----------|
| Semantic | Conceptual queries | Fast | High |
| Keyword | Exact matches | Very Fast | Medium |
| Hybrid | General queries | Medium | Very High |
| Cross-Encoder | Critical decisions | Slow | Highest |

### Example Decision Logic

```python
if query_type == "tactical":
    strategy = RAGStrategy.HYBRID  # Balanced for tactics
elif query_type == "stats":
    strategy = RAGStrategy.KEYWORD  # Fast exact matches
elif is_critical_match:
    strategy = RAGStrategy.CROSS_ENCODER  # Most accurate
else:
    strategy = RAGStrategy.SEMANTIC  # Default
```

## Production Deployment Patterns

### Docker Compose (Local)
```yaml
services:
  backend:   # FastAPI server
  frontend:  # React Vite app
  redis:     # Cache & session store
```

### Kubernetes (Production)
```yaml
Deployment:
  ├─ 3+ backend replicas
  ├─ HPA (2-10 replicas based on CPU)
  └─ Health checks & resource limits

Service:
  └─ ClusterIP (internal routing)

ConfigMap:
  └─ Environment configuration

Secret:
  └─ AWS credentials
```

### Scaling Characteristics

- **Horizontal**: Add more Pod replicas (auto-scaled via HPA)
- **Vertical**: Increase Pod resource limits (CPU/memory)
- **Database**: OpenSearch scaling, DynamoDB on-demand, Redis cluster

## Security Architecture

### Authentication & Authorization
- API keys via header (not implemented yet, use in production)
- CORS restricted to specific origins
- Rate limiting per client_id

### Data Protection
- AWS IAM roles for service-to-service auth
- Encryption in transit (TLS recommended)
- Encryption at rest (OpenSearch, DynamoDB)

### Container Security
- Non-root user (UID 1000)
- Read-only root filesystem
- Resource limits enforced
- No privileged containers

## Monitoring & Observability

### Logging Strategy

```
Application Logs (JSON)
    ├─ INFO: business events (research requested, etc.)
    ├─ WARNING: recoverable errors, retries
    ├─ ERROR: task failures, API issues
    └─ DEBUG: detailed execution flow

Output:
    ├─ Console (formatted)
    ├─ File (logs/pitchside.log)
    └─ CloudWatch (AWS)
```

### Health Checks

```
/health - Basic liveness
→ {"status": "healthy", "service": "PitchSide AI"}

/status - Readiness & metrics
→ {"status": "operational", "active_workflows": 3, "active_tasks": 8}
```

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable message",
  "details": {"key": "value"}
}
```

## Configuration Management

### Environment Variables

```bash
# Core
ENVIRONMENT=production
AWS_REGION=us-east-1

# Concurrency
MAX_CONCURRENT_TASKS=20
REQUEST_TIMEOUT_SECONDS=300

# Rate Limiting
RATE_LIMIT_RPM=100
RATE_LIMIT_BURST=10

# RAG
OPENSEARCH_ENDPOINT=...
OPENSEARCH_INDEX=pitchside-match-notes

# Bedrock Models
RESEARCH_MODEL=amazon.nova-pro-v2:0
VISION_MODEL=amazon.nova-lite-v2:0
LIVE_AUDIO_MODEL=amazon.nova-sonic-v2:0
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

### Validation

Configuration is validated on startup:
```python
validate_config()  # Raises if critical vars missing
```

## Performance Optimization Tips

### 1. RAG Optimization
- Use KEYWORD strategy for known facts (faster)
- Cache frequent queries in Redis
- Batch vector embeddings

### 2. Concurrency Tuning
- Adjust `MAX_CONCURRENT_TASKS` based on memory
- Monitor task queue depth
- Use appropriate timeout values

### 3. API Optimization
- Enable GZip compression (already enabled)
- Implement pagination for large result sets
- Cache static assets in frontend

### 4. Database Optimization
- Create OpenSearch index aliases
- Use DynamoDB on-demand or provisioned capacity
- Enable DAX caching layer

## Development Workflow

### Local Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Backend
python -m uvicorn api.server:app --reload

# Frontend (new terminal)
cd frontend && npm run dev
```

### Testing

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/ -m integration

# Load test
wrk -t4 -c100 -d30s http://localhost:8080/health
```

### Code Quality

```bash
# Type checking
mypy .

# Linting
ruff check .

# Formatting
black .
```

## Troubleshooting Guide

### Workflow State Issues
- Check `orchestrator.workflows` for workflow state
- Verify task was submitted with correct agent_type
- Look for task in `orchestrator.results`

### RAG Issues
- Verify `OPENSEARCH_ENDPOINT` is configured
- Check embedding generation (CPU-intensive)
- Monitor token usage for Titan embeddings

### Rate Limiting Issues
- Check limiter token count: `limiter.get_remaining_tokens(client_id)`
- Verify client_id is being passed correctly
- Adjust `RATE_LIMIT_RPM` if needed

### Task Timeout Issues
- Increase `REQUEST_TIMEOUT_SECONDS`
- Check Bedrock API quotas in AWS console
- Monitor network latency to AWS

---

**Document Version**: 2.1
**Last Updated**: April 2026
**Author**: PitchSide AI Team
