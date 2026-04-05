"""
Live Agent — Amazon Nova Sonic
Real-time Q&A and live query handling during matches.
Supports dynamic sport types with contextual responses.
"""
from typing import List, Optional

from agents.base import LiveAgent as BaseLiveAgent
from agents.research_agent import ResearchAgent
from rag import RetrievedDocument
from tools.dynamodb_tool import write_event, get_recent_events


class LiveAgent(BaseLiveAgent):
    """
    Handles real-time fan questions and commentary during live matches.
    Integrates with ResearchAgent for context-aware responses.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import LIVE_AUDIO_MODEL
        super().__init__(model_id or LIVE_AUDIO_MODEL, sport)
        self.research_agent = ResearchAgent(sport=sport)
        self.match_context = ""
        self.home_team = ""
        self.away_team = ""
        self.match_session = "active_match"

    async def execute(self, query: str) -> str:
        """Alias for handle_text_query for orchestration compatibility."""
        return await self.handle_text_query(query)

    async def start_session(
        self,
        home_team: str,
        away_team: str,
        sport: Optional[str] = None,
        match_session: Optional[str] = None,
    ) -> str:
        """
        Initialize live session with pre-match research.

        Args:
            home_team: Home team name
            away_team: Away team name
            sport: Optional - override sport type

        Returns:
            Match brief text
        """
        if sport:
            self.sport = sport

        self.home_team = home_team
        self.away_team = away_team
        if match_session:
            self.match_session = match_session

        self.log_event("session_started", {
            "home_team": home_team,
            "away_team": away_team
        })

        # Pre-load match context via research agent
        brief = await self.research_agent.build_match_brief(home_team, away_team)
        self.match_context = brief

        return brief

    async def handle_text_query(
        self,
        query: str,
        context: Optional[List[RetrievedDocument]] = None
    ) -> str:
        """
        Answer live fan question using RAG context and dynamic prompts.

        Args:
            query: Fan question
            context: Optional pre-fetched RAG documents from the API layer

        Returns:
            Answer text
        """
        self.log_event("query_received", {
            "query": query[:100],
            "has_context": bool(self.match_context),
            "has_rag_context": bool(context)
        })

        try:
            # Get recent match events for real-time context
            recent_events = await get_recent_events(5, match_session=self.match_session)
            events_text = "\n".join([
                e.get("description", "") for e in recent_events if e.get("description")
            ])

            context_sections = []
            if self.match_context:
                context_sections.append(
                    f"MATCH CONTEXT:\n{self.match_context[:1000]}"
                )
            if events_text:
                context_sections.append(f"RECENT EVENTS:\n{events_text}")

            full_context = "\n\n".join(context_sections)

            # Get answer from research agent (uses dynamic prompts)
            answer = await self.research_agent.answer_live_query(
                query,
                self.home_team,
                self.away_team,
                retrieved_docs=context,
                supplemental_context=full_context
            )

            # Log Q&A to DynamoDB
            await write_event(
                "fan_qa",
                f"Q: {query}",
                {
                    "question": query,
                    "answer": answer,
                    "sport": self.sport,
                    "home_team": self.home_team,
                    "away_team": self.away_team
                },
                match_session=self.match_session,
            )

            return answer

        except Exception as exc:
            self.logger.error("query_handling_failed", error=str(exc), exc_info=True)
            # Graceful fallback
            return "I'm having trouble answering that right now. Please try again."

    async def stream_audio(self, audio_bytes: bytes) -> str:
        """
        Handle audio chunk (simulated for now).
        In production, this would stream to Nova Sonic's speech-to-speech API.

        Args:
            audio_bytes: Audio frame bytes

        Returns:
            Text or audio response
        """
        self.log_event("audio_chunk_received", {
            "audio_size": len(audio_bytes)
        })

        try:
            # TODO: Implement actual speech-to-text via Bedrock
            # For now, return placeholder
            response = "Audio processing active. Please speak your question."

            await write_event(
                "audio_interaction",
                response,
                {
                    "audio_size": len(audio_bytes),
                    "sport": self.sport
                },
                match_session=self.match_session,
            )

            return response

        except Exception as exc:
            self.logger.error("audio_processing_failed", error=str(exc))
            raise

    async def generate_live_commentary(self, event_description: str) -> str:
        """
        Generate live commentary for a match event.

        Args:
            event_description: Description of what happened

        Returns:
            Commentary text
        """
        self.log_event("commentary_generation_requested", {
            "event": event_description[:100]
        })

        prompt = f"""
You are a professional {self.sport} commentator providing real-time match analysis.

MATCH: {self.home_team} vs {self.away_team}

EVENT: {event_description}

Generate 2-3 sentences of engaging live commentary that:
1. Explains what just happened
2. Provides tactical insight
3. Forecasts next likely play

Keep energy high and authentic to {self.sport} commentary style.

Commentary:
"""

        commentary = await self.call_bedrock(prompt, temperature=0.6, max_tokens=200)

        await write_event(
            "live_commentary",
            event_description,
            {
                "commentary": commentary,
                "sport": self.sport
            },
            match_session=self.match_session,
        )

        return commentary

    def get_session_info(self) -> dict:
        """Get current session information."""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "sport": self.sport,
            "has_context": bool(self.match_context),
            "context_length": len(self.match_context)
        }

