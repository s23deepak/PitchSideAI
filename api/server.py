"""
Production-level FastAPI Server — PitchSide AI Backend
Integrates orchestration, RAG, concurrency control, and monitoring.
"""
import base64
import json
import logging
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from config import AWS_REGION, PORT, LOG_LEVEL
from config.sports import SportType
from core import setup_logging, get_logger, get_rate_limiter, RateLimitConfig
from core.exceptions import RateLimitError, WorkflowExecutionError
from orchestration.engine import get_orchestrator
from orchestration.types import WorkflowContext, AgentType, WorkflowState
from rag import get_rag_retriever, RAGStrategy
from agents.live_agent import LiveAgent
from agents.vision_agent import VisionAgent
from agents.research_agent import ResearchAgent
from tools.dynamodb_tool import build_match_session_key, get_recent_events, write_event
from models.game_state import GameState

# Setup production logging
setup_logging(level=LOG_LEVEL, json_logs=True)
logger = get_logger(__name__)

NATIVE_VIDEO_BACKENDS = {"bedrock", "vllm"}


def _is_context_length_error(exc: Exception) -> bool:
    """Detect model-input-overflow errors from OpenAI-compatible backends."""
    message = str(exc).lower()
    return (
        "maximum context length" in message
        or "input length" in message
        or "context length" in message
        or "too many tokens" in message
    )


# ── Request/Response Models ────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    """Request to build pre-match research brief."""
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    sport: str = Field(default="soccer", pattern="^(soccer|cricket)$")


class FrameAnalysisRequest(BaseModel):
    """Request for video frame tactical analysis."""
    frame_b64: str = Field(..., description="Base64-encoded JPEG")
    sport: str = Field(
        default="soccer",
        pattern="^(soccer|cricket|basketball|tennis|rugby|american_football|hockey|baseball)$"
    )
    timestamp: Optional[int] = None
    match_session: Optional[str] = None


class VideoAnalysisRequest(BaseModel):
    """Request for multi-frame video tactical analysis."""
    video_b64: Optional[str] = None
    video_format: Optional[str] = Field(default="mp4", pattern="^(mkv|mov|mp4|webm|flv|mpeg|mpg|wmv|three_gp)$")
    frames_b64: Optional[list[str]] = Field(default=None, min_length=2, max_length=64)
    timestamps_ms: Optional[list[int]] = Field(default=None, min_length=2, max_length=64)
    sport: str = Field(
        default="soccer",
        pattern="^(soccer|cricket|basketball|tennis|rugby|american_football|hockey|baseball)$"
    )
    match_session: Optional[str] = None


class QueryRequest(BaseModel):
    """Text-based Q&A query."""
    query: str = Field(..., min_length=1, max_length=500)
    home_team: str = Field(default="Team A")
    away_team: str = Field(default="Team B")
    sport: str = Field(default="soccer", pattern="^(soccer|cricket|basketball|tennis|rugby|american_football|hockey|baseball)$")
    rag_strategy: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid|cross_encoder)$")
    match_session: Optional[str] = None


class CommentaryNotesRequest(BaseModel):
    """Request for professional commentary notes preparation."""
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    sport: str = Field(default="soccer", pattern="^(soccer|cricket|basketball|rugby|tennis|hockey|baseball)$")
    match_datetime: Optional[str] = None
    venue: Optional[str] = None
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


# ── Connection Manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts to sessions."""

    def __init__(self):
        self._sessions: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        self._sessions[session_id].append(ws)

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        self._sessions[session_id] = [w for w in self._sessions[session_id] if w is not ws]

    async def broadcast(self, session_id: str, message: dict) -> None:
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in list(self._sessions.get(session_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def send(self, ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            pass


manager = ConnectionManager()


def _format_video_timestamp_ms(timestamp_ms: int | float | None) -> str | None:
    """Format a millisecond timestamp into mm:ss or hh:mm:ss."""
    if not isinstance(timestamp_ms, (int, float)) or timestamp_ms < 0:
        return None

    total_seconds = int(timestamp_ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _format_tactical_commentary_note(analysis: dict) -> str:
    """Create a compact analyst note from a tactical detection payload."""
    label = (analysis.get("tactical_label") or "Tactical read").strip()
    observation = (analysis.get("key_observation") or "No observation provided.").strip()
    insight = (analysis.get("actionable_insight") or "").strip()
    confidence = analysis.get("confidence")
    video_timestamp_ms = analysis.get("timestamp_ms")
    video_moments = analysis.get("video_moments") or []
    clip_start = _format_video_timestamp_ms(analysis.get("clip_start_timestamp_ms"))
    clip_end = _format_video_timestamp_ms(analysis.get("clip_end_timestamp_ms"))

    confidence_text = ""
    if isinstance(confidence, (int, float)):
        confidence_text = f" ({round(confidence * 100)}% confidence)"

    if len(video_moments) > 1 and clip_start and clip_end:
        transition_points = []
        for moment in video_moments[:4]:
            moment_time = _format_video_timestamp_ms(moment.get("timestamp_ms"))
            moment_label = moment.get("tactical_label")
            if moment_time and moment_label:
                transition_points.append(f"{moment_time} {moment_label}")
        transitions_text = "; ".join(transition_points)
        primary_time = _format_video_timestamp_ms(video_timestamp_ms)
        note = (
            f"Analyst note across {clip_start}–{clip_end}: {observation} "
            f"Sequence: {transitions_text}."
        )
        if primary_time:
            note += f" Primary moment at {primary_time}: {label}{confidence_text}."
        else:
            note += f" Primary moment: {label}{confidence_text}."
    else:
        time_text = ""
        formatted = _format_video_timestamp_ms(video_timestamp_ms)
        if formatted:
            time_text = f" at {formatted}"
        note = f"Analyst note{time_text}: {label}{confidence_text}. {observation}"

    if insight:
        note += f" Commentary cue: {insight}"
    return note


async def _periodic_commentary(
    session_id: str,
    agent,
    match_session: str,
    interval: int = 60,
    game_state: Optional[GameState] = None,
) -> None:
    """Background task: generate contextual commentary every `interval` seconds."""
    await asyncio.sleep(interval)
    while True:
        try:
            recent = await get_recent_events(5, match_session=match_session)
            events_text = "; ".join(
                e.get("description", "") for e in recent if e.get("description")
            )
            seed = f"Match update — recent context: {events_text}" if events_text else "Ongoing match update"
            if game_state:
                ctx = game_state.to_context_string()
                if ctx:
                    seed = f"{ctx}\n{seed}"
            text = await agent.generate_live_commentary(seed)
            broadcast_msg = {
                "type": "commentary",
                "text": text,
                "source": "timer",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if game_state:
                broadcast_msg["gameState"] = game_state.to_dict()
            await manager.broadcast(session_id, broadcast_msg)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("periodic_commentary_failed", error=str(exc))
        await asyncio.sleep(interval)


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

# Shared agent instances (football/soccer only)
vision_agents: dict[str, VisionAgent] = {
    SportType.SOCCER.value: VisionAgent(sport=SportType.SOCCER.value),
}
research_agent = ResearchAgent()
orchestrator = get_orchestrator()


def get_vision_agent(sport: str) -> VisionAgent:
    """Return a cached vision agent for the requested sport."""
    normalized_sport = (sport or SportType.SOCCER.value).strip().lower()
    if normalized_sport not in vision_agents:
        vision_agents[normalized_sport] = VisionAgent(sport=normalized_sport)
    return vision_agents[normalized_sport]


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
        agent = get_vision_agent(req.sport)
        result = await agent.analyze_frame_b64(req.frame_b64, match_session=req.match_session)

        return {
            "status": "success",
            "analysis": result,
            "timestamp": req.timestamp
        }

    except Exception as exc:
        logger.error("frame_analysis_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/video/analyze", dependencies=[Depends(rate_limit_check)])
async def analyze_video(req: VideoAnalysisRequest) -> dict:
    """Analyze an uploaded video clip using full native video, native windows, or sampled frames."""
    agent = get_vision_agent(req.sport)
    native_video_enabled = agent.backend in NATIVE_VIDEO_BACKENDS
    use_native_video = native_video_enabled and bool(req.video_b64)
    native_video_fallback_reason: str | None = None
    analysis_path = "sampled_frames"
    native_video_used = False

    logger.log_event(
        "video_analysis_requested",
        {
            "sport": req.sport,
            "native_video_requested": bool(req.video_b64),
            "native_video_enabled": native_video_enabled,
            "native_video": use_native_video,
            "frames": len(req.frames_b64 or []),
        },
    )

    try:
        if use_native_video:
            try:
                sequence_analysis = await agent.analyze_video_clip_b64(
                    req.video_b64,
                    video_format=req.video_format or "mp4",
                    match_session=req.match_session,
                )
                analysis_path = sequence_analysis.get("native_video_strategy") or "full_clip"
                native_video_used = True
            except Exception as exc:
                if not _is_context_length_error(exc) or not req.frames_b64 or not req.timestamps_ms:
                    raise

                try:
                    sequence_analysis = await agent.analyze_video_clip_windowed_b64(
                        req.video_b64,
                        video_format=req.video_format or "mp4",
                        match_session=req.match_session,
                    )
                    native_video_fallback_reason = "native full-clip input exceeded model context length; used overlapping native-video windows"
                    analysis_path = sequence_analysis.get("native_video_strategy") or "windowed"
                    native_video_used = True
                    logger.warning(
                        "video_analysis_native_windowed",
                        sport=req.sport,
                        backend=agent.backend,
                        reason=native_video_fallback_reason,
                        windows=sequence_analysis.get("video_window_count"),
                    )
                except Exception as window_exc:
                    native_video_fallback_reason = (
                        "native full-clip input exceeded model context length; "
                        f"windowed native-video analysis failed: {window_exc}; falling back to sampled frames"
                    )
                    logger.warning(
                        "video_analysis_native_fallback",
                        sport=req.sport,
                        backend=agent.backend,
                        reason=native_video_fallback_reason,
                        frames=len(req.frames_b64),
                    )
                    sequence_analysis = await agent.analyze_video_sequence_b64(
                        req.frames_b64,
                        timestamps_ms=req.timestamps_ms,
                        match_session=req.match_session,
                    )
                    analysis_path = sequence_analysis.get("native_video_strategy") or "sampled_frames"
        else:
            if not req.frames_b64 or not req.timestamps_ms:
                raise HTTPException(
                    status_code=400,
                    detail="frames_b64 and timestamps_ms are required when native video analysis is unavailable for the active backend",
                )
            if len(req.frames_b64) != len(req.timestamps_ms):
                raise HTTPException(status_code=400, detail="frames_b64 and timestamps_ms must have the same length")

            sequence_analysis = await agent.analyze_video_sequence_b64(
                req.frames_b64,
                timestamps_ms=req.timestamps_ms,
                match_session=req.match_session,
            )
            analysis_path = sequence_analysis.get("native_video_strategy") or "sampled_frames"

        return {
            "status": "success",
            "analysis": sequence_analysis,
            "native_video_enabled": native_video_enabled,
            "native_video_used": native_video_used,
            "analysis_path": analysis_path,
            "fallback_reason": native_video_fallback_reason,
        }
    except Exception as exc:
        logger.error("video_analysis_failed", error=str(exc))
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
        agent = LiveAgent(sport=req.sport)
        agent.home_team = req.home_team
        agent.away_team = req.away_team
        agent.match_session = req.match_session or build_match_session_key(req.home_team, req.away_team, req.sport)
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
async def get_events(n: int = 20, match_session: Optional[str] = None):
    """Get recent match events."""
    try:
        events = await get_recent_events(n, match_session=match_session)
        return {
            "status": "success",
            "events": events,
            "count": len(events),
            "match_session": match_session or "active_match",
        }
    except Exception as exc:
        logger.error("events_fetch_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/events/stream")
async def events_stream(request: Request, n: int = 20, match_session: Optional[str] = None):
    """Server-Sent Events stream — pushes new DynamoDB events every 3 seconds."""
    async def generator():
        last_id: Optional[str] = None
        while True:
            if await request.is_disconnected():
                break
            try:
                events = await get_recent_events(n, match_session=match_session)
                newest_id = events[0].get("id") if events else None
                if newest_id and newest_id != last_id:
                    last_id = newest_id
                    yield f"data: {json.dumps(events)}\n\n"
            except Exception as exc:
                logger.error("sse_poll_failed", error=str(exc))
            await asyncio.sleep(3)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── WebSocket — Live Session ────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def live_audio_ws(websocket: WebSocket):
    """
    Bidirectional WebSocket for live match sessions.

    Text frames (JSON):
      -> {"type": "init",        "home_team": "...", "away_team": "...", "sport": "..."}
      -> {"type": "match_event", "description": "Haaland scores! 1-0 in 34'"}
            -> {"type": "tactical_detection", "analysis": {"tactical_label": "...", ...}}
      -> {"type": "query",       "text": "Who scored the last goal?"}
      <- {"type": "ready",       "message": "..."}
            <- {"type": "commentary",  "text": "...", "source": "event|timer|detection|analysis", "timestamp": "..."}
      <- {"type": "answer",      "text": "...", "timestamp": "..."}

    Binary frames: raw audio bytes (future Nova Sonic integration)
    """
    await websocket.accept()
    logger.info("New live session connected")

    agent = LiveAgent()
    workflow_id: Optional[str] = None
    periodic_task: Optional[asyncio.Task] = None
    match_session: Optional[str] = None

    try:
        # Step 1: Init message
        init_data = await websocket.receive_text()
        init = json.loads(init_data)

        home_team = init.get("home_team", "Home Team")
        away_team = init.get("away_team", "Away Team")
        sport = init.get("sport", "soccer")
        match_session = build_match_session_key(home_team, away_team, sport)
        game_state = GameState(home_team=home_team, away_team=away_team)

        context = WorkflowContext(
            match_id=match_session,
            home_team=home_team,
            away_team=away_team,
            sport=sport,
            session_id=str(websocket.client),
        )
        workflow_id = await orchestrator.start_workflow(context)

        await manager.connect(workflow_id, websocket)

        await manager.send(websocket, {
            "type": "status",
            "message": f"Researching {home_team} vs {away_team}...",
            "workflow_id": workflow_id,
            "match_session": match_session,
        })

        await agent.start_session(home_team, away_team, sport, match_session=match_session)

        await manager.send(websocket, {
            "type": "ready",
            "message": "Session ready. Commentary will fire on events, frame detections, and every 60 s.",
            "match_session": match_session,
        })

        # Start periodic commentary background task
        periodic_task = asyncio.create_task(
            _periodic_commentary(workflow_id, agent, match_session, game_state=game_state)
        )

        # Step 2: Message loop — handles text (events/queries) and binary (audio)
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=120.0)
            except asyncio.TimeoutError:
                await manager.send(websocket, {
                    "type": "info",
                    "message": "Session idle. Reconnect to continue.",
                })
                break

            if msg["type"] == "websocket.disconnect":
                break

            # ── Text frames ────────────────────────────────────────────────────
            if msg.get("text"):
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "match_event":
                    description = data.get("description", "").strip()
                    if not description:
                        continue
                    game_state.update_from_event(description)
                    seed = description
                    ctx = game_state.to_context_string()
                    if ctx:
                        seed = f"{ctx}\n{description}"
                    text = await agent.generate_live_commentary(seed)
                    broadcast_msg = {
                        "type": "commentary",
                        "text": text,
                        "source": "event",
                        "trigger": description,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "gameState": game_state.to_dict(),
                    }
                    await manager.broadcast(workflow_id, broadcast_msg)

                elif msg_type == "tactical_detection":
                    analysis = data.get("analysis") or {}
                    if not isinstance(analysis, dict):
                        continue

                    game_state.update_from_detection(analysis)
                    note_text = _format_tactical_commentary_note(analysis)
                    timestamp = datetime.now(timezone.utc).isoformat()

                    await write_event(
                        "tactical_analyst_note",
                        note_text,
                        {
                            "analysis": analysis,
                            "sport": sport,
                            "home_team": home_team,
                            "away_team": away_team,
                        },
                        match_session=match_session,
                    )

                    await manager.broadcast(workflow_id, {
                        "type": "commentary",
                        "text": note_text,
                        "source": "detection",
                        "label": analysis.get("tactical_label"),
                        "confidence": analysis.get("confidence"),
                        "videoTimestampMs": analysis.get("timestamp_ms"),
                        "videoRangeLabel": (
                            f"{_format_video_timestamp_ms(analysis.get('clip_start_timestamp_ms'))}–{_format_video_timestamp_ms(analysis.get('clip_end_timestamp_ms'))}"
                            if _format_video_timestamp_ms(analysis.get('clip_start_timestamp_ms')) and _format_video_timestamp_ms(analysis.get('clip_end_timestamp_ms'))
                            else None
                        ),
                        "trigger": analysis.get("actionable_insight") or analysis.get("key_observation"),
                        "timestamp": timestamp,
                    })

                    commentary_seed = (
                        analysis.get("sequence_summary")
                        or analysis.get("actionable_insight")
                        or analysis.get("key_observation")
                        or analysis.get("tactical_label")
                    )
                    temporal_change = analysis.get("key_observation")
                    if analysis.get("video_moments"):
                        commentary_seed = (
                            f"Video clip from {analysis.get('clip_start_timestamp_ms', 0)} ms to "
                            f"{analysis.get('clip_end_timestamp_ms', 0)} ms. "
                            f"Sequence: {analysis.get('sequence_summary', '')}. "
                            f"Temporal read: {temporal_change}."
                        )

                    if commentary_seed:
                        timestamp_prefix = ""
                        timestamp_ms = analysis.get("timestamp_ms")
                        if isinstance(timestamp_ms, (int, float)) and timestamp_ms >= 0:
                            total_seconds = int(timestamp_ms // 1000)
                            minutes, seconds = divmod(total_seconds, 60)
                            hours, minutes = divmod(minutes, 60)
                            formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
                            timestamp_prefix = f"Video timestamp {formatted}: "

                        full_seed = f"{timestamp_prefix}{commentary_seed}"
                        ctx = game_state.to_context_string()
                        if ctx:
                            full_seed = f"{ctx}\n{full_seed}"

                        text = await agent.generate_live_commentary(full_seed)
                        await manager.broadcast(workflow_id, {
                            "type": "commentary",
                            "text": text,
                            "source": "analysis",
                            "label": analysis.get("tactical_label"),
                            "confidence": analysis.get("confidence"),
                            "videoTimestampMs": analysis.get("timestamp_ms"),
                            "videoRangeLabel": (
                                f"{_format_video_timestamp_ms(analysis.get('clip_start_timestamp_ms'))}–{_format_video_timestamp_ms(analysis.get('clip_end_timestamp_ms'))}"
                                if _format_video_timestamp_ms(analysis.get('clip_start_timestamp_ms')) and _format_video_timestamp_ms(analysis.get('clip_end_timestamp_ms'))
                                else None
                            ),
                            "trigger": analysis.get("actionable_insight") or analysis.get("key_observation"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "gameState": game_state.to_dict(),
                        })

                elif msg_type == "query":
                    query_text = data.get("text", "").strip()
                    if not query_text:
                        continue
                    answer = await agent.handle_text_query(query_text)
                    await manager.send(websocket, {
                        "type": "answer",
                        "text": answer,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            # ── Binary frames (audio) ──────────────────────────────────────────
            elif msg.get("bytes"):
                await agent.stream_audio(msg["bytes"])

    except WebSocketDisconnect:
        logger.info("Live session disconnected", workflow_id=workflow_id)

    except Exception as exc:
        logger.error("live_session_error", error=str(exc), exc_info=True)
        await manager.send(websocket, {"type": "error", "message": str(exc)})

    finally:
        if periodic_task:
            periodic_task.cancel()
        if workflow_id:
            manager.disconnect(workflow_id, websocket)
            await orchestrator.finalize_workflow(workflow_id)


# ── WebSocket — Chunked Video Streaming ─────────────────────────────────────────

class ChunkedVideoConfig(BaseModel):
    """Configuration for chunked video streaming."""
    chunk_interval_seconds: int = Field(default=10, ge=5, le=30)
    max_chunk_frames: int = Field(default=12, ge=4, le=24)
    quality: str = Field(default="medium", pattern="^(low|medium|high)$")


@app.websocket("/ws/video/stream")
async def video_stream_ws(websocket: WebSocket):
    """
    WebSocket for chunked live video streaming and analysis.

    Client sends:
      -> {"type": "init", "match_session": "...", "config": {...}}  (optional config)
      -> {"type": "chunk", "frames_b64": [...], "timestamps_ms": [...]}
      -> {"type": "frame", "frame_b64": "...", "timestamp_ms": 12345}  (single frame buffering)

    Server broadcasts:
      <- {"type": "chunk_analyzed", "result": {...}}  (after each chunk is analyzed)
      <- {"type": "commentary", "text": "...", "source": "video_chunk"}
    """
    await websocket.accept()
    logger.info("Video streaming session connected")

    vision_agent = VisionAgent(sport="soccer")
    live_agent = LiveAgent()
    match_session: Optional[str] = None
    chunk_buffer: List[Dict[str, Any]] = []
    chunk_config = ChunkedVideoConfig()
    game_state: Optional[GameState] = None

    try:
        # Wait for init message
        init_msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        init_data = json.loads(init_msg)

        if init_data.get("type") != "init":
            await manager.send(websocket, {"type": "error", "message": "Expected 'init' message first"})
            return

        match_session = init_data.get("match_session", f"video_{datetime.now(timezone.utc).isoformat()}")
        config_data = init_data.get("config", {})

        # Parse optional config
        try:
            chunk_config = ChunkedVideoConfig(**config_data)
        except Exception as exc:
            logger.warning("video_stream_invalid_config", error=str(exc))

        await manager.send(websocket, {
            "type": "ready",
            "message": f"Ready for video chunks (interval: {chunk_config.chunk_interval_seconds}s, max frames: {chunk_config.max_chunk_frames})",
            "match_session": match_session,
        })

        # Streaming loop
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=300.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send(websocket, {"type": "ping", "message": "Still connected?"})
                continue

            if msg["type"] == "websocket.disconnect":
                break

            if msg.get("text"):
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "frame":
                    # Buffer individual frames until chunk is complete
                    frame_b64 = data.get("frame_b64")
                    timestamp_ms = data.get("timestamp_ms", len(chunk_buffer) * 1000)

                    if frame_b64:
                        chunk_buffer.append({"frame_b64": frame_b64, "timestamp_ms": timestamp_ms})

                        # Check if chunk is complete
                        if len(chunk_buffer) >= chunk_config.max_chunk_frames:
                            await _process_video_chunk(
                                websocket, vision_agent, live_agent,
                                chunk_buffer, match_session, game_state
                            )
                            chunk_buffer = []

                elif msg_type == "chunk":
                    # Client sends a complete chunk
                    frames_b64 = data.get("frames_b64", [])
                    timestamps_ms = data.get("timestamps_ms", [])

                    if frames_b64:
                        # Generate timestamps if not provided
                        if not timestamps_ms or len(timestamps_ms) != len(frames_b64):
                            timestamps_ms = [i * 1000 for i in range(len(frames_b64))]
                        await _process_video_chunk(
                            websocket, vision_agent, live_agent,
                            [{"frame_b64": f, "timestamp_ms": ts} for f, ts in zip(frames_b64, timestamps_ms)],
                            match_session, game_state,
                        )

                elif msg_type == "game_state_update":
                    # Client sends game state update
                    if game_state is None:
                        home = data.get("home_team", "Home")
                        away = data.get("away_team", "Away")
                        game_state = GameState(home_team=home, away_team=away)
                    else:
                        # Update existing game state
                        score_home = data.get("home_score")
                        score_away = data.get("away_score")
                        minute = data.get("minute")
                        if score_home is not None:
                            game_state.home_score = score_home
                        if score_away is not None:
                            game_state.away_score = score_away
                        if minute is not None:
                            game_state.match_minute = minute

            elif msg.get("bytes"):
                # Binary frame (JPEG) - buffer it
                frame_b64 = base64.b64encode(msg["bytes"]).decode("utf-8")
                timestamp_ms = len(chunk_buffer) * 1000
                chunk_buffer.append({"frame_b64": frame_b64, "timestamp_ms": timestamp_ms})

                if len(chunk_buffer) >= chunk_config.max_chunk_frames:
                    await _process_video_chunk(
                        websocket, vision_agent, live_agent,
                        chunk_buffer, match_session, game_state
                    )
                    chunk_buffer = []

    except WebSocketDisconnect:
        logger.info("Video streaming session disconnected")
    except Exception as exc:
        logger.error("video_stream_error", error=str(exc), exc_info=True)
        await manager.send(websocket, {"type": "error", "message": str(exc)})


async def _process_video_chunk(
    websocket: WebSocket,
    vision_agent: VisionAgent,
    live_agent: LiveAgent,
    chunk_data: List[Dict[str, Any]],
    match_session: str,
    game_state: Optional[GameState],
):
    """Process a chunk of video frames and broadcast commentary."""
    try:
        frames_b64 = [item["frame_b64"] for item in chunk_data]
        timestamps_ms = [item["timestamp_ms"] for item in chunk_data]

        # Analyze chunk
        result = await vision_agent.analyze_chunked_frames_b64(
            frames_b64,
            timestamps_ms=timestamps_ms,
            match_session=match_session,
            chunk_description=f"Live chunk: {len(frames_b64)} frames",
        )

        # Broadcast analysis result
        await manager.send(websocket, {
            "type": "chunk_analyzed",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Generate and broadcast commentary if confidence is high enough
        confidence = result.get("confidence", 0.0)
        if confidence > 0.5:
            seed = result.get("sequence_summary") or result.get("key_observation") or result.get("tactical_label")
            if seed:
                if game_state:
                    ctx = game_state.to_context_string()
                    if ctx:
                        seed = f"{ctx}\n{seed}"

                commentary_text = await live_agent.generate_live_commentary(seed)

                await manager.send(websocket, {
                    "type": "commentary",
                    "text": commentary_text,
                    "source": "video_chunk",
                    "tactical_label": result.get("tactical_label"),
                    "confidence": confidence,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "gameState": game_state.to_dict() if game_state else None,
                })

    except Exception as exc:
        logger.error("video_chunk_processing_error", error=str(exc))
        await manager.send(websocket, {
            "type": "error",
            "message": f"Chunk processing failed: {str(exc)}",
        })


# ── Commentary Notes Endpoint ──────────────────────────────────────────────────

@app.post("/api/v1/commentary/prepare-notes", dependencies=[Depends(rate_limit_check)])
async def prepare_commentary_notes(req: CommentaryNotesRequest, request: Request) -> StreamingResponse:
    """
    Prepare professional Peter Drury-style commentary notes.
    Streams SSE progress events, then the final result as the last event.
    """
    logger.log_event("commentary_notes_requested", {
        "home_team": req.home_team,
        "away_team": req.away_team,
        "sport": req.sport,
        "venue": req.venue
    })

    async def generate():
        import json as _json
        try:
            from workflows import CommentaryNotesState, create_workflow

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

            async def on_progress(phase: str, message: str, extra: dict):
                event = {"phase": phase, "message": message, "done": extra.get("done", False)}
                yield f"data: {_json.dumps(event)}\n\n"

            workflow = create_workflow()

            # We need a workaround: run_workflow calls on_progress which yields,
            # but we can't yield from inside the callback. Use a queue instead.
            progress_queue: asyncio.Queue = asyncio.Queue()

            async def _queue_progress(phase: str, message: str, extra: dict):
                await progress_queue.put({"phase": phase, "message": message, "done": extra.get("done", False)})

            async def _run():
                try:
                    result = await workflow.run_workflow(workflow_state, on_progress=_queue_progress)
                    await progress_queue.put(("__done__", result))
                except Exception as exc:
                    await progress_queue.put(("__error__", exc))

            task = asyncio.create_task(_run())

            try:
                while True:
                    if await request.is_disconnected():
                        logger.info("commentary_notes_client_disconnected")
                        return

                    try:
                        item = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue  # re-check disconnect

                    if isinstance(item, tuple):
                        tag, payload = item
                        if tag == "__done__":
                            completed_state = payload
                            break
                        elif tag == "__error__":
                            yield f"data: {_json.dumps({'phase': 'error', 'message': str(payload), 'done': True})}\n\n"
                            return
                    else:
                        yield f"data: {_json.dumps(item)}\n\n"
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info("commentary_notes_workflow_cancelled")

            await task  # ensure cleanup (already done if cancelled)

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

            yield f"data: {_json.dumps({'phase': 'complete', 'message': 'Done', 'done': True, 'result': response})}\n\n"

        except Exception as exc:
            error_msg = f"Commentary preparation failed: {str(exc)}"
            logger.error("commentary_notes_failed", error=error_msg, exc_info=True)
            yield f"data: {_json.dumps({'phase': 'error', 'message': error_msg, 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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
