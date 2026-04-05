# PitchSide AI — Production Deployment Guide

## Overview

This guide covers deploying PitchSide AI as a production-grade, highly-concurrent multimodal sports AI platform.

Update: `/ws/live` now accepts explicit `tactical_detection` messages, broadcasting an immediate analyst note followed by generated tactical commentary. The commentary-notes UI also exposes a dedicated Tactical Brief tab sourced from the organizer JSON payload.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Load Balancer / Ingress                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
     ┌──▼──┐           ┌──▼──┐           ┌──▼──┐
     │ Pod │           │ Pod │           │ Pod │  (3+ replicas)
     │ Srv │           │ Srv │           │ Srv │
     └──┬──┘           └──┬──┘           └──┬──┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     │                     │                     │
  ┌──▼──────┐        ┌─────▼────┐        ┌──────▼──┐
  │ DynamoDB │        │ OpenSearch│        │  Redis  │
  │ (Events) │        │ (RAG)    │        │(Cache)  │
  └──────────┘        └──────────┘        └─────────┘
     │                     │
     └─────────────────────┴─────────────────────────► AWS Bedrock
                                                      (Nova Models)
```

## Deployment Options

Recommended model split:
- Cloud production: Bedrock
- Self-hosted production: vLLM with `Qwen/Qwen2.5-VL-7B-Instruct`
- Lightweight local development: Ollama with `qwen2.5:3b` and `qwen2.5vl:3b`
- Mixed local development: `COMMENTARY_NOTES_LLM_BACKEND=ollama`, `VISION_LLM_BACKEND=vllm`, `OLLAMA_MODEL=qwen2.5:3b`, `VLLM_BASE_URL=http://localhost:8000`, `VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct-AWQ`

### Option 1: Docker Compose (Local Development)

```bash
# Setup
cp .env.example .env
# Edit .env with your AWS credentials

# Run
docker-compose up -d

# Access
- Backend: http://localhost:8080
- Frontend: http://localhost:5173
- Health: http://localhost:8080/health
```

### Option 2: Kubernetes (Production)

#### Prerequisites
- EKS cluster
- AWS IAM roles for pods
- OpenSearch cluster
- DynamoDB tables

#### Deployment

```bash
# Create namespace
kubectl create namespace pitchside

# Configure secrets
kubectl -n pitchside create secret generic pitchside-aws-creds \
  --from-literal=access_key_id=YOUR_KEY \
  --from-literal=secret_access_key=YOUR_SECRET

# Configure ConfigMap
kubectl apply -f k8s/config.yaml

# Deploy backend
kubectl apply -f k8s/backend-deployment.yaml

# Check status
kubectl -n pitchside get pods
kubectl -n pitchside logs -f deployment/pitchside-backend

# Port forward (local testing)
kubectl -n pitchside port-forward svc/pitchside-backend 8080:80
```

### Option 3: AWS ECS/Fargate

```bash
# Build and push image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_REPO

docker build -t pitchside-ai:latest .
docker tag pitchside-ai:latest YOUR_ECR_REPO/pitchside-ai:latest
docker push YOUR_ECR_REPO/pitchside-ai:latest

# Deploy via CloudFormation or AWS console
```

## Multi-Agent Orchestration

PitchSide AI implements advanced multi-agent workflows:

### Agent Types
1. **Research Agent** (Nova Pro) - Pre-match analysis
2. **Vision Agent** (Nova Lite) - Real-time tactical recognition
3. **Live Agent** (Nova Sonic) - Speech translation & Q&A
4. **Commentary Agent** - Match commentary generation

### Live Tactical Session Flow
- Client sends `tactical_detection` frames over `/ws/live` after frame analysis clears the confidence threshold.
- Video uploads hit `POST /api/v1/video/analyze`; Bedrock and vLLM deployments with a video-capable `VLLM_VISION_MODEL` first attempt full native clip analysis, then retry as overlapping native-video windows when a vLLM context limit is hit, and only then fall back to dense sampled frames across the clip duration.
- Server broadcasts a formatted analyst note with source `detection` to all tabs in the session.
- Server then generates a second broadcast commentary item with source `analysis`, seeded from the detection insight.
- DynamoDB stores the analyst note as a structured event in Bedrock-backed deployments.

### Orchestration Engine
- **Task Queue**: Async job processing with priority
- **Concurrency Control**: Token bucket rate limiting, circuit breakers
- **Workflow State Management**: Track agent inputs/outputs
- **Error Handling**: Automatic retries with exponential backoff

```python
# Example: Using the orchestrator
from orchestration.engine import get_orchestrator
from orchestration.types import WorkflowContext, AgentType

orchestrator = get_orchestrator(max_concurrent=20)

context = WorkflowContext(
    match_id="man_city_vs_liverpool",
    home_team="Man City",
    away_team="Liverpool",
    sport="soccer"
)

workflow_id = await orchestrator.start_workflow(context)

task_id = await orchestrator.submit_task(
    workflow_id,
    AgentType.RESEARCH,
    "build_brief",
    {"home_team": "Man City", "away_team": "Liverpool"},
    priority=10
)

result = orchestrator.get_task_result(task_id)
```

## Advanced RAG Strategies

The system implements multiple RAG approaches:

```python
from rag import get_rag_retriever, RAGStrategy

retriever = get_rag_retriever()

# Semantic search (vector similarity)
docs = await retriever.retrieve(
    "forwards pressing strategy",
    strategy=RAGStrategy.SEMANTIC,
    top_k=5
)

# Keyword search (BM25)
docs = await retriever.retrieve(
    "defensive tactics",
    strategy=RAGStrategy.KEYWORD
)

# Hybrid (combined)
docs = await retriever.retrieve(
    "formation changes",
    strategy=RAGStrategy.HYBRID
)

# With cross-encoder reranking
docs = await retriever.retrieve(
    "last minute goals",
    strategy=RAGStrategy.CROSS_ENCODER
)
```

## High Concurrency Support

### Rate Limiting
```python
from core import get_rate_limiter, RateLimitConfig

limiter = get_rate_limiter(
    RateLimitConfig(
        requests_per_minute=100,
        burst_size=10,
        timeout_seconds=10
    )
)

# Check limit
allowed, error = await limiter.check_rate_limit("user-123")

# Acquire token (with wait)
await limiter.acquire_token("user-123")
```

### Connection Pooling
```python
from core import get_connection_pool

pool = get_connection_pool(max_connections=100)

# Execute with retry and connection management
result = await pool.execute_with_retry(
    your_coroutine(),
    max_retries=3
)
```

### Circuit Breaker
```python
from core import CircuitBreaker

cb = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

await cb.call(bedrock_api_call())
```

## Production Logging

All errors and events are logged with structured JSON logging:

```json
{
  "timestamp": "2026-03-27T12:34:56.789Z",
  "level": "INFO",
  "event": "research_requested",
  "home_team": "Manchester City",
  "away_team": "Liverpool",
  "sport": "soccer",
  "request_id": "req-12345"
}
```

View logs:
```bash
# Docker Compose
docker-compose logs -f backend

# Kubernetes
kubectl -n pitchside logs -f deployment/pitchside-backend

# CloudWatch (AWS)
aws logs tail /ecs/pitchside-backend --follow
```

## Monitoring & Metrics

### Health Checks
```bash
# Liveness probe
curl http://localhost:8080/health

# Status and metrics
curl http://localhost:8080/status
```

Response:
```json
{
  "status": "healthy",
  "service": "PitchSide AI",
  "version": "2.0.0",
  "timestamp": "2026-03-27T12:34:56Z"
}
```

### Prometheus Metrics
Metrics exposed at `/metrics` (when enabled):
- `pitchside_workflows_active`
- `pitchside_tasks_processed_total`
- `pitchside_rag_queries_duration_ms`
- `pitchside_bedrock_calls_total`

## Environment Variables

See `.env.example` for all configuration options.

Critical variables:
```bash
# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx

# OpenSearch
OPENSEARCH_ENDPOINT=xxx.us-east-1.aoss.amazonaws.com

# DynamoDB
DYNAMODB_TABLE_NAME=PitchSideMatchEvents

# Concurrency
MAX_CONCURRENT_TASKS=20
```

## Security

### Production Checklist
- [ ] All env vars in Secrets Manager (not in code)
- [ ] IAM roles configured with least privilege
- [ ] Network policies restrict traffic
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] SSL/TLS certificates installed
- [ ] Regular security audits

### Container Security
- Non-root user (UID 1000)
- Read-only root filesystem (where possible)
- Security context applied
- Resource limits set

## Scaling

### Horizontal Scaling
- Kubernetes HPA automatically scales pods based on CPU/memory
- RDS read replicas for database
- OpenSearch domain scaling

### Load Testing
```bash
# Using wrk
wrk -t4 -c100 -d30s http://localhost:8080/health

# Using Apache Bench
ab -n 1000 -c 100 http://localhost:8080/health
```

## Troubleshooting

### High Latency
1. Check rate limiting: `curl http://localhost:8080/status`
2. Verify Bedrock API limits
3. Check network latency to OpenSearch

### Out of Memory
1. Reduce `MAX_CONCURRENT_TASKS`
2. Enable connection pooling
3. Monitor with `docker stats` or Kubernetes metrics

### Task Timeouts
1. Increase `REQUEST_TIMEOUT_SECONDS`
2. Check Bedrock API performance
3. Monitor task queue backlog

## Support & Resources

- Documentation: `/docs` (when Swagger UI enabled)
- Issues: GitHub Issues
- AWS Support: https://console.aws.amazon.com/support

---

**Last Updated**: March 27, 2026
**Version**: 2.0.0 (Production-Ready)
