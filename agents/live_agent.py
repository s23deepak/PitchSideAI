"""
Live Agent — Amazon Nova Sonic
Real-time Q&A and live query handling during matches.
Supports dynamic sport types with contextual responses.

Enhanced with NotesStore integration for O(1) retrieval of pre-computed
commentary beats triggered by vision detections.
"""
import json
from typing import List, Optional, Any, Dict

from agents.base import LiveAgent as BaseLiveAgent
from agents.research_agent import ResearchAgent
from rag import RetrievedDocument
from tools.dynamodb_tool import write_event, get_recent_events
from models.notes_store import NotesStore, TagResolver


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
        self.notes_store: Optional[NotesStore] = None
        self.tag_resolver = TagResolver()

    async def execute(self, query: str) -> str:
        """Alias for handle_text_query for orchestration compatibility."""
        return await self.handle_text_query(query)

    async def start_session(
        self,
        home_team: str,
        away_team: str,
        sport: Optional[str] = None,
        match_session: Optional[str] = None,
        notes_store: Optional[NotesStore] = None,
    ) -> str:
        """
        Initialize live session with pre-match research.

        Args:
            home_team: Home team name
            away_team: Away team name
            sport: Optional - override sport type
            match_session: Optional - match session key
            notes_store: Optional - pre-computed NotesStore from 7-agent pipeline

        Returns:
            Match brief text
        """
        if sport:
            self.sport = sport

        self.home_team = home_team
        self.away_team = away_team
        if match_session:
            self.match_session = match_session
        if notes_store:
            self.notes_store = notes_store

        self.log_event("session_started", {
            "home_team": home_team,
            "away_team": away_team,
            "has_notes_store": notes_store is not None
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

    async def handle_voice_query(self, audio_bytes: bytes) -> str:
        """
        Process voice query: speech-to-text → answer → text response.

        Args:
            audio_bytes: Audio bytes containing the user's question

        Returns:
            Text answer (no TTS - text only for lower latency)
        """
        self.log_event("voice_query_received", {
            "audio_size": len(audio_bytes)
        })

        try:
            # Transcribe audio to text using Bedrock
            transcribed_text = await self._transcribe_audio(audio_bytes)

            if not transcribed_text or not transcribed_text.strip():
                return "I couldn't hear your question clearly. Could you please try again?"

            # Process as text query
            answer = await self.handle_text_query(transcribed_text.strip())

            # Log voice Q&A
            await write_event(
                "fan_qa_voice",
                f"Voice Q: {transcribed_text}",
                {
                    "question": transcribed_text,
                    "answer": answer,
                    "sport": self.sport,
                    "home_team": self.home_team,
                    "away_team": self.away_team
                },
                match_session=self.match_session,
            )

            return answer

        except Exception as exc:
            self.logger.error("voice_query_failed", error=str(exc), exc_info=True)
            return "I'm having trouble processing your voice question. Please try again or type your question."

    async def _transcribe_audio(self, audio_bytes: bytes) -> str:
        """
        Transcribe audio to text using Amazon Bedrock.

        Args:
            audio_bytes: Raw audio bytes (WAV/PCM format expected)

        Returns:
            Transcribed text
        """
        import base64

        try:
            # Use Bedrock's InvokeModel with a speech-to-text capable model
            # For now, use a simple approach with Bedrock Runtime
            from config import AWS_REGION
            import boto3

            bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            # Use Nova Sonic or another STT-capable model
            # Note: This is a simplified implementation
            # In production, you'd use the actual Bedrock STT API
            prompt = "Transcribe the following audio. Return ONLY the transcribed text, nothing else:"

            response = bedrock_runtime.invoke_model(
                modelId="amazon.nova-sonic-v1:0",  # Or appropriate STT model
                body=json.dumps({
                    "prompt": prompt,
                    "audio_data": audio_b64,
                    "max_tokens": 256,
                })
            )

            result = json.loads(response["body"].read())
            transcribed = result.get("transcription", "").strip()

            self.log_event("audio_transcribed", {
                "transcription_length": len(transcribed)
            })

            return transcribed

        except ImportError:
            self.logger.warning("boto3_not_available_for_stt")
            return ""
        except Exception as exc:
            self.logger.error("stt_transcription_failed", error=str(exc))
            # Fallback: return empty string (caller will handle)
            return ""

    async def generate_live_commentary(
        self,
        event_description: str,
        vision_tactical_label: Optional[str] = None,
        game_state: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generate live commentary for a match event with NotesStore lookup.

        Uses O(1) deterministic retrieval from pre-computed beats when vision
        detects an event, falling back to full markdown context if no match.

        Args:
            event_description: Description of what happened
            vision_tactical_label: Optional vision detection label for tag resolution
            game_state: Optional GameState object for active player filter

        Returns:
            Dict with commentary text, source ("notes_lookup" or "raw_markdown"),
            retrieved_beats (list of NarrativeBeat dicts), and trivia_formatted
        """
        self.log_event("commentary_generation_requested", {
            "event": event_description[:100],
            "vision_label": vision_tactical_label,
            "has_notes_store": self.notes_store is not None
        })

        # Retrieve relevant beats via NotesStore lookup chain
        retrieved_beats = []
        source = "raw_markdown"
        resolved_tag = None

        if self.notes_store and vision_tactical_label:
            # Resolve vision label to canonical tag
            resolved_tag = self.tag_resolver.resolve(vision_tactical_label)

            if resolved_tag:
                # O(1) lookup
                beats = self.notes_store.get_beats_for_tag(resolved_tag)

                # Apply game_state active-player filter if available
                if game_state and hasattr(game_state, 'active_players'):
                    active_players = getattr(game_state, 'active_players', set())
                    if active_players:
                        beats = [
                            b for b in beats
                            if not b.players or any(p in active_players for p in b.players)
                        ]

                if beats:
                    retrieved_beats = beats
                    source = "notes_lookup"

        # Build prompt with retrieved beats
        beat_context = ""
        if retrieved_beats:
            beat_lines = []
            for beat in retrieved_beats[:5]:  # Limit to 5 most relevant beats
                beat_lines.append(f"- {beat.text} (source: {beat.source})")
            beat_context = "\n".join(beat_lines)

        prompt = f"""You are a professional {self.sport} commentator providing real-time match analysis in the style of Peter Drury — poetic, insightful, and emotionally resonant.

MATCH: {self.home_team} vs {self.away_team}

EVENT: {event_description}
"""

        if beat_context:
            prompt += f"""
RELEVANT CONTEXT (from pre-computed notes):
{beat_context}
"""

        prompt += f"""
Generate 2-3 sentences of engaging live commentary that:
1. Explains what just happened with vivid imagery
2. Weaves in the relevant context naturally (if provided above)
3. Provides tactical insight or emotional resonance
4. Forecasts next likely play

Keep energy high and authentic to {self.sport} commentary style.
Use metaphors and narrative flair characteristic of Peter Drury.

Commentary:"""

        commentary = await self.call_bedrock(prompt, temperature=0.7, max_tokens=250)

        # Format trivia card (2-line fact for Fan Lens)
        trivia_formatted = self._format_trivia_card(
            commentary, retrieved_beats, resolved_tag
        )

        result = {
            "commentary": commentary,
            "source": source,
            "retrieved_beats": [
                {
                    "text": b.text,
                    "event_tags": b.event_tags,
                    "players": b.players,
                    "source": b.source,
                    "confidence": b.confidence,
                }
                for b in retrieved_beats
            ],
            "trivia_formatted": trivia_formatted,
            "resolved_tag": resolved_tag,
        }

        await write_event(
            "live_commentary",
            event_description,
            {
                "commentary": commentary,
                "sport": self.sport,
                "source": source,
                "resolved_tag": resolved_tag,
            },
            match_session=self.match_session,
        )

        return result

    def _format_trivia_card(
        self,
        commentary: str,
        retrieved_beats: List[Any],
        resolved_tag: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Format a 2-line trivia card from commentary for Fan Lens display.

        Args:
            commentary: Full commentary text
            retrieved_beats: List of NarrativeBeat objects used in generation
            resolved_tag: Canonical event tag that triggered this commentary

        Returns:
            Trivia card dict with text, source attribution, and display metadata,
            or None if no high-confidence beats were retrieved.
        """
        if not retrieved_beats:
            return None

        # Find highest confidence beat for trivia
        best_beat = max(retrieved_beats, key=lambda b: b.confidence, default=None)

        if not best_beat or best_beat.confidence < 0.6:
            return None

        # Extract 2-line fact from beat text
        fact_text = best_beat.text
        # Truncate to ~150 chars for card display
        if len(fact_text) > 150:
            fact_text = fact_text[:147] + "..."

        # Determine fade-in/out timing based on confidence
        confidence = best_beat.confidence
        if confidence >= 0.8:
            display_duration_ms = 5000
            fade_in_ms = 400
            fade_out_ms = 400
        elif confidence >= 0.6:
            display_duration_ms = 3000
            fade_in_ms = 300
            fade_out_ms = 300
        else:
            return None  # Too low confidence to surface

        return {
            "text": fact_text,
            "source": best_beat.source,
            "event_tag": resolved_tag,
            "confidence": confidence,
            "display_duration_ms": display_duration_ms,
            "fade_in_ms": fade_in_ms,
            "fade_out_ms": fade_out_ms,
        }

    def get_session_info(self) -> dict:
        """Get current session information."""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "sport": self.sport,
            "has_context": bool(self.match_context),
            "context_length": len(self.match_context)
        }

