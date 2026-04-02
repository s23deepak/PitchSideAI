"""
Production-level FastAPI Server — PitchSide AI Backend
Integrates orchestration, RAG, concurrency control, and monitoring.
"""
import base64
import json
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
import structlog

from config import AWS_REGION, PORT, LOG_LEVEL
from core import setup_logging, get_logger, get_rate_limiter, RateLimitConfig
from core.exceptions import RateLimitError, WorkflowExecutionError
from orchestration.engine import get_orchestrator
from orchestration.types import WorkflowContext, AgentType, WorkflowState
from rag import get_rag_retriever, RAGStrategy
from agents.live_agent import LiveAgent
from agents.vision_agent import VisionAgent
from agents.research_agent import ResearchAgent
from tools.dynamodb_tool import get_recent_events

# Setup production logging
setup_logging(level=LOG_LEVEL, json_logs=True)
logger = get_logger(__name__)


# ── Request/Response Models ────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    """Request to build pre-match research brief."""
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    sport: str = Field(default="soccer", pattern="^(soccer|cricket)$")


class FrameAnalysisRequest(BaseModel):
    """Request for video frame tactical analysis."""
    frame_b64: str = Field(..., description="Base64-encoded JPEG")
    sport: str = Field(default="soccer", pattern="^(soccer|cricket)$")
    timestamp: Optional[int] = None


class QueryRequest(BaseModel):
    """Text-based Q&A query."""
    query: str = Field(..., min_length=1, max_length=500)
    home_team: str = Field(default="Team A")
    away_team: str = Field(default="Team B")
    rag_strategy: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid|cross_encoder)$")


class CommentaryNotesRequest(BaseModel):
    """Request for professional commentary notes preparation."""
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    sport: str = Field(default="soccer", pattern="^(soccer|cricket|basketball|rugby|tennis|hockey|baseball)$")
    match_datetime: str = Field(..., description="ISO format datetime")
    venue: str = Field(..., min_length=1, max_length=200)
    venue_lat: float = Field(default=0.0, description="Venue latitude")
    venue_lon: float = Field(default=0.0, description="Venue longitude")
    include_embedded_json: bool = Field(default=True)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    timestamp: str


# ── Dependency Injection ───────────────────────────────────────────────────────

async def rate_limit_check(client_id: str = "anonymous") -> None:
    """Rate limiting dependency."""
    rate_limiter = get_rate_limiter(RateLimitConfig(requests_per_minute=100))
    allowed, error_msg = await rate_limiter.check_rate_limit(client_id)

    if not allowed:
        raise HTTPException(status_code=429, detail=error_msg)


# ── Application Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("🏟️  PitchSide AI backend starting...")

    # Initialize orchestrator
    orchestrator = get_orchestrator(max_concurrent=20)

    # Start task queue processor
    task_processor = asyncio.create_task(orchestrator.process_task_queue())

    yield

    # Cleanup
    task_processor.cancel()
    logger.info("PitchSide AI backend shutting down.")


# ── Create FastAPI App ─────────────────────────────────────────────────────────

app = FastAPI(
    title="PitchSide AI",
    version="2.0.0",
    description="Production-grade multimodal sports AI assistant",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Production: use env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared agent instances
vision_soccer = VisionAgent(sport="soccer")
vision_cricket = VisionAgent(sport="cricket")
research_agent = ResearchAgent()
orchestrator = get_orchestrator()


# ── Health & Status Endpoints ──────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    from datetime import datetime
    return HealthResponse(
        status="healthy",
        service="PitchSide AI",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/status")
async def status():
    """Get system status and metrics."""
    active_tasks = await orchestrator.get_active_tasks_count()
    return {
        "status": "operational",
        "active_workflows": len(orchestrator.workflows),
        "active_tasks": active_tasks,
        "max_concurrent_tasks": orchestrator.max_concurrent_tasks
    }


# ── Research Endpoint ──────────────────────────────────────────────────────────

@app.post("/api/v1/research", dependencies=[Depends(rate_limit_check)])
async def build_research(req: ResearchRequest) -> dict:
    """
    Trigger pre-match research with orchestration.
    Returns:
        - brief: Match analysis text
        - rag_docs: Retrieved context documents
        - workflow_id: For tracking
    """
    logger.log_event("research_requested", {
        "home_team": req.home_team,
        "away_team": req.away_team,
        "sport": req.sport
    })

    try:
        # Use orchestrator to manage workflow
        context = WorkflowContext(
            match_id=f"{req.home_team}_{req.away_team}",
            home_team=req.home_team,
            away_team=req.away_team,
            sport=req.sport
        )

        workflow_id = await orchestrator.start_workflow(context)

        # Submit research task
        task_id = await orchestrator.submit_task(
            workflow_id,
            AgentType.RESEARCH,
            "build_brief",
            {
                "home_team": req.home_team,
                "away_team": req.away_team,
                "sport": req.sport
            },
            priority=10  # High priority
        )

        # Wait for task completion (with timeout)
        for _ in range(30):  # Poll for up to 30 seconds
            result = orchestrator.get_task_result(task_id)
            if result:
                if result.success:
                    return {
                        "status": "success",
                        "brief": result.data.get("brief", ""),
                        "rag_docs": result.data.get("documents", []),
                        "workflow_id": workflow_id,
                        "execution_time_ms": result.execution_time_ms
                    }
                else:
                    raise WorkflowExecutionError(workflow_id, result.error or "Unknown error")

            await asyncio.sleep(1)

        raise TimeoutError("Research task", 30)

    except Exception as exc:
        logger.error("research_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Frame Analysis Endpoint ────────────────────────────────────────────────────

@app.post("/api/v1/frame/analyze", dependencies=[Depends(rate_limit_check)])
async def analyze_frame(req: FrameAnalysisRequest) -> dict:
    """Analyze video frame for tactical patterns."""
    logger.log_event("frame_analysis_requested", {"sport": req.sport})

    try:
        agent = vision_soccer if req.sport == "soccer" else vision_cricket
        result = await agent.analyze_frame_b64(req.frame_b64)

        return {
            "status": "success",
            "analysis": result,
            "timestamp": req.timestamp
        }

    except Exception as exc:
        logger.error("frame_analysis_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── Advanced Query Endpoint ───────────────────────────────────────────────────

@app.post("/api/v1/query", dependencies=[Depends(rate_limit_check)])
async def text_query(req: QueryRequest) -> dict:
    """
    Advanced Q&A with selectable RAG strategy.
    """
    logger.log_event("query_received", {
        "query": req.query,
        "rag_strategy": req.rag_strategy
    })

    try:
        # Get RAG retriever with selected strategy
        retriever = get_rag_retriever()
        rag_strategy = RAGStrategy(req.rag_strategy)

        # Retrieve context with selected strategy
        documents = await retriever.retrieve(
            query=req.query,
            strategy=rag_strategy,
            top_k=5
        )

        # Answer query using retrieved context
        agent = LiveAgent()
        answer = await agent.handle_text_query(
            req.query,
            context=documents
        )

        return {
            "status": "success",
            "answer": answer,
            "documents_retrieved": len(documents),
            "rag_strategy": req.rag_strategy,
            "sources": [
                {"doc_id": doc.doc_id, "score": doc.score}
                for doc in documents
            ]
        }

    except Exception as exc:
        logger.error("query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── Events Endpoint ────────────────────────────────────────────────────────────

@app.get("/api/v1/events")
async def get_events(n: int = 20):
    """Get recent match events."""
    try:
        events = await get_recent_events(n)
        return {
            "status": "success",
            "events": events,
            "count": len(events)
        }
    except Exception as exc:
        logger.error("events_fetch_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


# ── WebSocket — Live Audio Streaming ───────────────────────────────────────────

@app.websocket("/ws/live")
async def live_audio_ws(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional live audio streaming.

    Protocol:
    1. Client sends: {"type": "init", "home_team": "...", "away_team": "...", "sport": "..."}
    2. Client streams audio chunks
    3. Server streams back audio responses + text
    """
    await websocket.accept()
    logger.info("New live audio session connected")

    agent = LiveAgent()
    workflow_id: Optional[str] = None

    try:
        # Step 1: Receive session initialization
        init_data = await websocket.receive_text()
        init = json.loads(init_data)

        home_team = init.get("home_team", "Home Team")
        away_team = init.get("away_team", "Away Team")
        sport = init.get("sport", "soccer")

        # Create workflow context
        context = WorkflowContext(
            match_id=f"{home_team}_{away_team}",
            home_team=home_team,
            away_team=away_team,
            sport=sport,
            session_id=str(websocket.client)
        )

        workflow_id = await orchestrator.start_workflow(context)

        await websocket.send_text(json.dumps({
            "type": "status",
            "message": f"🔬 Researching {home_team} vs {away_team}... Stand by.",
            "workflow_id": workflow_id
        }))

        # Initialize session
        await agent.start_session(home_team, away_team, sport)

        await websocket.send_text(json.dumps({
            "type": "ready",
            "message": "✅ Ready! Push to talk and ask me anything."
        }))

        # Step 2: Stream audio chunks
        while True:
            try:
                audio_chunk = await asyncio.wait_for(
                    websocket.receive_bytes(),
                    timeout=60.0
                )
                await agent.stream_audio(audio_chunk, websocket)

            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "type": "info",
                    "message": "Session idle timeout. Please reconnect."
                }))
                break

    except WebSocketDisconnect:
        logger.info("Live session disconnected", workflow_id=workflow_id)
        if workflow_id:
            await orchestrator.finalize_workflow(workflow_id)

    except Exception as exc:
        logger.error("live_session_error", error=str(exc), exc_info=True)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Session error: {str(exc)}"
            }))
        except:
            pass
        if workflow_id:
            await orchestrator.finalize_workflow(workflow_id, success=False)


# ── Commentary Notes Endpoint ──────────────────────────────────────────────────

@app.post("/api/v1/commentary/prepare-notes", dependencies=[Depends(rate_limit_check)])
async def prepare_commentary_notes(req: CommentaryNotesRequest) -> dict:
    """
    Prepare professional Peter Drury-style commentary notes.

    Orchestrates multi-agent system to research:
    - 25 players per team
    - Team form and tactical patterns
    - Historical context and storylines
    - Weather conditions and impact
    - Key player matchups
    - Current team news and injuries

    Returns:
        - markdown_notes: Professional commentary notes in Markdown format
        - json_structure: Complete structured data for programmatic access
        - preparation_time_ms: Time taken to generate notes
        - quality_metrics: Data completeness and source tracking
    """
    logger.log_event("commentary_notes_requested", {
        "home_team": req.home_team,
        "away_team": req.away_team,
        "sport": req.sport,
        "venue": req.venue
    })

    try:
        from workflows import CommentaryNotesState, create_workflow

        # Initialize workflow state
        workflow_state = CommentaryNotesState(
            match_id=f"{req.home_team}_{req.away_team}_{req.match_datetime}",
            home_team=req.home_team,
            away_team=req.away_team,
            sport=req.sport,
            match_datetime=req.match_datetime,
            venue=req.venue,
            venue_lat=req.venue_lat,
            venue_lon=req.venue_lon,
        )

        # Run workflow directly
        workflow = create_workflow()
        completed_state = await workflow.run_workflow(workflow_state)


        # Calculate preparation time
        duration_ms = (completed_state.end_time - completed_state.start_time).total_seconds() * 1000 if completed_state.end_time else 0

        response = {
            "status": "success",
            "workflow_id": completed_state.workflow_id,
            "match": f"{req.home_team} vs {req.away_team}",
            "sport": req.sport,
            "markdown_notes": completed_state.markdown_notes or "",
            "preparation_time_ms": duration_ms,
            "agents_completed": len(completed_state.completed_agents),
            "errors": completed_state.errors,
            "warnings": completed_state.warnings,
        }

        if req.include_embedded_json:
            response["json_structure"] = completed_state.json_structure or {}

        logger.log_event("commentary_notes_generated", {
            "workflow_id": completed_state.workflow_id,
            "preparation_time_ms": duration_ms,
            "agents": len(completed_state.completed_agents),
            "notes_length": len(completed_state.markdown_notes or "")
        })

        return response

    except TimeoutError as exc:
        error_msg = f"Commentary preparation timeout: {str(exc)}"
        logger.error("commentary_notes_timeout", error=error_msg)
        raise HTTPException(status_code=504, detail=error_msg)

    except Exception as exc:
        error_msg = f"Commentary preparation failed: {str(exc)}"
        logger.error("commentary_notes_failed", error=error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


# ── Error Handlers ─────────────────────────────────────────────────────────────

@app.exception_handler(RateLimitError)
async def rate_limit_handler(request, exc):
    """Handle rate limit errors."""
    return {
        "error": "RATE_LIMIT_EXCEEDED",
        "message": exc.message,
        "retry_after": 60
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL,
        reload=True
    )
