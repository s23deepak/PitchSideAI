"""
SGLang Backend for Streaming Vision

SGLang provides:
- Lower TTFT (Time To First Token) vs vLLM
- RadixAttention for prefix reuse across frames
- Better streaming smoothness for continuous video

This backend connects to an SGLang serving endpoint and leverages
RadixAttention for efficient KV-cache prefix sharing between video chunks.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from streaming.streaming_bridge import StreamingBackend, StreamingResult, clean_model_answer
from streaming.frame_buffer import VideoChunk

logger = logging.getLogger("pitchai.streaming.sglang")


class SGLangStreamingBackend(StreamingBackend):
    """
    Streaming backend using SGLang serving engine.

    SGLang (Structured Generation Language) is a serving engine optimized for:
    - Low latency streaming inference
    - RadixAttention for prefix cache reuse
    - Disaggregated prefill/decode

    Key difference from vLLM backend:
    - vLLM: Each frame/chunk is independent, no KV-cache reuse
    - SGLang: RadixAttention maintains prefix cache across chunks

    Requires SGLang server running at sglang_base_url.
    Start SGLang with:
        python -m sglang.launch_server \\
            --model-path Qwen/Qwen2.5-VL-3B-Instruct \\
            --port 30000 \\
            --mem-fraction-static 0.8
    """

    def __init__(
        self,
        sglang_base_url: str = "http://localhost:30000",
        model_name: str = "Qwen/Qwen2.5-VL-3B-Instruct",
        sport: str = "football",
        enable_radix_attention: bool = True,
    ):
        self.sglang_base_url = sglang_base_url.rstrip("/")
        self.model_name = model_name
        self.sport = sport
        self.enable_radix_attention = enable_radix_attention
        self._initialized = False
        self._session_id: Optional[str] = None
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._conversation_history: List[str] = []
        self._stats: Dict[str, Any] = {}

    async def initialize(self):
        """Verify SGLang server is running and model is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.sglang_base_url}/get_model_info",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"SGLang available: {data.get('model_path', 'unknown')}")
                    else:
                        logger.warning(f"SGLang responded {resp.status} — will retry on first chunk")
        except Exception as exc:
            logger.warning(f"SGLang not reachable at {self.sglang_base_url}: {exc}")
            logger.info("Will attempt connection on first process_chunk call")

        self._initialized = True

    async def process_chunk(
        self,
        chunk: VideoChunk,
        previous_text: str = "",
        query_hint: Optional[str] = None,
    ) -> StreamingResult:
        """
        Process a video chunk through SGLang with RadixAttention.

        SGLang's RadixAttention automatically handles prefix cache reuse
        across chunks when the same session is used.
        """
        start = time.perf_counter()

        # Encode frames as base64 for HTTP transmission
        frames_b64 = [base64.b64encode(f.data).decode("utf-8") for f in chunk.frames]

        # Build conversation context from history (last 5 commentary rounds)
        context = ""
        if self._conversation_history:
            recent = self._conversation_history[-5:]
            context = "\n".join(f"[{i+1}] {c}" for i, c in enumerate(recent))

        # Build prompt with streaming context
        is_question = query_hint is not None
        query = query_hint or "Describe the key action happening in this moment of the match."
        prompt = (
            self._build_question_prompt(context, query)
            if is_question
            else self._build_streaming_prompt(context, query)
        )

        # Build messages with vision content
        content = [{"type": "text", "text": prompt}]
        for b64 in frames_b64[-8:]:  # Last 8 frames for visual context
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

        messages = [{"role": "user", "content": content}]

        try:
            async with aiohttp.ClientSession() as session:
                # SGLang OpenAI-compatible API
                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.7,
                    "stream": False,
                }

                # Enable RadixAttention prefix reuse
                if self.enable_radix_attention and self._session_id:
                    payload["session_id"] = self._session_id

                async with session.post(
                    f"{self.sglang_base_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_text = data["choices"][0]["message"]["content"]

                        # Extract session_id for prefix reuse in next chunk
                        if "session_id" in data:
                            self._session_id = data["session_id"]
                    else:
                        text = await resp.text()
                        logger.error(f"SGLang error {resp.status}: {text[:200]}")
                        raw_text = "Unable to analyze this moment."
        except Exception as exc:
            logger.error(f"SGLang request failed: {exc}")
            raw_text = "Commentary unavailable for this moment."

        elapsed = (time.perf_counter() - start) * 1000.0
        self._chunk_count += 1
        self._total_latency_ms += elapsed

        # Parse the raw output into structured result
        result = (
            self._parse_answer(raw_text, chunk, elapsed)
            if is_question
            else self._parse_commentary(raw_text, chunk, elapsed)
        )

        # Store only automatic commentary for future continuity.
        if not is_question:
            self._conversation_history.append(result.commentary)
            if len(self._conversation_history) > 20:
                self._conversation_history = self._conversation_history[-20:]

        return result

    async def reset(self):
        """Reset session state for a new video."""
        self._conversation_history.clear()
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._session_id = None
        self._stats = {}

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._chunk_count, 1)
        return {
            "backend": "sglang",
            "model": self.model_name,
            "chunks_processed": self._chunk_count,
            "avg_latency_ms": round(avg_latency, 1),
            "total_latency_ms": round(self._total_latency_ms, 1),
            "radix_attention_enabled": self.enable_radix_attention,
            "session_id": self._session_id,
        }

    def _build_streaming_prompt(
        self,
        context: str,
        query: str,
    ) -> str:
        """Build prompt for streaming commentary with context."""
        return f"""You are a live football commentator providing real-time, Peter Drury-style commentary.

Previous commentary (for context):
{context if context else "(This is the start of the match)"}

IMPORTANT: Look at these frames from the current moment of the match. Describe ONLY what you see happening NOW.

{query}

Respond in JSON format:
{{"commentary": "2-3 sentences of dramatic live commentary about what just happened",
 "tactical_label": "one tactical category: Build Up, Counter Attack, Set Piece, Defensive Stand, Goal Attempt, Ball Recovery, Midfield Battle, Wings Play, Pressing, or Open Play",
 "key_observation": "the single most important thing happening in this moment",
 "confidence": 0.0-1.0,
 "actionable_insight": "what the commentator should watch for next"}}

Commentary Rules:
- Be specific: name players if visible, describe positions and movement
- Build drama: use the style of Peter Drury — poetic, passionate, precise
- Stay current: comment on THIS moment, not what happened before
- Keep it tight: 2-3 sentences maximum"""

    def _build_question_prompt(
        self,
        context: str,
        query: str,
    ) -> str:
        """Build prompt for an interrupting user question."""
        return f"""You are watching the current moment of a live football match.

Previous commentary for continuity:
{context if context else "(No previous commentary yet)"}

Answer the user's question using the visible frames from the latest moment. Be direct, grounded in what is on screen, and use plain English.

Question: {query}

Answer in one or two concise sentences. Do not output JSON, markdown, labels, or commentary fields."""

    def _parse_answer(
        self,
        raw_text: str,
        chunk: VideoChunk,
        latency_ms: float,
    ) -> StreamingResult:
        """Parse direct Q&A output into the shared result shape."""
        answer = clean_model_answer(raw_text)
        return StreamingResult(
            commentary=answer or raw_text[:200],
            tactical_label="Question Answer",
            key_observation=answer[:100] if answer else raw_text[:100],
            confidence=0.6,
            actionable_insight="Resume live commentary from the newest frames.",
            start_timestamp_ms=chunk.start_timestamp_ms,
            end_timestamp_ms=chunk.end_timestamp_ms,
            latency_ms=latency_ms,
            chunk_index=chunk.chunk_index,
            raw_generation=raw_text,
        )

    def _parse_commentary(
        self,
        raw_text: str,
        chunk: VideoChunk,
        latency_ms: float,
    ) -> StreamingResult:
        """Parse model output into structured result."""
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*"commentary"[^{}]*\}', raw_text)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return StreamingResult(
                    commentary=parsed.get("commentary", raw_text),
                    tactical_label=parsed.get("tactical_label", "Open Play"),
                    key_observation=parsed.get("key_observation", raw_text[:100]),
                    confidence=float(parsed.get("confidence", 0.7)),
                    actionable_insight=parsed.get("actionable_insight", "Continue watching for developments."),
                    start_timestamp_ms=chunk.start_timestamp_ms,
                    end_timestamp_ms=chunk.end_timestamp_ms,
                    latency_ms=latency_ms,
                    chunk_index=chunk.chunk_index,
                    raw_generation=raw_text,
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        return StreamingResult(
            commentary=raw_text[:200],
            tactical_label="Open Play",
            key_observation=raw_text[:100],
            confidence=0.5,
            actionable_insight="Watch for the next phase of play.",
            start_timestamp_ms=chunk.start_timestamp_ms,
            end_timestamp_ms=chunk.end_timestamp_ms,
            latency_ms=latency_ms,
            chunk_index=chunk.chunk_index,
            raw_generation=raw_text,
        )
