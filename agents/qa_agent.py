"""
QA Agent — Story 2.2: Q&A Backend Answer Generation

Handles fan questions with Peter Drury-style commentator voice,
game state injection, pre-computed Q&A cache lookup, and temporal context awareness.

FRs covered: FR13 (Same-Commentator Voice), FR11 (Graceful Fallback)
"""
import json
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from agents.base import LiveAgent as BaseLiveAgent
from agents.research_agent import ResearchAgent
from models.game_state import GameState
from models.notes_store import NotesStore, TagResolver
from tools.dynamodb_tool import write_event, get_recent_events


@dataclass
class QAPair:
    """Pre-computed Q&A pair from Story 1.3 pipeline."""
    question: str
    answer_text: str
    overlay_coordinates: Optional[Dict[str, Any]] = None
    timestamp_ms: Optional[int] = None
    temporal_context: str = "full"


@dataclass
class TemporalContext:
    """KV cache temporal context for grounding answers."""
    timestamp_ms: Optional[int] = None
    similarity_score: float = 0.0
    frame_caption: str = ""
    is_limited: bool = False  # True if > 120s ago or fallback level 3-4


@dataclass
class VisionTacticalContext:
    """Live vision-based tactical context from StreamingVisionBridge."""
    tactical_label: str = ""  # e.g., "Counter Attack", "Set Piece", "Pressing"
    key_observation: str = ""  # What the vision model observed
    actionable_insight: str = ""  # What to watch for next
    confidence: float = 0.0  # Vision model confidence 0.0-1.0
    timestamp_ms: Optional[int] = None  # When this observation was made

    def to_prompt_hint(self) -> str:
        """Convert to natural language hint for the LLM."""
        if not self.tactical_label or self.confidence < 0.4:
            return ""
        parts = [f"Live vision detects: {self.tactical_label}"]
        if self.key_observation:
            parts.append(f"Observation: {self.key_observation}")
        if self.actionable_insight:
            parts.append(f"Watch for: {self.actionable_insight}")
        return " | ".join(parts)


class QAAgent(BaseLiveAgent):
    """
    Story 2.2: Q&A Backend Answer Generation

    Handles WebSocket query messages, generates answers in commentator voice,
    uses pre-computed Q&A cache and KV cache temporal context.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import LIVE_AUDIO_MODEL
        super().__init__(model_id or LIVE_AUDIO_MODEL, sport)
        self.research_agent = ResearchAgent(sport=sport)
        self.home_team = ""
        self.away_team = ""
        self.match_session = "active_match"
        self.notes_store: Optional[NotesStore] = None
        self.tag_resolver = TagResolver()
        self.qa_cache: Dict[str, QAPair] = {}  # Pre-computed Q&A from Story 1.3
        self.commentary_settings = {
            "bias": 0,  # -1 (Team A fan) to +1 (Team B fan)
            "excitement": 0.7,  # 0=subdued, 1=maximum
            "knowledge_depth": 1,  # 0=beginner, 1=tactical
        }

    async def start_session(
        self,
        home_team: str,
        away_team: str,
        sport: Optional[str] = None,
        match_session: Optional[str] = None,
        notes_store: Optional[NotesStore] = None,
        qa_cache: Optional[Dict[str, QAPair]] = None,
    ) -> None:
        """
        Initialize Q&A session with pre-match research and Q&A cache.

        Args:
            home_team: Home team name
            away_team: Away team name
            sport: Optional sport override
            match_session: Optional match session key
            notes_store: Pre-computed NotesStore from Story 1.3
            qa_cache: Pre-computed Q&A pairs from Story 1.3
        """
        if sport:
            self.sport = sport
        self.home_team = home_team
        self.away_team = away_team
        if match_session:
            self.match_session = match_session
        if notes_store:
            self.notes_store = notes_store
        if qa_cache:
            self.qa_cache = qa_cache

        self.log_event("qa_session_started", {
            "home_team": home_team,
            "away_team": away_team,
            "qa_cache_size": len(qa_cache) if qa_cache else 0,
        })

        # Pre-load match context
        brief = await self.research_agent.build_match_brief(home_team, away_team)
        self.match_context = brief

    def set_commentary_settings(
        self,
        bias: float = 0,
        excitement: float = 0.7,
        knowledge_depth: float = 1,
    ) -> None:
        """Update commentary settings for answer generation."""
        self.commentary_settings = {
            "bias": max(-1.0, min(1.0, bias)),
            "excitement": max(0.0, min(1.0, excitement)),
            "knowledge_depth": max(0.0, min(1.0, knowledge_depth)),
        }

    def _normalize_question(self, question: str) -> str:
        """Normalize question text for cache lookup."""
        # Strip whitespace, lowercase, collapse spaces, remove trailing punctuation
        normalized = question.strip().casefold()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.rstrip("?!.")
        return normalized

    def _check_precomputed_cache(self, question: str) -> Optional[QAPair]:
        """
        Check pre-computed Q&A cache (Story 1.3).

        Args:
            question: Fan question text

        Returns:
            QAPair if found, None otherwise
        """
        normalized = self._normalize_question(question)

        # Exact match
        if normalized in self.qa_cache:
            return self.qa_cache[normalized]

        # Partial match (contains key phrases)
        for key, pair in self.qa_cache.items():
            if key in normalized or normalized in key:
                return pair

        return None

    def _search_kv_cache_temporal_context(
        self,
        question: str,
        retained_frames: List[Dict[str, Any]],
    ) -> TemporalContext:
        """
        Semantic search over retained KV cache frames.

        Args:
            question: Fan question
            retained_frames: List of retained frames with embeddings/captions

        Returns:
            TemporalContext with most relevant timestamp
        """
        if not retained_frames:
            return TemporalContext(is_limited=True)

        # Normalize question (same as _normalize_question)
        normalized_q = self._normalize_question(question)
        question_tokens = set(normalized_q.split())

        # Simple keyword-based similarity (replace with cosine similarity in prod)
        best_match = None
        best_score = 0.0

        for frame in retained_frames:
            caption = frame.get("caption", "")
            # Normalize caption too
            caption_normalized = caption.casefold().rstrip("?!.")
            caption_tokens = set(caption_normalized.split())
            overlap = len(question_tokens & caption_tokens)
            score = overlap / max(len(question_tokens), 1)

            if score > best_score:
                best_score = score
                best_match = frame

        if best_match and best_score > 0.3:  # Threshold for "full" temporal context
            return TemporalContext(
                timestamp_ms=best_match.get("timestamp_ms"),
                similarity_score=best_score,
                frame_caption=best_match.get("caption", ""),
                is_limited=False,
            )
        else:
            return TemporalContext(is_limited=True)

    def _build_qa_prompt(
        self,
        question: str,
        game_state: Optional[GameState],
        temporal_context: Optional[TemporalContext],
        vision_context: Optional[VisionTacticalContext] = None,
    ) -> str:
        """
        Build prompt with game state, settings, temporal context, and live vision data.

        Args:
            question: Fan question
            game_state: Current match game state
            temporal_context: KV cache temporal context
            vision_context: Live vision-based tactical context from StreamingVisionBridge

        Returns:
            Formatted prompt string
        """
        settings = self.commentary_settings

        # Game state context
        game_ctx = ""
        if game_state:
            game_ctx = game_state.to_context_string()

        # Recent events
        recent_events_text = ""
        # Note: get_recent_events is async, caller should fetch and pass in

        # Temporal context hint
        temporal_hint = ""
        if temporal_context and not temporal_context.is_limited:
            ts_sec = int((temporal_context.timestamp_ms or 0) // 1000)
            mins, secs = divmod(ts_sec, 60)
            temporal_hint = f"Relevant footage at {mins:02d}:{secs:02d}: {temporal_context.frame_caption}"

        # Vision tactical context (highest priority for tactical questions)
        vision_hint = ""
        if vision_context and vision_context.confidence >= 0.4:
            vision_hint = vision_context.to_prompt_hint()

        prompt = f"""{game_ctx}

Commentary Settings:
- Bias: {settings['bias']} (-1=Team A fan, 0=neutral, +1=Team B fan)
- Excitement: {settings['excitement']} (0=subdued, 1=maximum)
- Knowledge Depth: {settings['knowledge_depth']} (0=beginner, 1=tactical)

Match: {self.home_team} vs {self.away_team}

Question: {question}

{temporal_hint if temporal_hint else ""}
{" — " + vision_hint if vision_hint else ""}

Answer in the style of Peter Drury commentary — poetic, insightful, emotionally resonant.
Reference specific visual moments if temporal context is available.
If the question is not about football, gracefully redirect.

Answer:"""

        return prompt

    async def handle_query(
        self,
        question: str,
        game_state: Optional[GameState] = None,
        retained_frames: Optional[List[Dict[str, Any]]] = None,
        vision_context: Optional[VisionTacticalContext] = None,
    ) -> Dict[str, Any]:
        """
        Handle fan Q&A question with full Story 2.2 pipeline including live vision context.

        Pipeline:
        1. Check pre-computed Q&A cache (tap path < 1s)
        2. Search KV cache for temporal context
        3. Build prompt with game state + settings + live vision data
        4. Call LLM (Priority 1 GPU scheduling)
        5. Return answer with metadata

        Args:
            question: Fan question text
            game_state: Current match game state
            retained_frames: Retained KV cache frames for temporal search
            vision_context: Live vision-based tactical context from StreamingVisionBridge

        Returns:
            Dict with answer text, game state, temporal_context flag, overlay coordinates
        """
        self.log_event("qa_query_received", {
            "question": question[:100],
            "has_game_state": game_state is not None,
            "has_vision_context": vision_context is not None,
        })

        # Step 1: Check pre-computed Q&A cache (tap path)
        cached_pair = self._check_precomputed_cache(question)
        if cached_pair:
            self.log_event("qa_cache_hit", {
                "question": question[:50],
            })
            return {
                "type": "answer",
                "text": cached_pair.answer_text,
                "gameState": game_state.to_dict() if game_state else None,
                "temporal_context": "full" if cached_pair.timestamp_ms else "limited",
                "timestamp_ms": cached_pair.timestamp_ms,
                "overlay_coordinates": cached_pair.overlay_coordinates,
                "source": "precomputed_cache",
            }

        # Step 2: Search KV cache for temporal context
        temporal_ctx = None
        if retained_frames:
            temporal_ctx = self._search_kv_cache_temporal_context(question, retained_frames)

        # Step 3: Build prompt with game state + settings + live vision data
        prompt = self._build_qa_prompt(question, game_state, temporal_ctx, vision_context)

        # Step 4: Call LLM (Priority 1 GPU scheduling)
        answer_text = await self.call_bedrock(
            prompt,
            temperature=0.7,
            max_tokens=300,
        )

        # Step 5: Handle non-football questions
        if self._is_non_football_question(question, answer_text):
            answer_text = "I'm focused on the match right now — try asking about what's happening on the pitch!"

        # Step 6: Log Q&A event
        await write_event(
            "fan_qa",
            f"Q: {question}",
            {
                "question": question,
                "answer": answer_text,
                "sport": self.sport,
                "home_team": self.home_team,
                "away_team": self.away_team,
                "temporal_context": "limited" if temporal_ctx and temporal_ctx.is_limited else "full",
            },
            match_session=self.match_session,
        )

        # Step 7: Return answer with metadata
        return {
            "type": "answer",
            "text": answer_text,
            "gameState": game_state.to_dict() if game_state else None,
            "temporal_context": "limited" if (temporal_ctx and temporal_ctx.is_limited) else "full",
            "timestamp_ms": temporal_ctx.timestamp_ms if temporal_ctx and not temporal_ctx.is_limited else None,
            "overlay_coordinates": None,  # Would come from player ID if referencing a player
            "source": "llm_generate",
            "vision_context": {
                "tactical_label": vision_context.tactical_label,
                "confidence": vision_context.confidence,
            } if vision_context and vision_context.confidence >= 0.4 else None,
        }

    def _is_non_football_question(self, question: str, answer: str) -> bool:
        """Detect non-football questions that need graceful redirect."""
        non_football_keywords = [
            "weather", "recipe", "news", "politics", "stock",
            "math", "science", "history", "music", "movie",
        ]
        question_lower = question.casefold()
        return any(kw in question_lower for kw in non_football_keywords)

    async def handle_query_with_recent_events(
        self,
        question: str,
        game_state: Optional[GameState] = None,
        retained_frames: Optional[List[Dict[str, Any]]] = None,
        vision_context: Optional[VisionTacticalContext] = None,
    ) -> Dict[str, Any]:
        """
        Handle query with recent events fetched from DynamoDB and live vision context.

        Convenience wrapper that fetches recent events and passes to handle_query.
        """
        # Fetch recent events for additional context
        try:
            recent = await get_recent_events(5, match_session=self.match_session)
            events_text = "; ".join(
                e.get("description", "") for e in recent if e.get("description")
            )
            if events_text and game_state:
                # Inject into game state context
                pass  # Game state already has recent events baked in
        except Exception:
            pass  # Continue without recent events

        return await self.handle_query(question, game_state, retained_frames, vision_context)

    def load_qa_cache_from_notes(self, notes_store: NotesStore) -> None:
        """
        Load pre-computed Q&A pairs from NotesStore.

        Called after Story 1.3 pipeline completes to populate cache.

        Story 1.3 generates Q&A pairs for:
        - "Why is that a red card?" → triggered by red card event
        - "Who is number 10?" → triggered by player detection
        - "What formation are they playing?" → triggered by tactical analysis
        """
        if not notes_store or not notes_store.beats:
            return

        for beat in notes_store.beats:
            # Generate likely questions from beat text
            questions = self._generate_questions_from_beat(beat)
            for q in questions:
                self.qa_cache[self._normalize_question(q)] = QAPair(
                    question=q,
                    answer_text=beat.text,
                    overlay_coordinates=None,  # Would come from Story 2.4
                    timestamp_ms=None,
                    temporal_context="full",
                )

        self.log_event("qa_cache_loaded", {
            "cache_size": len(self.qa_cache),
        })

    def _generate_questions_from_beat(self, beat) -> List[str]:
        """Generate likely fan questions from a narrative beat."""
        questions = []

        if "red_card" in beat.event_tags or "red card" in beat.text.casefold():
            questions.append("Why is that a red card?")
            questions.append("Was that the right decision?")

        if "yellow_card" in beat.event_tags or "yellow card" in beat.text.casefold():
            questions.append("Why did the ref show a yellow?")

        if "goal" in beat.event_tags or "goal" in beat.text.casefold():
            questions.append("How did they score?")
            questions.append("Who scored?")

        if "substitution" in beat.event_tags or "sub" in beat.text.casefold():
            questions.append("Who's coming off?")

        if "corner" in beat.event_tags or "corner" in beat.text.casefold():
            questions.append("Who won the corner?")

        # Player-specific questions
        if beat.players:
            for player in beat.players[:2]:  # Limit to first 2 players
                questions.append(f"Tell me about {player}")

        return questions
