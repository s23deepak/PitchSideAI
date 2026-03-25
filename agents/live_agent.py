"""
Live Agent — Amazon Nova 2 Sonic (Real-time Speech Translation via Bedrock)
Handles bidirectional audio streaming between the fan's browser and Nova 2 Sonic.
"""
import json
import logging
import boto3

from config import AWS_REGION, LIVE_AUDIO_MODEL
from agents.research_agent import ResearchAgent
from tools.dynamodb_tool import write_event, get_recent_events

logger = logging.getLogger(__name__)

# Bedrock runtime client
_bedrock = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)

SYSTEM_PROMPT = "You are PitchSide AI, an expert sports analyst assistant powered by Amazon Nova 2 Sonic."

class LiveAgent:
    """
    Wraps Amazon Nova 2 Sonic via Bedrock ConverseStream for real-time interaction.
    """

    def __init__(self, match_context: str = ""):
        self.research = ResearchAgent()
        self.match_context = match_context
        self.model_id = LIVE_AUDIO_MODEL

    async def start_session(self, home_team: str, away_team: str, sport: str = "soccer"):
        """Pre-loads the match context via Nova 2 Pro."""
        brief = await self.research.build_match_brief(home_team, away_team, sport)
        self.match_context = brief
        return True

    async def stream_audio(self, audio_bytes: bytes, websocket) -> None:
        """
        Sends fan audio to Nova 2 Sonic and streams the response back.
        Since Bedrock Nova Sonic true bidirectional live streaming SDK implementation 
        could be complex via standard REST, this simulates the stream/relay logic for the UI.
        """
        # In a real implementation for Nova Sonic speech-to-speech, 
        # we would continuously pipe chunks to ConverseStream API.
        # For scaffolding purposes, we simulate the text response relay.
        
        logger.info(f"[LiveAgent: Nova Sonic] Received audio chunk ({len(audio_bytes)} bytes)")
        
        # Simulated response pipeline due to lack of local AWS audio context
        text_response = "Nova 2 Sonic audio processing active."
        await write_event("fan_qa", text_response)
        
        # Normally would stream audio response back to browser
        # await websocket.send_bytes(audio_response_bytes)

    async def handle_text_query(self, query: str) -> str:
        """
        Handles a text Q&A query using Nova 2 Pro.
        """
        recent_events = await get_recent_events(5)
        events_text = "\n".join([e.get("description", "") for e in recent_events])

        context = f"Recent events: {events_text}\n\nFan question: {query}"
        answer = await self.research.answer_live_query(context)
        
        await write_event("fan_qa", f"Q: {query} | A: {answer}")
        return answer
