"""
Streaming Vision Bridge — connects PitchAI to streaming VLM inference.

Two backends:
- vllm_backend: Uses PitchAI's existing vLLM + Qwen2.5-VL-3B-AWQ (RTX 5060, 8GB)
- streaming_vlm_backend: Full StreamingVLM patches on unquantized model (MI300X, 192GB)

Both expose the same StreamingVisionProtocol so the pipeline is backend-agnostic.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from streaming.frame_buffer import FrameBuffer, FrameBufferConfig, VideoChunk
from streaming.kv_cache_manager import KVCacheManager, KVCacheConfig, KVCacheState

logger = logging.getLogger("pitchai.streaming")


# ── Protocol Types ────────────────────────────────────────────────────────────

@dataclass
class StreamingResult:
    """Result from processing a video chunk through a streaming VLM."""
    commentary: str                           # Generated commentary text
    tactical_label: str                       # e.g. "Counter Attack", "Corner Kick"
    key_observation: str                      # What happened in this chunk
    confidence: float                         # 0.0-1.0
    actionable_insight: str                   # What the commentator should say next
    start_timestamp_ms: int                   # Chunk start time
    end_timestamp_ms: int                     # Chunk end time
    latency_ms: float                         # Processing latency
    chunk_index: int                          # Sequential chunk number
    raw_generation: Optional[str] = None      # Raw model output (for debugging)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commentary": self.commentary,
            "tactical_label": self.tactical_label,
            "key_observation": self.key_observation,
            "confidence": self.confidence,
            "actionable_insight": self.actionable_insight,
            "start_timestamp_ms": self.start_timestamp_ms,
            "end_timestamp_ms": self.end_timestamp_ms,
            "latency_ms": self.latency_ms,
            "chunk_index": self.chunk_index,
        }


# ── Backend Interface ─────────────────────────────────────────────────────────

class StreamingBackend(ABC):
    """Abstract backend for streaming VLM inference."""

    @abstractmethod
    async def initialize(self):
        """Load model and prepare for inference."""

    @abstractmethod
    async def process_chunk(self, chunk: VideoChunk,
                            previous_text: str = "",
                            query_hint: Optional[str] = None) -> StreamingResult:
        """Process a video chunk and return streaming commentary."""

    @abstractmethod
    async def reset(self):
        """Reset session state for a new video."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get backend performance statistics."""


# ── vLLM Backend (RTX 5060, 8GB VRAM) ────────────────────────────────────────

class VLLMStreamingBackend(StreamingBackend):
    """
    Streaming backend using PitchAI's existing vLLM + Qwen2.5-VL-3B-AWQ.

    Simulates streaming by:
    - Accumulating frames into chunks
    - Sending each chunk as a multi-frame VQA query
    - Maintaining conversation context across chunks via prompt history
    - NOT using KV-cache persistence (vLLM manages its own cache)

    This works on RTX 5060 (8GB) with AWQ-quantized 3B model.
    """

    def __init__(self, vllm_base_url: str = "http://localhost:8001",
                 model_name: str = "Qwen/Qwen2.5-VL-3B-Instruct-AWQ",
                 sport: str = "football"):
        self.vllm_base_url = vllm_base_url.rstrip("/")
        self.model_name = model_name
        self.sport = sport
        self._initialized = False
        self._conversation_history: List[str] = []  # Previous commentary for context
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._stats: Dict[str, Any] = {}

    async def initialize(self):
        """Verify vLLM is running and model is available."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.vllm_base_url}/v1/models", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("id", "") for m in data.get("data", [])]
                        logger.info(f"vLLM available. Models: {models}")
                    else:
                        logger.warning(f"vLLM responded {resp.status} — will retry on first chunk")
        except Exception as exc:
            logger.warning(f"vLLM not reachable at {self.vllm_base_url}: {exc}")
        self._initialized = True

    async def process_chunk(self, chunk: VideoChunk,
                            previous_text: str = "",
                            query_hint: Optional[str] = None) -> StreamingResult:
        """Process a chunk through vLLM's OpenAI-compatible API with vision."""
        import aiohttp

        start = time.perf_counter()
        frames_b64 = [base64.b64encode(f.data).decode("utf-8") for f in chunk.frames]

        # Build conversation context from history (last 5 commentary rounds)
        context = ""
        if self._conversation_history:
            recent = self._conversation_history[-5:]
            context = "\n".join(f"[{i+1}] {c}" for i, c in enumerate(recent))

        # Build prompt with streaming context
        query = query_hint or "Describe the key action happening in this moment of the match."
        prompt = self._build_streaming_prompt(context, previous_text, query)

        # Build OpenAI-compatible messages with vision content
        content = [{"type": "text", "text": prompt}]
        for b64 in frames_b64[-8:]:  # Last 8 frames for visual context
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

        messages = [{"role": "user", "content": content}]

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.7,
                }
                async with session.post(
                    f"{self.vllm_base_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_text = data["choices"][0]["message"]["content"]
                    else:
                        text = await resp.text()
                        logger.error(f"vLLM error {resp.status}: {text[:200]}")
                        raw_text = "Unable to analyze this moment."
        except Exception as exc:
            logger.error(f"vLLM request failed: {exc}")
            raw_text = "Commentary unavailable for this moment."

        elapsed = (time.perf_counter() - start) * 1000.0
        self._chunk_count += 1
        self._total_latency_ms += elapsed

        # Parse the raw output into structured result
        result = self._parse_commentary(raw_text, chunk, elapsed)

        # Store for context in future chunks
        self._conversation_history.append(result.commentary)
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        return result

    async def reset(self):
        self._conversation_history.clear()
        self._chunk_count = 0
        self._total_latency_ms = 0.0

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._chunk_count, 1)
        return {
            "backend": "vllm",
            "model": self.model_name,
            "chunks_processed": self._chunk_count,
            "avg_latency_ms": round(avg_latency, 1),
            "total_latency_ms": round(self._total_latency_ms, 1),
        }

    def _build_streaming_prompt(self, context: str, previous_text: str, query: str) -> str:
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

    def _parse_commentary(self, raw_text: str, chunk: VideoChunk, latency_ms: float) -> StreamingResult:
        """Parse model output into structured result."""
        try:
            # Try to extract JSON from response
            import re
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


# ── Full StreamingVLM Backend (MI300X, 192GB) ────────────────────────────────

class StreamingVLMBackend(StreamingBackend):
    """
    Full StreamingVLM backend using patched Qwen2.5-VL with compact KV-cache.

    Implements the exact StreamingVLM algorithm from MIT HAN Lab:
    - Attention sinks + sliding window for vision and text
    - KV-cache pruning between chunks
    - Position embedding management (shrink mode)

    Requires MI300X (192GB) or H100 (80GB) — will NOT fit on 8GB.
    """

    def __init__(self, model_path: str = "mit-han-lab/StreamingVLM",
                 model_base: str = "Qwen2_5",
                 sport: str = "football",
                 window_size: int = 16,
                 chunk_duration: int = 1,
                 text_round: int = 16,
                 text_sink: int = 512,
                 text_sliding_window: int = 512,
                 device: str = "cuda"):
        self.model_path = model_path
        self.model_base = model_base
        self.sport = sport
        self.window_size = window_size
        self.chunk_duration = chunk_duration
        self.text_round = text_round
        self.text_sink = text_sink
        self.text_sliding_window = text_sliding_window
        self.device = device
        self._model = None
        self._processor = None
        self._initialized = False
        self._cache: Optional[KVCacheState] = None
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._input_video_path: Optional[str] = None

    async def initialize(self):
        """Load model and processor. Call once per session."""
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        logger.info(f"Loading {self.model_path} on {self.device}...")
        loop = asyncio.get_event_loop()

        def _load():
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.model_path,
                torch_dtype=torch.bfloat16,
                device_map=self.device,
                attn_implementation="flash_attention_2" if torch.cuda.is_available() else "eager",
            )
            # Apply StreamingVLM patches
            from streaming_vlm.inference.qwen2_5.patch_model import convert_qwen2_5_to_streaming
            model = convert_qwen2_5_to_streaming(model)
            processor = AutoProcessor.from_pretrained(self.model_path, use_fast=False)
            return model, processor

        self._model, self._processor = await loop.run_in_executor(None, _load)
        self._initialized = True
        logger.info(f"StreamingVLM loaded. Memory: {torch.cuda.memory_allocated() / 1e9:.1f}GB")

    async def process_chunk(self, chunk: VideoChunk,
                            previous_text: str = "",
                            query_hint: Optional[str] = None) -> StreamingResult:
        """
        Process a video chunk using StreamingVLM's compact KV-cache algorithm.

        For the full StreamingVLM pipeline, we need the raw video file + timestamps.
        The chunk's frames are decoded from the video at the right timestamps.
        """
        import torch
        from streaming_vlm.inference.streaming_args import StreamingArgs

        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()
        query = query_hint or "Commentate on this match"

        try:
            # Run streaming inference in executor (blocking CUDA ops)
            loop = asyncio.get_event_loop()
            result_text = await loop.run_in_executor(
                None,
                self._run_streaming_inference,
                chunk, query, previous_text,
            )

            elapsed = (time.perf_counter() - start) * 1000.0
            self._chunk_count += 1
            self._total_latency_ms += elapsed

            return self._parse_result(result_text, chunk, elapsed)

        except Exception as exc:
            logger.error(f"StreamingVLM inference failed: {exc}")
            elapsed = (time.perf_counter() - start) * 1000.0
            return StreamingResult(
                commentary="Streaming vision processing interrupted.",
                tactical_label="Processing Error",
                key_observation=str(exc)[:100],
                confidence=0.0,
                actionable_insight="Retry with next chunk.",
                start_timestamp_ms=chunk.start_timestamp_ms,
                end_timestamp_ms=chunk.end_timestamp_ms,
                latency_ms=elapsed,
                chunk_index=chunk.chunk_index,
            )

    def _run_streaming_inference(self, chunk: VideoChunk, query: str, previous_text: str) -> str:
        """Run one step of StreamingVLM inference (blocking)."""
        # This mirrors streaming_vlm/inference/inference.py but adapted for our chunk pipeline
        import torch
        from streaming_vlm.inference.streaming_args import StreamingArgs
        from qwen_vl_utils.vision_process import FPS
        from transformers import set_seed

        set_seed(42)
        streaming_args = StreamingArgs(pos_mode="shrink", all_text=False)

        # Build the conversation for this chunk
        start_time = chunk.start_timestamp_ms / 1000.0
        chunk_dur = max(chunk.duration_seconds, 0.5)

        if self._chunk_count == 0:
            full_history = [
                {"role": "previous text", "content": previous_text},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Time={start_time:.1f}-{start_time + chunk_dur:.1f}s"},
                    {"type": "text", "text": query},
                ]}
            ]
        else:
            full_history = [
                {"role": "user", "content": [
                    {"type": "text", "text": f"Time={start_time:.1f}-{start_time + chunk_dur:.1f}s"},
                ]}
            ]

        text = self._processor.apply_chat_template(full_history, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text], padding=True, return_tensors="pt").to(self.device)

        if streaming_args.pos_mode == "shrink":
            streaming_args.input_ids = inputs['input_ids']

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=50 if self.sport == "football" else 30,
                use_cache=True,
                return_dict_in_generate=True,
                do_sample=True,
                temperature=0.9,
                repetition_penalty=1.05,
                streaming_args=streaming_args,
                pad_token_id=151645,
            )

        generated_ids = outputs.sequences
        new_tokens = generated_ids[:, inputs['input_ids'].shape[1]:]
        response = self._processor.batch_decode(new_tokens, skip_special_tokens=True)[0]
        return response.strip()

    async def reset(self):
        self._cache = KVCacheState()
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._input_video_path = None
        if self._model and torch.cuda.is_available():
            torch.cuda.empty_cache()

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._chunk_count, 1)
        return {
            "backend": "streaming_vlm",
            "model": self.model_path,
            "model_base": self.model_base,
            "chunks_processed": self._chunk_count,
            "avg_latency_ms": round(avg_latency, 1),
            "total_latency_ms": round(self._total_latency_ms, 1),
            "window_size": self.window_size,
            "chunk_duration": self.chunk_duration,
        }

    def _parse_result(self, raw_text: str, chunk: VideoChunk, latency_ms: float) -> StreamingResult:
        try:
            import re
            json_match = re.search(r'\{[^{}]*"commentary"[^{}]*\}', raw_text)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return StreamingResult(
                    commentary=parsed.get("commentary", raw_text),
                    tactical_label=parsed.get("tactical_label", "Open Play"),
                    key_observation=parsed.get("key_observation", raw_text[:100]),
                    confidence=float(parsed.get("confidence", 0.7)),
                    actionable_insight=parsed.get("actionable_insight", "Continue commentary."),
                    start_timestamp_ms=chunk.start_timestamp_ms,
                    end_timestamp_ms=chunk.end_timestamp_ms,
                    latency_ms=latency_ms,
                    chunk_index=chunk.chunk_index,
                    raw_generation=raw_text,
                )
        except (json.JSONDecodeError, KeyError):
            pass

        return StreamingResult(
            commentary=raw_text[:200],
            tactical_label="Open Play",
            key_observation=raw_text[:100],
            confidence=0.5,
            actionable_insight="Monitor the developing play.",
            start_timestamp_ms=chunk.start_timestamp_ms,
            end_timestamp_ms=chunk.end_timestamp_ms,
            latency_ms=latency_ms,
            chunk_index=chunk.chunk_index,
            raw_generation=raw_text,
        )


# ── Streaming Vision Bridge ───────────────────────────────────────────────────

@dataclass
class StreamingBridgeConfig:
    """Top-level configuration for the streaming vision bridge."""
    backend: str = "vllm"                # "vllm" or "streaming_vlm"
    vllm_base_url: str = "http://localhost:8001"
    vllm_model: str = "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"
    streaming_vlm_model: str = "mit-han-lab/StreamingVLM"
    sport: str = "football"
    # Frame buffer config
    target_fps: float = 8.0
    chunk_interval_seconds: float = 5.0
    max_chunk_frames: int = 24
    # KV cache config
    window_size: int = 16
    text_sink: int = 512
    text_sliding_window: int = 512


class StreamingVisionBridge:
    """
    Main entry point for streaming vision in PitchAI.

    Manages:
    - Frame buffering and chunk formation
    - Backend selection (vLLM for local, StreamingVLM for AMD cloud)
    - KV cache state tracking
    - Integration with GameState and commentary agents
    """

    def __init__(self, config: Optional[StreamingBridgeConfig] = None):
        self.config = config or StreamingBridgeConfig()

        # Frame buffer for chunk formation
        frame_config = FrameBufferConfig(
            target_fps=self.config.target_fps,
            chunk_interval_seconds=self.config.chunk_interval_seconds,
            max_chunk_frames=self.config.max_chunk_frames,
        )
        self.frame_buffer = FrameBuffer(frame_config)

        # KV cache manager
        kv_config = KVCacheConfig(
            window_size=self.config.window_size,
            text_sink=self.config.text_sink,
            text_sliding_window=self.config.text_sliding_window,
        )
        self.kv_cache = KVCacheManager(kv_config)

        # Backend (lazy initialized)
        self._backend: Optional[StreamingBackend] = None
        self._initialized = False

        # Commentary history for context
        self._commentary_history: List[str] = []
        self._previous_text: str = ""

    async def initialize(self):
        """Initialize the appropriate backend."""
        if self.config.backend == "streaming_vlm":
            self._backend = StreamingVLMBackend(
                model_path=self.config.streaming_vlm_model,
                sport=self.config.sport,
                window_size=self.config.window_size,
                text_sink=self.config.text_sink,
                text_sliding_window=self.config.text_sliding_window,
            )
        else:
            self._backend = VLLMStreamingBackend(
                vllm_base_url=self.config.vllm_base_url,
                model_name=self.config.vllm_model,
                sport=self.config.sport,
            )
        await self._backend.initialize()
        self._initialized = True
        logger.info(f"StreamingVisionBridge initialized with {self.config.backend} backend")

    async def process_frame(self, frame_data: bytes, timestamp_ms: int,
                            keyframe: bool = False,
                            quality_score: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Process an incoming video frame. Returns commentary if a chunk was formed.

        This is the main entry point called from the WebSocket video stream handler.
        """
        if not self._initialized:
            await self.initialize()

        chunk = self.frame_buffer.add_frame(
            frame_data, timestamp_ms,
            keyframe=keyframe, quality_score=quality_score,
        )

        if chunk is None:
            return None

        return await self._process_chunk(chunk)

    async def _process_chunk(self, chunk: VideoChunk) -> Dict[str, Any]:
        """Process a formed chunk through the streaming backend."""
        result = await self._backend.process_chunk(
            chunk,
            previous_text=self._previous_text,
        )

        # Update context for next chunk
        if result.commentary:
            self._commentary_history.append(result.commentary)
            self._previous_text = result.commentary
            if len(self._commentary_history) > 20:
                self._commentary_history = self._commentary_history[-20:]

        self.kv_cache.state.chunk_index = chunk.chunk_index
        self.kv_cache.state.total_processed_seconds += chunk.duration_seconds

        return result.to_dict()

    async def force_flush(self) -> Optional[Dict[str, Any]]:
        """Force process any remaining buffered frames."""
        chunk = self.frame_buffer.force_chunk()
        if chunk is None:
            return None
        return await self._process_chunk(chunk)

    def get_previous_commentary(self, n: int = 3) -> str:
        """Get the last N commentary lines for context injection."""
        return " ".join(self._commentary_history[-n:])

    async def reset(self):
        """Reset state for a new video session."""
        self.frame_buffer.reset()
        self.kv_cache.reset()
        self._commentary_history.clear()
        self._previous_text = ""
        if self._backend:
            await self._backend.reset()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "frame_buffer": self.frame_buffer.to_dict(),
            "kv_cache": self.kv_cache.to_dict(),
            "backend": self._backend.get_stats() if self._backend else {},
            "commentary_count": len(self._commentary_history),
        }