"""
Production-level FastAPI Server — PitchSideAI Backend
Integrates orchestration, RAG, concurrency control, and monitoring.
"""
import base64
import json
import logging
import asyncio
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict
import httpx

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field
import os
import structlog

from config import (
    AWS_REGION,
    LOG_LEVEL,
    PORT,
    RATE_LIMIT_BURST,
    RATE_LIMIT_RPM,
    STREAMING_BACKEND,
    VLLM_BASE_URL,
    VLLM_VISION_MODEL,
)
from config.sports import SportType
from core import setup_logging, get_logger, get_rate_limiter, RateLimitConfig
from core.exceptions import RateLimitError, WorkflowExecutionError
from orchestration.engine import get_orchestrator
from orchestration.types import WorkflowContext, AgentType, WorkflowState
from rag import get_rag_retriever, RAGStrategy
from agents.live_agent import LiveAgent
from agents.vision_agent import VisionAgent
from agents.research_agent import ResearchAgent
from agents.qa_agent import QAAgent, QAPair
from agents.player_id_agent import PlayerIDAgent
from tools.dynamodb_tool import build_match_session_key, get_recent_events, write_event
from models.game_state import GameState
from models.session_persistence import SessionPersistence
from streaming import StreamingVisionBridge
from streaming.streaming_bridge import StreamingBridgeConfig, clean_model_answer
from api.live_contract import parse_live_init_message

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


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    status: str
    service: str
    version: str
    timestamp: str
    checks: Dict[str, Dict[str, Any]]


# ── Dependency Injection ───────────────────────────────────────────────────────

def _client_id_from_request(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"api-key:{api_key}"

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"

    if request.client and request.client.host:
        return f"ip:{request.client.host}"

    return "anonymous"


async def rate_limit_check(request: Request) -> None:
    """Rate limit by API key when present, otherwise by client IP."""
    client_id = _client_id_from_request(request)
    rate_limiter = get_rate_limiter(RateLimitConfig(
        requests_per_minute=RATE_LIMIT_RPM,
        burst_size=RATE_LIMIT_BURST,
    ))
    allowed, error_msg = await rate_limiter.check_rate_limit(client_id)

    if not allowed:
        raise HTTPException(status_code=429, detail=error_msg)


# ── Application Lifespan ───────────────────────────────────────────────────────

# Singleton streaming backend — loaded once, reused across all /api/v1/video/qa requests
_streaming_vlm_singleton: Optional[Any] = None
_streaming_vlm_lock = asyncio.Lock()


async def get_or_init_streaming_backend(backend: str):
    """Return a cached backend, initializing it on first call."""
    global _streaming_vlm_singleton
    if _streaming_vlm_singleton is not None:
        return _streaming_vlm_singleton
    async with _streaming_vlm_lock:
        # Double-check after acquiring lock
        if _streaming_vlm_singleton is not None:
            return _streaming_vlm_singleton
        from streaming.factory import FallbackStreamingBackend, get_streaming_backend as _gsb
        if backend == "auto":
            _b = FallbackStreamingBackend(start_level=1)
        else:
            _b = _gsb(backend=backend)
        await _b.initialize()
        _streaming_vlm_singleton = _b
        return _b


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("🏟️  PitchSideAI backend starting...")

    # Initialize orchestrator
    orchestrator = get_orchestrator(max_concurrent=20)

    # Start task queue processor
    task_processor = asyncio.create_task(orchestrator.process_task_queue())

    try:
        from models.notes_jobs import init_notes_job_db
        await init_notes_job_db()
        logger.info("Notes job tables ready.")
    except Exception as exc:
        logger.warning(f"Notes job database initialization failed: {exc}")

    # Pre-warm the streaming VLM backend so first video Q&A request is fast
    if STREAMING_BACKEND == "streaming_vlm" or STREAMING_BACKEND == "auto":
        try:
            logger.info("Pre-warming StreamingVLM backend...")
            await get_or_init_streaming_backend(STREAMING_BACKEND)
            logger.info("StreamingVLM backend warmed up and ready.")
        except Exception as exc:
            logger.warning(f"StreamingVLM pre-warm failed (will init on first request): {exc}")

    yield

    # Cleanup
    task_processor.cancel()
    logger.info("PitchSideAI backend shutting down.")


# ── Connection Manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts to sessions."""

    def __init__(self):
        self._sessions: dict[str, list[WebSocket]] = defaultdict(list)
        self._notes_stores: dict[str, Any] = {}  # match_session -> NotesStore
        self._qa_runners: dict[str, Any] = {}  # match_session -> QARunner
        self._settings: dict[str, dict] = {}  # match_session -> commentary settings
        self._languages: dict[str, str] = {}  # match_session -> language code
        self._vision_context: dict[str, Any] = {}  # match_session -> VisionTacticalContext
        self._persistence = SessionPersistence()

    def store_notes(self, match_session: str, notes_store: Any) -> None:
        """Store NotesStore for a match session."""
        self._notes_stores[match_session] = notes_store
        self._persistence.save_notes(match_session, notes_store)

    def get_notes(self, match_session: str) -> Optional[Any]:
        """Retrieve NotesStore for a match session."""
        notes_store = self._notes_stores.get(match_session)
        if notes_store is None:
            notes_store = self._persistence.load_notes(match_session)
            if notes_store is not None:
                self._notes_stores[match_session] = notes_store
        return notes_store

    def store_qa_runner(self, match_session: str, runner: Any) -> None:
        """Store Q&A parallel runner for a match session."""
        self._qa_runners[match_session] = runner

    def get_qa_runner(self, match_session: str) -> Optional[Any]:
        """Retrieve Q&A parallel runner for a match session."""
        return self._qa_runners.get(match_session)

    def store_settings(self, match_session: str, settings: dict) -> None:
        """Store commentary settings for a match session."""
        self._settings[match_session] = settings
        self._persistence.save_value(match_session, "settings", settings)

    def get_settings(self, match_session: str) -> dict:
        """Retrieve commentary settings for a match session."""
        default = {
            "bias": 0,
            "excitement": 0.5,
            "knowledge_depth": 0.5,
        }
        if match_session in self._settings:
            return self._settings[match_session]
        settings = self._persistence.load_value(match_session, "settings", default)
        self._settings[match_session] = settings
        return settings

    def store_language(self, match_session: str, language: str) -> None:
        """Store commentary language for a match session."""
        self._languages[match_session] = language
        self._persistence.save_value(match_session, "language", language)

    def get_language(self, match_session: str) -> str:
        """Retrieve commentary language for a match session."""
        if match_session in self._languages:
            return self._languages[match_session]
        language = self._persistence.load_value(match_session, "language", "en")
        self._languages[match_session] = language
        return language

    def store_vision_context(self, match_session: str, vision_context: Any) -> None:
        """Store latest vision tactical context for a match session."""
        self._vision_context[match_session] = vision_context
        self._persistence.save_value(match_session, "vision_context", self._json_safe(vision_context))

    def get_vision_context(self, match_session: str) -> Optional[Any]:
        """Retrieve latest vision tactical context for a match session."""
        vision_context = self._vision_context.get(match_session)
        if vision_context is None:
            vision_context = self._persistence.load_value(match_session, "vision_context")
            if vision_context is not None:
                self._vision_context[match_session] = vision_context
        return vision_context

    def _json_safe(self, value: Any) -> Any:
        """Convert common model objects to JSON-safe values for persistence."""
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._json_safe(v) for v in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

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


async def load_notes_store_for_session(match_session: str) -> Optional[Any]:
    """Load NotesStore from hot cache, then durable Postgres storage."""
    notes_store = manager.get_notes(match_session)
    if notes_store is not None:
        return notes_store
    try:
        from models.notes_jobs import NotesJobRepository, notes_store_from_result
        repo = NotesJobRepository()
        result = await repo.get_latest_result_for_session(match_session)
        if result is not None:
            notes_store = notes_store_from_result(result)
            manager.store_notes(match_session, notes_store)
            return notes_store
    except Exception as exc:
        logger.warning(f"notes_store_postgres_load_failed: {exc}")
    return None


async def refresh_agent_notes_store(agent: Any, match_session: str) -> None:
    """Attach newly completed notes to a live agent without blocking commentary."""
    if getattr(agent, "notes_store", None) is not None:
        return
    notes_store = await load_notes_store_for_session(match_session)
    if notes_store is not None:
        agent.notes_store = notes_store


# ── Story 2.2 + 2.4: Parallel Q&A Handler ──────────────────────────────────────

async def _handle_fan_query_parallel(
    question: str,
    game_state: GameState,
    match_session: str,
    current_frame_b64: Optional[str] = None,
    vision_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Handle fan question using Stories 2.2 + 2.4 parallel agents with live vision context.

    Flow:
    1. Get or create QAAgent + PlayerIDAgent runner for session
    2. Detect if question references a player
    3. Run Q&A and Player ID in parallel if needed
    4. Merge results with overlay coordinates
    5. Include live vision tactical context for tactical questions

    Args:
        question: Fan question text
        game_state: Current match game state
        match_session: Match session key
        current_frame_b64: Optional current frame for player ID
        vision_context: Optional VisionTacticalContext from StreamingVisionBridge

    Returns:
        Dict with answer text, game state, player ID, overlay coordinates, vision context
    """
    # Get or create Q&A runner for this session
    runner = manager.get_qa_runner(match_session)

    if runner is None:
        # Fallback to simple LiveAgent handling if runner not initialized
        # This happens if pre-match notes weren't generated
        from agents.live_agent import LiveAgent
        agent = LiveAgent()
        answer = await agent.handle_text_query(question)
        return {
            "type": "answer",
            "text": answer,
            "gameState": game_state.to_dict(),
            "temporal_context": "full",
            "source": "fallback_live_agent",
        }

    settings = manager.get_settings(match_session)
    if hasattr(runner, "set_commentary_settings"):
        runner.set_commentary_settings(
            bias=settings.get("bias", 0),
            excitement=settings.get("excitement", 0.7),
            knowledge_depth=settings.get("knowledge_depth", 1),
        )

    # Use parallel runner with vision context
    result = await runner.handle_fan_question(
        question=question,
        frame_b64=current_frame_b64,
        vision_context=vision_context,
    )

    return result


def _detect_player_reference(question: str) -> bool:
    """Check if question references a player (by number or name)."""
    import re
    patterns = [
        r"number\s*\d+",  # "number 10", "who's #7"
        r"who\s+(is|just|scored)",  # "who is", "who just"
        r"\b\d+\b",  # Any number reference
    ]
    for pattern in patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return True
    return False


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


# ── Language Translation Pipeline (Story 3.4) ──────────────────────────────────

async def _translate_commentary(text: str, target_language: str, source_language: str = "en") -> str:
    """
    Translate commentary text using LLM.

    Args:
        text: Commentary text to translate
        target_language: Target language code (e.g., "es" for Spanish)
        source_language: Source language code (default: "en")

    Returns:
        Translated text
    """
    if source_language == target_language:
        return text

    language_names = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "pt": "Portuguese",
        "it": "Italian",
    }

    target_name = language_names.get(target_language, target_language)
    source_name = language_names.get(source_language, "English")

    prompt = f"""Translate the following {source_name} sports commentary to {target_name}.
Preserve the tone, style, and emotional intensity. Do not add or remove any information.
Return ONLY the translation, no explanations.

Original: {text}

Translation:"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Use the configured LLM backend for translation
            from config import (
                LLM_BACKEND,
                OPENAI_API_KEY,
                OPENAI_MODEL,
                VLLM_BASE_URL,
                VLLM_MODEL,
            )

            if LLM_BACKEND == "openai":
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json={
                        "model": OPENAI_MODEL or "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 500,
                    },
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {},
                )
            elif LLM_BACKEND == "vllm":
                response = await client.post(
                    f"{VLLM_BASE_URL}/v1/chat/completions",
                    json={
                        "model": VLLM_MODEL or "",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_completion_tokens": 500,
                    },
                )
            else:
                # Unknown backend
                logger.warning("translation_unavailable", backend=LLM_BACKEND)
                return text

            if response.status_code == 200:
                result = response.json()
                translated = result.get("choices", [{}])[0].get("message", {}).get("content", text)
                return translated.strip() or text
            else:
                logger.warning("translation_failed", status=response.status_code)
                return text

    except Exception as exc:
        logger.error("translation_error", error=str(exc))
        return text


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

            await refresh_agent_notes_store(agent, match_session)
            # Call LiveAgent (no vision label for timer-based commentary)
            result = await agent.generate_live_commentary(
                event_description=seed,
                vision_tactical_label=None,
                game_state=game_state,
                settings=manager.get_settings(match_session),
            )

            broadcast_msg = {
                "type": "commentary",
                "text": result.get("commentary", ""),
                "source": result.get("source", "timer"),
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
    title="PitchSideAI",
    version="2.0.0",
    description="Production-grade multimodal sports AI assistant",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Fix #1 & #2: CORS with safe JSON parsing and origin validation
def _parse_allowed_origins() -> list:
    """Parse ALLOWED_ORIGINS env var with validation and graceful fallback."""
    origins_env = os.getenv("ALLOWED_ORIGINS") or '["http://localhost:5173", "http://localhost:3000"]'
    try:
        allowed = json.loads(origins_env)
        # Validate: must be non-empty list of strings starting with http:// or https://
        if not isinstance(allowed, list) or not allowed:
            logger.warning("ALLOWED_ORIGINS invalid type or empty, using defaults")
            return ["http://localhost:5173", "http://localhost:3000"]
        if not all(isinstance(o, str) and o.startswith(("http://", "https://")) for o in allowed):
            logger.warning("ALLOWED_ORIGINS contains invalid origins, using defaults")
            return ["http://localhost:5173", "http://localhost:3000"]
        return allowed
    except json.JSONDecodeError as exc:
        logger.warning("ALLOWED_ORIGINS JSON parse failed", error=str(exc), using_defaults=True)
        return ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files (for Docker/production deployment)
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
frontend_assets = os.path.join(frontend_dist, "assets")
index_path = os.path.join(frontend_dist, "index.html")

# Fix #3: Validate directories exist BEFORE any path operations
frontend_dist_exists = os.path.isdir(frontend_dist)
frontend_assets_exists = os.path.isdir(frontend_assets)

if frontend_dist_exists and frontend_assets_exists:
    # Fix #4: Path validation BEFORE mount (not after) with OSError handling
    dist_path_resolved = None
    assets_path_resolved = None
    path_validation_failed = False

    try:
        dist_path_resolved = Path(frontend_dist).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        logger.error("frontend_dist_path_resolve_failed", path=frontend_dist, error=str(exc))
        path_validation_failed = True

    if not path_validation_failed:
        try:
            assets_path_resolved = Path(frontend_assets).resolve(strict=True)
            # Validate assets is within dist (defense in depth)
            assets_path_resolved.relative_to(dist_path_resolved)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.error("assets_path_validation_failed", path=frontend_assets, error=str(exc))
            path_validation_failed = True

    # Only mount if path validation passed
    if not path_validation_failed and assets_path_resolved:
        app.mount("/assets", StaticFiles(directory=str(assets_path_resolved)), name="assets")
        logger.info("static_files_mounted", path=str(assets_path_resolved))

    @app.get("/")
    async def serve_index():
        """Serve React app index.html for SPA routing."""
        # Fix #5: Race condition guard with proper exception handling
        try:
            index_resolved = Path(index_path).resolve(strict=True)
            # Path traversal prevention - guard against None (Patch #1)
            if dist_path_resolved:
                index_resolved.relative_to(dist_path_resolved)
            # Existence check (re-verify after resolve to catch TOCTOU)
            if index_resolved.exists():
                return FileResponse(str(index_resolved))
        except (OSError, RuntimeError) as exc:
            logger.error("index_path_error", error=str(exc))
        except ValueError as exc:
            logger.warning("index_path_traversal_blocked", path=str(index_resolved) if 'index_resolved' in dir() else index_path)
        except Exception as exc:
            logger.error("index_serve_error", error=str(exc))

        # Graceful degradation: return error page instead of raw JSON error
        return HTMLResponse(
            content="""<!DOCTYPE html><html><head><title>PitchSideAI - Building</title></head>
            <body style="background:#020617;color:#f1f5f9;font-family:system-ui;padding:2rem;">
            <h1>PitchSideAI is building...</h1>
            <p>The frontend is being compiled. Please refresh in a few seconds.</p>
            <p style="color:#94a3b8;margin-top:2rem;">If this persists, check server logs or run: <code>npm run build</code> in frontend/</p>
            </body></html>""",
            status_code=503,
        )
else:
    logger.info("static_files_not_mounted", reason="frontend_dist_missing", frontend_dist=frontend_dist)

    @app.get("/")
    async def serve_index():
        """Return API-only mode notice."""
        return HTMLResponse(
            content="""<!DOCTYPE html><html><head><title>PitchSideAI - API Mode</title></head>
            <body style="background:#020617;color:#f1f5f9;font-family:system-ui;padding:2rem;">
            <h1>PitchSideAI API Server</h1>
            <p>Frontend not built. Run <code>npm run build</code> in frontend/ directory.</p>
            <p style="color:#94a3b8;margin-top:2rem;">API endpoints available at /docs</p>
            </body></html>""",
            status_code=503,
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
        service="PitchSideAI",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/ready", response_model=ReadinessResponse)
async def readiness_check(response: Response):
    """Readiness check for dependencies required to serve production traffic."""
    import redis.asyncio as redis
    from sqlalchemy import text
    from config import LLM_BACKEND, OPENAI_API_KEY, REDIS_URL, VLLM_BASE_URL
    from models.notes_jobs import engine

    async def check_postgres() -> Dict[str, Any]:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception as exc:
            return {"status": "unready", "error": str(exc)}

    async def check_redis() -> Dict[str, Any]:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        try:
            await client.ping()
            return {"status": "ready"}
        except Exception as exc:
            return {"status": "unready", "error": str(exc)}
        finally:
            await client.aclose()

    async def check_llm() -> Dict[str, Any]:
        if LLM_BACKEND == "openai":
            return {"status": "ready" if bool(OPENAI_API_KEY) else "unready", "backend": "openai"}
        if LLM_BACKEND == "vllm":
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    llm_response = await client.get(f"{VLLM_BASE_URL}/v1/models")
                return {
                    "status": "ready" if llm_response.status_code < 500 else "unready",
                    "backend": "vllm",
                    "status_code": llm_response.status_code,
                }
            except Exception as exc:
                return {"status": "unready", "backend": "vllm", "error": str(exc)}
        return {"status": "unready", "backend": LLM_BACKEND, "error": "Unsupported LLM_BACKEND"}

    checks = {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "llm": await check_llm(),
    }
    is_ready = all(check["status"] == "ready" for check in checks.values())
    if not is_ready:
        response.status_code = 503

    return ReadinessResponse(
        status="ready" if is_ready else "unready",
        service="PitchSideAI",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat(),
        checks=checks,
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


# ── Video Q&A — streaming SSE endpoint ───────────────────────────────────────
# Users upload a clip and ask a question; the backend auto-selects the best
# available streaming vision backend (StreamingVLM → vLLM).
# No backend, fps, or chunk parameters are exposed to the client.

@app.post("/api/v1/video/qa")
async def video_qa(
    video: UploadFile = File(...),
    query: str = Form(default=""),
    sport: str = Form(default="soccer"),
    backend: str = Form(default=STREAMING_BACKEND),  # "streaming_vlm" | "vllm" | "auto"
) -> StreamingResponse:
    """
    Upload a video clip and ask an AI question about it.

    Returns a Server-Sent Events stream:
      data: {"type": "meta",  "backend_level": 4, "model": "Qwen2.5-VL-3B-AWQ"}
      data: {"type": "token", "text": "The ..."}
      data: {"type": "token", "text": "team is ..."}
      data: [DONE]

    The backend is automatically selected via FallbackStreamingBackend:
      Level 1: StreamingVLM (mit-han-lab/StreamingVLM) — needs 40GB+ VRAM
      Level 2: vLLM frame-by-frame (always available)
    """
    import json as _json

    video_bytes = await video.read()
    default_query = (
        f"Analyze this {sport} clip. Describe the tactical situation, "
        "key players visible, formation, and likely next move."
    )
    question = query.strip() or default_query

    async def event_stream():
        try:
            _backend = await get_or_init_streaming_backend(backend)
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        level = getattr(_backend, 'current_level', backend)
        model = os.environ.get("STREAMING_VLM_MODEL", "Qwen/Qwen3-VL-4B-Instruct")
        yield f"data: {_json.dumps({'type': 'meta', 'backend_level': level, 'model': model})}\n\n"

        try:
            # ── Sample frames from uploaded video bytes ──────────────────────
            from streaming.frame_buffer import VideoChunk, FrameSample
            import tempfile, os as _os

            frames: list[FrameSample] = []
            try:
                import cv2
                # Write to temp file (cv2 needs a path)
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp.write(video_bytes)
                    tmp_path = tmp.name
                try:
                    cap = cv2.VideoCapture(tmp_path)
                    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps_v = cap.get(cv2.CAP_PROP_FPS) or 25.0
                    # Sample 2 evenly-spaced frames (fewer visual tokens = faster)
                    n_frames = min(2, total)
                    indices = [int(i * total / n_frames) for i in range(n_frames)]
                    for idx in indices:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                        ok, frame = cap.read()
                        if not ok:
                            continue
                        # Resize to 280px on longest side — 280/14=20 patches/dim → 400 patches/frame
                        # vs 448px which gives 1024 patches/frame (2.5x more VRAM pressure)
                        h, w = frame.shape[:2]
                        scale = 280 / max(h, w)
                        if scale < 1.0:
                            frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        frames.append(FrameSample(
                            data=jpeg.tobytes(),
                            timestamp_ms=int((idx / fps_v) * 1000),
                            frame_index=idx,
                        ))
                    cap.release()
                finally:
                    _os.unlink(tmp_path)
            except ImportError:
                # cv2 not available — encode entire video as single "frame" for vLLM native video
                import base64 as _b64
                frames.append(FrameSample(
                    data=_b64.b64encode(video_bytes),  # base64 for native-video backends
                    timestamp_ms=0,
                    frame_index=0,
                ))

            if not frames:
                raise ValueError("Could not extract frames from uploaded video")

            chunk = VideoChunk(
                frames=frames,
                start_timestamp_ms=frames[0].timestamp_ms,
                end_timestamp_ms=frames[-1].timestamp_ms,
                duration_seconds=(frames[-1].timestamp_ms - frames[0].timestamp_ms) / 1000.0,
                chunk_index=0,
            )
            result = await _backend.process_chunk(chunk, query_hint=question)
            # StreamingResult is a dataclass; dicts also supported
            if isinstance(result, dict):
                text = result.get("analysis") or result.get("text") or result.get("commentary") or str(result)
            else:
                text = getattr(result, 'commentary', None) or getattr(result, 'analysis', None) or str(result)
            text = clean_model_answer(text) or "I could not produce a clear answer from this clip."

            # Stream as tokens (sentence-level for smooth UI)
            import re as _re
            sentences = _re.split(r'(?<=[.!?])\s+', text.strip())
            for sentence in sentences:
                if sentence:
                    yield f"data: {_json.dumps({'type': 'token', 'text': sentence + ' '})}\n\n"

        except Exception as e:
            logger.error("video_qa_stream_failed", error=str(e))
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Don't reset the singleton — keep model warm for next request
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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

    Answer payload (Story 2.2 + 2.4 enhanced):
      {
        "type": "answer",
        "text": "...",
        "gameState": {...},
        "temporal_context": "full" | "limited",
        "timestamp_ms": 12345,  // For split-screen navigation
        "player_identification": {  // Story 2.4
          "player_name": "Haaland",
          "confidence": 0.95,
          "source": "jersey_number + lineup_data",
          "jersey_number": 9
        },
        "overlay_coordinates": {  // Story 2.4: SVG overlay for Fan Lens
          "type": "circle" | "zone",
          "cx": 50, "cy": 50, "r": 8,  // or rx/ry for zone
          "stroke": "#00ff00", "stroke_width": 3
        }
      }

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
        try:
            init = parse_live_init_message(json.loads(init_data))
        except (json.JSONDecodeError, ValueError) as exc:
            await manager.send(websocket, {
                "type": "error",
                "message": "Invalid live session init payload",
            })
            await websocket.close(code=1008)
            logger.warning("live_session_invalid_init", error=str(exc))
            return

        home_team = init.home_team
        away_team = init.away_team
        sport = init.sport
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

        # Load NotesStore if available from pre-match generation
        notes_store = await load_notes_store_for_session(match_session)

        # Story 2.2 + 2.4: Initialize parallel Q&A runner
        from agents.qa_runner import QARunner
        qa_runner = QARunner(sport=sport)
        manager.store_qa_runner(match_session, qa_runner)

        # Send ready immediately — session init runs in the background so the
        # frontend connects without waiting for the LLM to warm up.
        await manager.send(websocket, {
            "type": "ready",
            "message": "Session ready. Commentary will fire on events, frame detections, and every 60 s. Q&A available with player identification.",
            "match_session": match_session,
            "has_notes_store": notes_store is not None,
            "qa_enhanced": True,  # Story 2.2 + 2.4 flag
        })

        # Background: build match brief + initialize Q&A (may be slow on first load)
        async def _init_session():
            try:
                await asyncio.wait_for(
                    agent.start_session(
                        home_team, away_team, sport,
                        match_session=match_session,
                        notes_store=notes_store,
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning("start_session timed out — continuing without match brief")
            except Exception as exc:
                logger.warning(f"start_session failed: {exc}")

            try:
                await asyncio.wait_for(
                    qa_runner.initialize_session(
                        home_team=home_team,
                        away_team=away_team,
                        match_session=match_session,
                        notes_store=notes_store,
                    ),
                    timeout=30.0,
                )
                if notes_store and hasattr(notes_store, 'lineup_data'):
                    qa_runner.player_id_agent.set_lineup_data(notes_store.lineup_data)
                await manager.send(websocket, {
                    "type": "status",
                    "message": f"Match brief ready for {home_team} vs {away_team}.",
                })
            except Exception as exc:
                logger.warning("qa_runner.initialize_session failed: %s", exc)

        asyncio.create_task(_init_session())

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
                    ctx = game_state.to_context_string()
                    seed = f"{ctx}\n{description}" if ctx else description

                    # Call LiveAgent with event type extracted from description for NotesStore lookup
                    # Extract potential event type from description (simple heuristic)
                    event_type = None
                    desc_lower = description.lower()
                    if "goal" in desc_lower or "score" in desc_lower:
                        event_type = "goal"
                    elif "yellow card" in desc_lower or "booking" in desc_lower:
                        event_type = "yellow_card"
                    elif "red card" in desc_lower or "sent off" in desc_lower:
                        event_type = "red_card"
                    elif "sub" in desc_lower or "off for" in desc_lower:
                        event_type = "substitution"
                    elif "foul" in desc_lower:
                        event_type = "foul"
                    elif "corner" in desc_lower:
                        event_type = "corner"
                    elif "offside" in desc_lower:
                        event_type = "offside"

                    await refresh_agent_notes_store(agent, match_session)
                    result = await agent.generate_live_commentary(
                        event_description=seed,
                        vision_tactical_label=event_type,
                        game_state=game_state,
                        settings=manager.get_settings(match_session),
                    )

                    broadcast_msg = {
                        "type": "commentary",
                        "text": result.get("commentary", ""),
                        "source": result.get("source", "event"),
                        "trigger": description,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "gameState": game_state.to_dict(),
                        "resolved_tag": result.get("resolved_tag"),
                    }
                    await manager.broadcast(workflow_id, broadcast_msg)

                    # Broadcast trivia card if high-confidence beat retrieved
                    trivia = result.get("trivia_formatted")
                    if trivia:
                        await manager.broadcast(workflow_id, {
                            "type": "trivia_card",
                            "text": trivia["text"],
                            "source": trivia["source"],
                            "source_urls": trivia.get("source_urls", []),
                            "source_attribution": trivia.get("source_attribution", []),
                            "event_tag": trivia.get("event_tag"),
                            "confidence": trivia["confidence"],
                            "display_duration_ms": trivia["display_duration_ms"],
                            "fade_in_ms": trivia["fade_in_ms"],
                            "fade_out_ms": trivia["fade_out_ms"],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                elif msg_type == "tactical_detection":
                    analysis = data.get("analysis") or {}
                    if not isinstance(analysis, dict):
                        continue

                    game_state.update_from_detection(analysis)
                    note_text = _format_tactical_commentary_note(analysis)
                    timestamp = datetime.now(timezone.utc).isoformat()

                    # Fix: Translate tactical note if language is not English
                    current_language = manager.get_language(match_session)
                    if current_language != "en":
                        note_text = await _translate_commentary(
                            note_text,
                            target_language=current_language,
                            source_language="en"
                        )

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

                    # Broadcast tactical analyst note
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

                    # Generate enhanced commentary with NotesStore lookup
                    tactical_label = analysis.get("tactical_label", "")
                    commentary_seed = (
                        analysis.get("sequence_summary")
                        or analysis.get("actionable_insight")
                        or analysis.get("key_observation")
                        or tactical_label
                    )

                    if commentary_seed:
                        # Build seed with video timestamp prefix
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

                        # Fix #1: Get settings and inject into commentary generation
                        settings = manager.get_settings(match_session)

                        await refresh_agent_notes_store(agent, match_session)
                        # Call LiveAgent with vision label for NotesStore lookup
                        result = await agent.generate_live_commentary(
                            event_description=full_seed,
                            vision_tactical_label=tactical_label,
                            game_state=game_state,
                            settings=settings,  # Inject user settings
                        )

                        # Fix: Translate commentary if language is not English
                        commentary_text = result.get("commentary", "")
                        current_language = manager.get_language(match_session)
                        if current_language != "en":
                            commentary_text = await _translate_commentary(
                                commentary_text,
                                target_language=current_language,
                                source_language="en"
                            )

                        # Broadcast enhanced commentary with beat indices for teleprompter highlighting
                        beat_indices = result.get("beat_indices", [])
                        broadcast_msg = {
                            "type": "commentary",
                            "text": commentary_text,
                            "source": result.get("source", "analysis"),
                            "label": tactical_label,
                            "confidence": analysis.get("confidence"),
                            "videoTimestampMs": timestamp_ms,
                            "videoRangeLabel": (
                                f"{_format_video_timestamp_ms(analysis.get('clip_start_timestamp_ms'))}–{_format_video_timestamp_ms(analysis.get('clip_end_timestamp_ms'))}"
                                if _format_video_timestamp_ms(analysis.get('clip_start_timestamp_ms')) and _format_video_timestamp_ms(analysis.get('clip_end_timestamp_ms'))
                                else None
                            ),
                            "trigger": analysis.get("actionable_insight") or analysis.get("key_observation"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "gameState": game_state.to_dict(),
                            "resolved_tag": result.get("resolved_tag"),
                            "retrieved_beat_count": len(result.get("retrieved_beats", [])),
                            "beat_indices": beat_indices,  # For teleprompter highlighting (Story 3.2)
                        }
                        await manager.broadcast(workflow_id, broadcast_msg)

                        # Story 3.2: Broadcast beat highlight for teleprompter
                        if beat_indices:
                            # Find the best beat (highest confidence) for highlighting
                            retrieved_beats = result.get("retrieved_beats", [])
                            best_beat_idx = beat_indices[0]
                            best_confidence = 0
                            for beat_data in retrieved_beats:
                                if beat_data.get("confidence", 0) > best_confidence:
                                    best_confidence = beat_data["confidence"]
                                    best_beat_idx = beat_data.get("index", beat_indices[0])

                            await manager.broadcast(workflow_id, {
                                "type": "beat_highlight",
                                "beat_index": best_beat_idx,
                                "confidence": best_confidence,
                                "next_indices": beat_indices[:3],  # Next 3 beats for preview
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                        # Broadcast trivia card if high-confidence beat retrieved
                        trivia = result.get("trivia_formatted")
                        if trivia:
                            await manager.broadcast(workflow_id, {
                                "type": "trivia_card",
                                "text": trivia["text"],
                                "source": trivia["source"],
                                "source_urls": trivia.get("source_urls", []),
                                "source_attribution": trivia.get("source_attribution", []),
                                "event_tag": trivia.get("event_tag"),
                                "confidence": trivia["confidence"],
                                "display_duration_ms": trivia["display_duration_ms"],
                                "fade_in_ms": trivia["fade_in_ms"],
                                "fade_out_ms": trivia["fade_out_ms"],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                elif msg_type == "settings_update":
                    # Story 3.3: Commentary Settings — store for next commentary cycle
                    # Fix #14: Validate settings values
                    raw_bias = data.get("bias", 0)
                    raw_excitement = data.get("excitement", 0.5)
                    raw_knowledge = data.get("knowledge_depth", 0.5)

                    # Type coercion and range validation
                    try:
                        bias = float(raw_bias) if isinstance(raw_bias, (int, float)) else 0
                        bias = max(-1.0, min(1.0, bias))  # Clamp to [-1, 1]

                        excitement = float(raw_excitement) if isinstance(raw_excitement, (int, float)) else 0.5
                        excitement = max(0.0, min(1.0, excitement))  # Clamp to [0, 1]

                        knowledge = float(raw_knowledge) if isinstance(raw_knowledge, (int, float)) else 0.5
                        knowledge = max(0.0, min(1.0, knowledge))  # Clamp to [0, 1]
                    except (TypeError, ValueError):
                        # Fallback to defaults on invalid input
                        bias, excitement, knowledge = 0, 0.5, 0.5

                    settings = {
                        "bias": bias,
                        "excitement": excitement,
                        "knowledge_depth": knowledge,
                    }
                    manager.store_settings(match_session, settings)
                    runner = manager.get_qa_runner(match_session)
                    if runner and hasattr(runner, "set_commentary_settings"):
                        runner.set_commentary_settings(
                            bias=settings["bias"],
                            excitement=settings["excitement"],
                            knowledge_depth=settings["knowledge_depth"],
                        )
                    logger.log_event("settings_updated", {
                        "match_session": match_session,
                        "settings": settings,
                    })

                elif msg_type == "language_switch":
                    # Story 3.4: Language Toggle — store language for commentary routing
                    new_language = data.get("language", "en")
                    manager.store_language(match_session, new_language)
                    logger.log_event("language_switched", {
                        "match_session": match_session,
                        "language": new_language,
                    })
                    # Acknowledge to client
                    await manager.send(websocket, {
                        "type": "language_confirmed",
                        "language": new_language,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif msg_type == "query":
                    query_text = data.get("text", "").strip()
                    if not query_text:
                        continue

                    # Story 2.2 + 2.4: Parallel Q&A with Player ID + Live Vision
                    # Get latest vision tactical context from streaming bridge
                    vision_context = manager.get_vision_context(match_session)
                    current_frame_b64 = vision_context.get("current_frame_b64") if vision_context else None

                    result = await _handle_fan_query_parallel(
                        question=query_text,
                        game_state=game_state,
                        match_session=match_session,
                        current_frame_b64=current_frame_b64,
                        vision_context=vision_context,
                    )

                    # Build answer payload with Story 2.2 + 2.4 enhancements
                    answer_payload = {
                        "type": "answer",
                        "text": result.get("text", ""),
                        "gameState": result.get("gameState"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    # Add Story 2.2: Temporal context
                    if result.get("temporal_context"):
                        answer_payload["temporal_context"] = result["temporal_context"]

                    # Add Story 2.2: Timestamp for split-screen navigation
                    if result.get("timestamp_ms"):
                        answer_payload["timestamp_ms"] = result["timestamp_ms"]

                    # Add Story 2.4: Player identification
                    if result.get("player_identification"):
                        player_id = result["player_identification"]
                        answer_payload["player_identification"] = {
                            "player_name": player_id.get("player_name"),
                            "confidence": player_id.get("confidence"),
                            "source": player_id.get("source"),
                            "jersey_number": player_id.get("jersey_number"),
                            "position": player_id.get("position"),
                            "team_side": player_id.get("team_side"),
                            "kit_color": player_id.get("kit_color"),
                            "pitch_zone": player_id.get("pitch_zone"),
                        }

                    # Add Story 2.4: Overlay coordinates for SVG rendering
                    if result.get("overlay_coordinates"):
                        answer_payload["overlay_coordinates"] = result["overlay_coordinates"]

                    # Add backend level for UI debugging / transparency
                    answer_payload["backend_level"] = result.get("backend_level", 4)

                    await manager.send(websocket, answer_payload)

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

                await refresh_agent_notes_store(live_agent, match_session)
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


# ── WebSocket — StreamingVisionBridge (Hackathon Track 3) ────────────────────

class StreamingVideoConfig(BaseModel):
    """Configuration for StreamingVisionBridge video streaming."""
    backend: str = Field(default=STREAMING_BACKEND, pattern="^(auto|vllm|streaming_vlm)$")
    chunk_interval_seconds: int = Field(default=5, ge=1, le=30)
    max_chunk_frames: int = Field(default=24, ge=4, le=48)
    target_fps: float = Field(default=8.0, ge=1.0, le=30.0)
    sport: str = Field(default="football", pattern="^(football|soccer|cricket|basketball)$")
    auto_commentary_enabled: bool = True


@app.websocket("/ws/video/streaming")
async def streaming_video_ws(websocket: WebSocket):
    """
    WebSocket for StreamingVisionBridge-based real-time video commentary.

    This is the primary hackathon endpoint — uses StreamingVLM's
    compact KV-cache algorithm for truly real-time continuous video understanding.

    Client sends:
      -> {"type": "init", "home_team": "...", "away_team": "...",
          "config": {"backend": "vllm", "chunk_interval_seconds": 5, "sport": "football"}}
      -> {"type": "frame", "frame_b64": "...", "timestamp_ms": 12345, "keyframe": true}
      -> {"type": "match_event", "description": "Goal! 34th minute header"}
      -> {"type": "query", "text": "What formation are they playing?"}

    Server broadcasts:
      <- {"type": "commentary", "text": "...", "source": "streaming_vlm",
          "tactical_label": "Counter Attack", "confidence": 0.85, "gameState": {...}}
      <- {"type": "status", "message": "...", "stats": {...}}
    """
    await websocket.accept()
    logger.info("Streaming video session connected")

    match_session: Optional[str] = None
    game_state: Optional[GameState] = None
    live_agent: Optional[LiveAgent] = None
    bridge: Optional[StreamingVisionBridge] = None
    periodic_task: Optional[asyncio.Task] = None
    workflow_id: Optional[str] = None

    try:
        # Wait for init message
        init_msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        init_data = json.loads(init_msg)

        if init_data.get("type") != "init":
            await manager.send(websocket, {"type": "error", "message": "Expected 'init' message first"})
            return

        home_team = init_data.get("home_team", "Home")
        away_team = init_data.get("away_team", "Away")
        sport = init_data.get("sport", "football")
        match_session = init_data.get("match_session", build_match_session_key(home_team, away_team, sport))
        game_state = GameState(home_team=home_team, away_team=away_team)
        live_agent = LiveAgent(sport=sport)

        # Parse streaming config
        config_data = init_data.get("config", {})
        streaming_config = StreamingVideoConfig(**config_data)

        # Initialize StreamingVisionBridge.
        # Explicit backend ("streaming_vlm", "vllm") → no fallback cascade.
        # "auto" → fallback chain (StreamingVLM → vLLM).
        explicit_backend = streaming_config.backend != "auto"
        bridge_config = StreamingBridgeConfig(
            backend=streaming_config.backend,  # "auto" | "vllm" | "streaming_vlm"
            sport=streaming_config.sport,
            target_fps=streaming_config.target_fps,
            chunk_interval_seconds=streaming_config.chunk_interval_seconds,
            max_chunk_frames=streaming_config.max_chunk_frames,
            auto_commentary_enabled=streaming_config.auto_commentary_enabled,
            vllm_base_url=VLLM_BASE_URL,
            vllm_model=VLLM_VISION_MODEL,
            use_fallback_chain=not explicit_backend,  # fallback only for "auto"
        )
        bridge = StreamingVisionBridge(bridge_config)
        if streaming_config.backend in {"streaming_vlm", "auto"}:
            bridge._backend = await get_or_init_streaming_backend(streaming_config.backend)
            bridge._initialized = True
        else:
            await bridge.initialize()

        # Get actual backend level from fallback
        backend_stats = bridge._backend.get_stats() if bridge._backend else {}
        fallback_level = backend_stats.get("fallback_level", "unknown")
        actual_backend = backend_stats.get("backend", streaming_config.backend)

        # Start research workflow
        context = WorkflowContext(
            match_id=match_session,
            home_team=home_team,
            away_team=away_team,
            sport=sport,
            session_id=str(websocket.client),
        )
        workflow_id = await orchestrator.start_workflow(context)
        await manager.connect(workflow_id, websocket)
        asyncio.create_task(asyncio.wait_for(
            live_agent.start_session(home_team, away_team, sport, match_session=match_session),
            timeout=30.0,
        ))

        await manager.send(websocket, {
            "type": "ready",
            "message": f"Streaming vision active (Fallback Level {fallback_level}: {actual_backend}). "
                       f"Chunk interval: {streaming_config.chunk_interval_seconds}s, "
                       f"Target FPS: {streaming_config.target_fps}",
            "match_session": match_session,
            "config": streaming_config.model_dump(),
            "fallback_level": fallback_level,
            "actual_backend": actual_backend,
        })

        # Start periodic stats broadcast
        periodic_task = asyncio.create_task(
            _periodic_streaming_stats(workflow_id, bridge)
        )

        # Frame buffering loop
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=300.0)
            except asyncio.TimeoutError:
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
                    frame_b64 = data.get("frame_b64")
                    if not frame_b64:
                        continue
                    timestamp_ms = data.get("timestamp_ms", 0)
                    keyframe = data.get("keyframe", False)

                    try:
                        frame_bytes = base64.b64decode(frame_b64)
                    except Exception:
                        continue

                    result = await bridge.process_frame(
                        frame_bytes, timestamp_ms, keyframe=keyframe
                    )

                    if result is not None:
                        # Store vision tactical context for Q&A queries
                        from agents.qa_agent import VisionTacticalContext
                        vision_ctx = VisionTacticalContext(
                            tactical_label=result.get("tactical_label", ""),
                            key_observation=result.get("key_observation", ""),
                            actionable_insight=result.get("actionable_insight", ""),
                            confidence=float(result.get("confidence", 0.0)),
                            timestamp_ms=result.get("end_timestamp_ms"),
                        )
                        manager.store_vision_context(match_session, vision_ctx)

                        # Bridge formed a chunk and returned commentary
                        await _broadcast_streaming_result(
                            websocket, workflow_id, result,
                            game_state, live_agent, match_session=match_session,
                        )

                elif msg_type == "chunk":
                    # Client sends a pre-formed chunk
                    frames_b64 = data.get("frames_b64", [])
                    timestamps_ms = data.get("timestamps_ms", [])

                    for idx, fb64 in enumerate(frames_b64):
                        ts = timestamps_ms[idx] if idx < len(timestamps_ms) else 0
                        try:
                            frame_bytes = base64.b64decode(fb64)
                        except Exception:
                            continue
                        result = await bridge.process_frame(frame_bytes, ts)
                        if result is not None:
                            # Store vision tactical context for Q&A queries
                            from agents.qa_agent import VisionTacticalContext
                            vision_ctx = VisionTacticalContext(
                                tactical_label=result.get("tactical_label", ""),
                                key_observation=result.get("key_observation", ""),
                                actionable_insight=result.get("actionable_insight", ""),
                                confidence=float(result.get("confidence", 0.0)),
                                timestamp_ms=result.get("end_timestamp_ms"),
                            )
                            manager.store_vision_context(match_session, vision_ctx)

                            await _broadcast_streaming_result(
                                websocket, workflow_id, result,
                                game_state, live_agent, match_session=match_session,
                            )

                elif msg_type == "match_event":
                    description = data.get("description", "").strip()
                    if not description:
                        continue
                    game_state.update_from_event(description)
                    seed = description
                    ctx = game_state.to_context_string()
                    if ctx:
                        seed = f"{ctx}\n{description}"
                    await refresh_agent_notes_store(live_agent, match_session)
                    text = await live_agent.generate_live_commentary(seed)
                    await manager.broadcast(workflow_id, {
                        "type": "commentary",
                        "text": text,
                        "source": "event",
                        "trigger": description,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "gameState": game_state.to_dict(),
                    })

                elif msg_type == "query":
                    query_text = data.get("text", "").strip()
                    if not query_text:
                        continue
                    result = None
                    backend_source = "system"
                    if bridge:
                        try:
                            result = await asyncio.wait_for(
                                bridge.force_flush(query_hint=query_text),
                                timeout=25.0,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("video_stream_query_timeout", query=query_text[:120])
                        except Exception as exc:
                            logger.warning("video_stream_query_failed", error=str(exc), query=query_text[:120])

                    if result:
                        answer = clean_model_answer(
                            result.get("commentary")
                            or result.get("key_observation")
                            or "I processed the current video context, but no answer text was returned."
                        )
                        backend_source = result.get("backend") or "vllm"
                    elif live_agent:
                        try:
                            answer = await asyncio.wait_for(
                                live_agent.handle_text_query(query_text),
                                timeout=8.0,
                            )
                            backend_source = "live"
                        except asyncio.TimeoutError:
                            answer = (
                                "I am still processing the video frames, but this looks like a close decision "
                                "from the current passage of play. Try asking again on the replay moment for a "
                                "more precise visual explanation."
                            )
                        except Exception as exc:
                            logger.warning("video_stream_live_fallback_failed", error=str(exc), query=query_text[:120])
                            answer = "I could not complete the video answer from the current frames. Try again on the replay moment."
                    else:
                        answer = "I need a few video frames before I can answer from the stream."
                    await manager.send(websocket, {
                        "type": "answer",
                        "text": answer,
                        "source": "video_qa",
                        "backend_source": backend_source,
                        "result": result,
                        "question": query_text,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif msg_type == "stats":
                    stats = bridge.get_stats() if bridge else {}
                    await manager.send(websocket, {
                        "type": "stats",
                        "stats": stats,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            elif msg.get("bytes"):
                # Binary frame — treat as JPEG
                frame_b64 = base64.b64encode(msg["bytes"]).decode("utf-8")
                timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                try:
                    result = await bridge.process_frame(msg["bytes"], timestamp_ms)
                    if result is not None:
                        await _broadcast_streaming_result(
                            websocket, workflow_id, result,
                            game_state, live_agent, match_session=match_session,
                        )
                except Exception as exc:
                    logger.error("binary_frame_error", error=str(exc))

    except WebSocketDisconnect:
        logger.info("Streaming video session disconnected")
    except Exception as exc:
        logger.error("streaming_video_error", error=str(exc), exc_info=True)
        await manager.send(websocket, {"type": "error", "message": str(exc)})
    finally:
        if periodic_task:
            periodic_task.cancel()
        if bridge:
            await bridge.force_flush()
        if workflow_id:
            manager.disconnect(workflow_id, websocket)
            await orchestrator.finalize_workflow(workflow_id)


async def _broadcast_streaming_result(
    websocket: WebSocket,
    workflow_id: str,
    result: Dict[str, Any],
    game_state: Optional[GameState],
    live_agent: Optional[LiveAgent],
    match_session: Optional[str] = None,
):
    """Broadcast streaming commentary result to all session clients."""
    if game_state:
        game_state.update_from_detection({
            "timestamp_ms": result.get("start_timestamp_ms"),
        })

    # Broadcast the raw streaming result
    await manager.broadcast(workflow_id, {
        "type": "commentary",
        "text": result.get("commentary", ""),
        "source": "streaming_vlm",
        "tactical_label": result.get("tactical_label"),
        "confidence": result.get("confidence"),
        "start_timestamp_ms": result.get("start_timestamp_ms"),
        "end_timestamp_ms": result.get("end_timestamp_ms"),
        "latency_ms": result.get("latency_ms"),
        "chunk_index": result.get("chunk_index"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gameState": game_state.to_dict() if game_state else None,
    })


async def _periodic_streaming_stats(workflow_id: str, bridge: StreamingVisionBridge):
    """Periodically broadcast streaming performance stats."""
    while True:
        try:
            await asyncio.sleep(15)
            stats = bridge.get_stats()
            if stats:
                await manager.broadcast(workflow_id, {
                    "type": "stats_update",
                    "stats": stats,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except asyncio.CancelledError:
            break
        except Exception:
            pass


# ── Commentary Notes Endpoint ──────────────────────────────────────────────────

@app.post("/api/v1/commentary/prepare-notes", dependencies=[Depends(rate_limit_check)])
async def prepare_commentary_notes(req: CommentaryNotesRequest, request: Request) -> JSONResponse:
    """
    Prepare professional Peter Drury-style commentary notes.
    Enqueues a durable background job and returns job metadata.
    """
    from jobs.notes_tasks import enqueue_commentary_notes_job
    from models.notes_jobs import NotesJobRepository, job_to_dict

    canonical_match_session_key = build_match_session_key(req.home_team, req.away_team, req.sport)
    job_id = str(uuid.uuid4())
    repo = NotesJobRepository()
    job, created = await repo.create_or_get_active_job(
        job_id=job_id,
        match_session=canonical_match_session_key,
        home_team=req.home_team,
        away_team=req.away_team,
        sport=req.sport,
    )

    if created:
        enqueue_commentary_notes_job(job.job_id)

    logger.log_event("commentary_notes_requested", {
        "home_team": req.home_team,
        "away_team": req.away_team,
        "sport": req.sport,
        "venue": req.venue,
        "job_id": job.job_id,
        "created": created,
    })

    payload = job_to_dict(job)
    payload.update({
        "status_url": f"/api/v1/commentary/notes-jobs/{job.job_id}",
        "events_url": f"/api/v1/commentary/notes-jobs/{job.job_id}/events",
        "created": created,
    })
    return JSONResponse(payload, status_code=202)


@app.get("/api/v1/commentary/notes-jobs/{job_id}")
async def get_commentary_notes_job(job_id: str):
    """Return durable commentary-notes job state and result when complete."""
    from models.notes_jobs import NotesJobRepository, job_to_dict, notes_store_from_result, result_to_response

    repo = NotesJobRepository()
    job = await repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Notes job not found")

    payload = job_to_dict(job)
    result = await repo.get_result(job_id)
    if result is not None:
        notes_store = notes_store_from_result(result)
        manager.store_notes(result.match_session, notes_store)
        result_payload = result_to_response(result)
        result_payload.update({
            "match": f"{job.home_team} vs {job.away_team}",
            "sport": job.sport,
        })
        payload["result"] = result_payload
    return payload


@app.get("/api/v1/commentary/notes-jobs/{job_id}/events")
async def stream_commentary_notes_job_events(job_id: str, request: Request):
    """Stream commentary-notes job progress from Redis, with DB polling fallback."""
    import json as _json
    import redis.asyncio as redis
    from config import REDIS_URL
    from jobs.notes_events import notes_job_channel
    from models.notes_jobs import NotesJobRepository, job_to_dict, result_to_response

    async def generate():
        repo = NotesJobRepository()
        job = await repo.get_job(job_id)
        if job is None:
            yield f"data: {_json.dumps({'phase': 'error', 'message': 'Notes job not found', 'done': True})}\n\n"
            return

        yield f"data: {_json.dumps({'phase': job.phase, 'message': job.status, 'progress': job.progress, 'done': job.status in ('succeeded', 'failed', 'cancelled')})}\n\n"
        if job.status == "succeeded":
            result = await repo.get_result(job_id)
            if result:
                result_payload = result_to_response(result)
                result_payload.update({"match": f"{job.home_team} vs {job.away_team}", "sport": job.sport})
                yield f"data: {_json.dumps({'phase': 'complete', 'message': 'Done', 'progress': 1.0, 'done': True, 'result': result_payload})}\n\n"
            return
        if job.status in ("failed", "cancelled"):
            yield f"data: {_json.dumps({'phase': 'error', 'message': job.error or job.status, 'done': True})}\n\n"
            return

        client = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(notes_job_channel(job_id))
            while True:
                if await request.is_disconnected():
                    return
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    yield f"data: {message['data']}\n\n"
                    try:
                        event = _json.loads(message["data"])
                    except Exception:
                        event = {}
                    if event.get("done"):
                        return
                else:
                    job = await repo.get_job(job_id)
                    if job is None:
                        return
                    if job.status == "succeeded":
                        result = await repo.get_result(job_id)
                        if result:
                            result_payload = result_to_response(result)
                            result_payload.update({"match": f"{job.home_team} vs {job.away_team}", "sport": job.sport})
                            yield f"data: {_json.dumps({'phase': 'complete', 'message': 'Done', 'progress': 1.0, 'done': True, 'result': result_payload})}\n\n"
                        return
                    if job.status in ("failed", "cancelled"):
                        yield f"data: {_json.dumps({'phase': 'error', 'message': job.error or job.status, 'done': True})}\n\n"
                        return
                    yield f"data: {_json.dumps({'phase': job.phase, 'message': job.status, 'progress': job.progress, 'done': False})}\n\n"
        finally:
            await pubsub.unsubscribe(notes_job_channel(job_id))
            await pubsub.aclose()
            await client.aclose()

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/notes/{match_session}")
async def get_commentary_notes(match_session: str):
    """
    Poll endpoint for NotesGenerationHub to check if commentary notes are ready.
    Returns notes status and data if available.
    """
    notes_store = await load_notes_store_for_session(match_session)

    if notes_store is None:
        # Notes not generated yet
        raise HTTPException(status_code=404, detail="Notes not ready")

    # Convert NotesStore to dict for frontend
    notes_data = {
        "status": "ready",
        "markdown_notes": getattr(notes_store, "raw_markdown", "") or "",
        "notes": {
            "beats": [
                {
                    "text": beat.text,
                    "event_tags": beat.event_tags,
                    "players": beat.players,
                    "section": beat.section,
                    "source": beat.source,
                    "source_urls": beat.source_urls,
                    "source_attribution": beat.source_attribution,
                    "confidence": beat.confidence,
                }
                for beat in notes_store.beats
            ] if notes_store.beats else [],
            "lookup": dict(notes_store.lookup) if notes_store.lookup else {},
        },
        "beat_count": len(notes_store.beats) if notes_store.beats else 0,
    }

    return notes_data


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
