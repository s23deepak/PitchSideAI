"""
FastAPI Server — PitchSide AI Backend
Exposes WebSocket for live audio and REST endpoints for frame analysis and research.
"""
import base64
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.live_agent import LiveAgent
from agents.vision_agent import VisionAgent
from agents.research_agent import ResearchAgent
from tools.dynamodb_tool import get_recent_events

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

# Shared agent instances (one per sport; Live sessions are per-connection)
vision_soccer = VisionAgent(sport="soccer")
vision_cricket = VisionAgent(sport="cricket")
research_agent = ResearchAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏟️  PitchSide AI backend starting...")
    yield
    logger.info("PitchSide AI backend shutting down.")


app = FastAPI(title="PitchSide AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Endpoints ─────────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    home_team: str
    away_team: str
    sport: str = "soccer"


class FrameRequest(BaseModel):
    frame_b64: str           # Base64-encoded JPEG
    sport: str = "soccer"


class TextQueryRequest(BaseModel):
    query: str
    home_team: str = "Team A"
    away_team: str = "Team B"


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PitchSide AI"}


@app.post("/api/research")
async def build_research(req: ResearchRequest):
    """Trigger pre-match research. Returns the Commentator's Brief."""
    try:
        brief = await research_agent.build_match_brief(req.home_team, req.away_team, req.sport)
        return {"brief": brief, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/frame")
async def analyze_frame(req: FrameRequest):
    """Submit a video frame for tactical analysis."""
    try:
        agent = vision_soccer if req.sport == "soccer" else vision_cricket
        result = await agent.analyze_frame_b64(req.frame_b64)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query")
async def text_query(req: TextQueryRequest):
    """Text-based Q&A fallback (for browsers without mic)."""
    agent = LiveAgent()
    answer = await agent.handle_text_query(req.query)
    return {"answer": answer}


@app.get("/api/events")
async def get_events(n: int = 20):
    """Get the most recent N match events from DynamoDB."""
    events = await get_recent_events(n)
    return {"events": events}


# ── WebSocket — Live Audio Streaming ──────────────────────────────────────────

@app.websocket("/ws/live")
async def live_audio_ws(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional Gemini Live API audio streaming.
    
    Protocol:
    1. Client sends JSON: {"type": "init", "home_team": "...", "away_team": "...", "sport": "..."}
    2. Client then streams raw PCM audio bytes.
    3. Server streams back raw PCM audio bytes (agent's spoken response).
    """
    await websocket.accept()
    logger.info("🎙️  New live audio session connected.")
    agent = LiveAgent()

    try:
        # Step 1: Receive session init
        init_data = await websocket.receive_text()
        init = json.loads(init_data)
        home_team = init.get("home_team", "Home Team")
        away_team = init.get("away_team", "Away Team")
        sport = init.get("sport", "soccer")

        await websocket.send_text(json.dumps({
            "type": "status",
            "message": f"🔬 Researching {home_team} vs {away_team}... Stand by."
        }))

        # Pre-load the match brief
        config = await agent.start_session(home_team, away_team, sport)

        await websocket.send_text(json.dumps({
            "type": "ready",
            "message": "✅ Research complete! Push to talk and ask me anything."
        }))

        # Step 2: Stream audio chunks
        while True:
            audio_chunk = await websocket.receive_bytes()
            await agent.stream_audio(audio_chunk, websocket)

    except WebSocketDisconnect:
        logger.info("Fan session disconnected.")
    except Exception as e:
        logger.error(f"Live session error: {e}")
        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))


if __name__ == "__main__":
    import uvicorn
    from config import PORT, LOG_LEVEL
    uvicorn.run("api.server:app", host="0.0.0.0", port=PORT, log_level=LOG_LEVEL, reload=True)
