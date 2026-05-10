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
import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# streaming-vlm-qwen3-rocm is installed as a package (pip install -e).
# Fallback: add the directory to sys.path for editable installs that aren't on PATH yet.
_STREAMING_VLM_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'streaming-vlm-qwen3-rocm')
if os.path.isdir(_STREAMING_VLM_PATH) and _STREAMING_VLM_PATH not in sys.path:
    sys.path.insert(0, _STREAMING_VLM_PATH)

from streaming.frame_buffer import FrameBuffer, FrameBufferConfig, VideoChunk
from streaming.kv_cache_manager import KVCacheManager, KVCacheConfig, KVCacheState

logger = logging.getLogger("pitchai.streaming")


def clean_model_answer(text: Any) -> str:
    """Return a user-facing answer from raw model text or malformed JSON."""
    import re

    if text is None:
        return ""
    cleaned = str(text).strip()
    if not cleaned:
        return ""

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            for key in ("answer", "commentary", "key_observation", "analysis", "text"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    cleaned = value.strip()
                    break
    except Exception:
        match = re.search(
            r'"(?:answer|commentary|key_observation|analysis|text)"\s*:\s*"([^"]+)',
            cleaned,
            re.DOTALL,
        )
        if match:
            cleaned = match.group(1)

    cleaned = cleaned.replace("\\n", " ").replace('\\"', '"')
    cleaned = cleaned.strip(" \t\r\n{}[],'\"")
    cleaned = re.sub(r'^\s*(?:answer|commentary|analysis|text)\s*:\s*', "", cleaned, flags=re.I)
    cleaned = re.sub(r'",?\s*\d+\s*:\s*.*$', "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:500].rstrip(" ,:;")


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
    Streaming backend using vLLM + Qwen3-VL-2B-Instruct (fits 8GB VRAM).

    Simulates streaming by:
    - Accumulating frames into chunks
    - Sending each chunk as a multi-frame VQA query
    - Maintaining conversation context across chunks via prompt history
    - NOT using KV-cache persistence (vLLM manages its own cache)

    This works on RTX 5060 (8GB) with the 2B model.
    """

    def __init__(self, vllm_base_url: str = "http://localhost:8001",
                 model_name: str = "Qwen/Qwen3-VL-2B-Instruct",
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
        is_question = query_hint is not None
        query = query_hint or "Describe the key action happening in this moment of the match."
        prompt = (
            self._build_question_prompt(context, previous_text, query)
            if is_question
            else self._build_streaming_prompt(context, previous_text, query)
        )

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
        result = (
            self._parse_answer(raw_text, chunk, elapsed)
            if is_question
            else self._parse_commentary(raw_text, chunk, elapsed)
        )

        # Store only automatic commentary for continuity. User answers should
        # not become the seed for the next broadcast line.
        if not is_question:
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

    def _build_question_prompt(self, context: str, previous_text: str, query: str) -> str:
        recent = context or previous_text or "(No previous commentary yet)"
        return f"""You are watching the current moment of a live football match.

Previous commentary for continuity:
{recent}

Answer the user's question using the visible frames from the latest moment. Be direct, grounded in what is on screen, and use plain English.

Question: {query}

Answer in one or two concise sentences. Do not output JSON, markdown, labels, or commentary fields."""

    def _parse_answer(self, raw_text: str, chunk: VideoChunk, latency_ms: float) -> StreamingResult:
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
    StreamingVLM backend using the local streaming-vlm-qwen3-rocm package.

    Uses Qwen3-VL with compact KV-cache patches for real-time video understanding:
    - Attention sinks + sliding window for vision and text
    - KV-cache pruning between chunks
    - SDPA attention (ROCm-compatible, no flash-attn dependency)

    Package: /home/deepu/PitchAI/streaming-vlm-qwen3-rocm
    Model: Qwen/Qwen3-VL-4B-Instruct (override via STREAMING_VLM_MODEL env var)
    """

    def __init__(self, model_path: str = "Qwen/Qwen3-VL-4B-Instruct",
                 sport: str = "football",
                 window_size: int = 16,
                 chunk_duration: int = 1,
                 text_round: int = 16,
                 text_sink: int = 512,
                 text_sliding_window: int = 512,
                 device: str = "auto"):
        self.model_path = model_path
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
        self._past_key_values = None
        self._accumulated_input_ids = None
        self._video_token_positions: List[Tuple[int, int]] = []
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._input_video_path: Optional[str] = None

    async def initialize(self):
        """Load model and processor using local streaming-vlm-qwen3-rocm package."""
        import torch
        from streaming_vlm.inference.generate.streaming_cache import StreamingCache
        from streaming_vlm.inference.inference import StreamingConfig, load_model_and_processor

        logger.info(f"Loading {self.model_path} via streaming-vlm-qwen3-rocm...")
        loop = asyncio.get_event_loop()

        def _load():
            config = StreamingConfig(
                model_path=self.model_path,
                window_size=self.window_size,
                text_sink=self.text_sink,
                text_sliding_window=self.text_sliding_window,
                chunk_duration=float(self.chunk_duration),
                attn_implementation="sdpa",
                device="auto",
                dtype="bfloat16",
            )
            return load_model_and_processor(config)

        self._model, self._processor = await loop.run_in_executor(None, _load)
        self._past_key_values = StreamingCache()
        self._accumulated_input_ids = None
        self._video_token_positions = []
        self._initialized = True
        try:
            import torch
            logger.info(f"StreamingVLM loaded. VRAM: {torch.cuda.memory_allocated() / 1e9:.1f}GB")
        except Exception:
            logger.info("StreamingVLM loaded.")

    async def process_chunk(self, chunk: VideoChunk,
                            previous_text: str = "",
                            query_hint: Optional[str] = None) -> StreamingResult:
        """
        Process a video chunk using StreamingVLM's compact KV-cache algorithm.

        The bridge receives decoded frame chunks from the WebSocket and runs the
        same stateful StreamingVLM cache/prune step used by offline inference.
        """
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
                chunk, query, previous_text, query_hint is not None,
            )

            elapsed = (time.perf_counter() - start) * 1000.0
            self._chunk_count += 1
            self._total_latency_ms += elapsed

            return self._parse_result(result_text, chunk, elapsed)

        except Exception as exc:
            logger.exception(f"StreamingVLM inference failed: {exc}")
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

    def _run_streaming_inference(self, chunk: VideoChunk, query: str, previous_text: str,
                                 stateless: bool = False) -> str:
        """Run one StreamingVLM step over a frame chunk, preserving KV cache."""
        import torch
        from PIL import Image
        import io
        from streaming_vlm.inference.inference import StreamingConfig, prune_kv_cache
        from streaming_vlm.inference.streaming_args import StreamingArgs

        pil_frames = [Image.open(io.BytesIO(f.data)).convert("RGB") for f in chunk.frames]
        fps = len(pil_frames) / max(chunk.duration_seconds, 0.001)
        fps = max(1.0, min(fps, 8.0))

        if stateless:
            prompt = (
                "Answer the user's question about the current football video in plain English. "
                "Do not output JSON, labels, markdown, lists, or commentary fields. "
                "Give one or two direct sentences.\n\n"
                f"Question: {query}"
            )
        else:
            prompt = query
        if previous_text and not stateless:
            prompt = (
                "Previous commentary for continuity:\n"
                f"{previous_text}\n\n"
                f"{query}"
            )

        user_content = [
            {"type": "video", "video": pil_frames, "fps": fps},
            {"type": "text", "text": prompt},
        ]

        full_history = [
            {
                "role": "system",
                "content": (
                    "You are an expert football analyst using continuous video context. "
                    "For user questions, answer directly in plain English. "
                    "For automatic commentary, return concise JSON with commentary, "
                    "tactical_label, key_observation, confidence, and actionable_insight."
                ),
            },
            {"role": "user", "content": user_content},
        ]

        text = self._processor.apply_chat_template(full_history, tokenize=False, add_generation_prompt=True)

        # Resolve actual device from model (device_map='auto' spans CPU/GPU)
        try:
            _device = next(self._model.parameters()).device
        except StopIteration:
            _device = torch.device('cpu')

        inputs = self._processor(
            text=[text],
            images=None,
            videos=[pil_frames],
            padding=True,
            return_tensors="pt",
        )
        inputs = {
            k: v.to(_device) if isinstance(v, torch.Tensor) else v
            for k, v in inputs.items()
        }

        input_ids = inputs["input_ids"]
        video_token_id = getattr(self._model.config, "video_token_id", None)
        if video_token_id is not None and not stateless:
            video_mask = input_ids == video_token_id
            if video_mask.any():
                positions = video_mask.nonzero(as_tuple=True)[1]
                offset = (
                    self._accumulated_input_ids.shape[1]
                    if self._accumulated_input_ids is not None
                    else 0
                )
                self._video_token_positions.append(
                    (offset + positions[0].item(), offset + positions[-1].item())
                )

        streaming_args = StreamingArgs(
            pos_mode="shrink",
            all_text=False,
            input_ids=input_ids,
            video_grid_thw=inputs.get("video_grid_thw") if hasattr(inputs, "get") else None,
            second_per_grid_ts=inputs.get("second_per_grid_ts") if hasattr(inputs, "get") else None,
        )

        generate_kwargs = {
            **inputs,
            "past_key_values": (
                self._past_key_values
                if self._accumulated_input_ids is not None and not stateless
                else None
            ),
            "max_new_tokens": 60,
            "use_cache": True,
            "do_sample": False,
            "streaming_args": streaming_args,
            "repetition_penalty": 1.1,
        }
        tokenizer = getattr(self._processor, "tokenizer", None)
        pad_token_id = getattr(tokenizer, "pad_token_id", None)
        if pad_token_id is not None:
            generate_kwargs["pad_token_id"] = pad_token_id

        with torch.no_grad():
            outputs = self._model.generate(**generate_kwargs)

        generated_ids = outputs.sequences if hasattr(outputs, "sequences") else outputs
        new_tokens = generated_ids[:, input_ids.shape[1]:]
        response = self._processor.batch_decode(new_tokens, skip_special_tokens=True)[0]

        if stateless:
            return clean_model_answer(response)

        if self._accumulated_input_ids is None:
            self._accumulated_input_ids = generated_ids
        else:
            self._accumulated_input_ids = torch.cat(
                [self._accumulated_input_ids, generated_ids[:, input_ids.shape[1]:]],
                dim=1,
            )

        prune_config = StreamingConfig(
            model_path=self.model_path,
            fps=fps,
            chunk_duration=float(self.chunk_duration),
            window_size=self.window_size,
            text_sink=self.text_sink,
            text_sliding_window=self.text_sliding_window,
            max_new_tokens=60,
            attn_implementation="sdpa",
            device=self.device,
            dtype="bfloat16",
        )
        self._accumulated_input_ids, self._past_key_values = prune_kv_cache(
            self._accumulated_input_ids,
            self._past_key_values,
            prune_config,
            self._video_token_positions,
        )
        return response.strip()

    async def reset(self):
        from streaming_vlm.inference.generate.streaming_cache import StreamingCache

        self._cache = KVCacheState()
        self._past_key_values = StreamingCache()
        self._accumulated_input_ids = None
        self._video_token_positions = []
        self._chunk_count = 0
        self._total_latency_ms = 0.0
        self._input_video_path = None
        if self._model:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._chunk_count, 1)
        return {
            "backend": "streaming_vlm",
            "model": self.model_path,
            "chunks_processed": self._chunk_count,
            "avg_latency_ms": round(avg_latency, 1),
            "total_latency_ms": round(self._total_latency_ms, 1),
            "window_size": self.window_size,
            "chunk_duration": self.chunk_duration,
            "streaming_cache_active": self._past_key_values is not None,
            "cached_video_ranges": len(self._video_token_positions),
        }

    def _parse_result(self, raw_text: str, chunk: VideoChunk, latency_ms: float) -> StreamingResult:
        cleaned_text = clean_model_answer(raw_text)
        try:
            import re
            json_match = re.search(r'\{[^{}]*"commentary"[^{}]*\}', raw_text)
            if json_match:
                parsed = json.loads(json_match.group(0))
                commentary = clean_model_answer(parsed.get("commentary", raw_text))
                return StreamingResult(
                    commentary=commentary,
                    tactical_label=parsed.get("tactical_label", "Open Play"),
                    key_observation=clean_model_answer(parsed.get("key_observation", commentary)),
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
            commentary=cleaned_text or raw_text[:200],
            tactical_label="Open Play",
            key_observation=cleaned_text[:100] if cleaned_text else raw_text[:100],
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
    backend: str = "streaming_vlm"     # "auto" | "vllm" | "sglang" | "streaming_vlm"
    vllm_base_url: str = "http://localhost:8001"
    vllm_model: str = "Qwen/Qwen3-VL-2B-Instruct"
    sglang_base_url: str = "http://localhost:30000"
    sglang_model: str = "Qwen/Qwen3-VL-2B-Instruct"
    streaming_vlm_model: str = "Qwen/Qwen3-VL-2B-Instruct"
    sport: str = "football"
    # Frame buffer config
    target_fps: float = 8.0
    chunk_interval_seconds: float = 5.0
    max_chunk_frames: int = 24
    # KV cache config
    window_size: int = 16
    text_sink: int = 512
    text_sliding_window: int = 512
    auto_commentary_enabled: bool = False
    # Fallback
    use_fallback_chain: bool = False     # True only when backend="auto"; explicit backends never fallback


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
        from streaming.factory import get_streaming_backend, FallbackStreamingBackend

        # "auto" uses the fallback chain (Level 1→2→3→4).
        # Any explicit backend ("streaming_vlm", "sglang", "vllm") is used as-is —
        # no cascade to another backend on failure.
        if self.config.backend == "auto" or self.config.use_fallback_chain:
            logger.info("Initializing with fallback chain (Level 1→2→3→4)")
            self._backend = FallbackStreamingBackend(start_level=1)
            await self._backend.initialize()
            stats = self._backend.get_stats()
            logger.info(f"Fallback chain initialized at Level {stats.get('fallback_level', 'unknown')}")
        else:
            # Explicit backend selection
            if self.config.backend == "streaming_vlm":
                self._backend = StreamingVLMBackend(
                    model_path=self.config.streaming_vlm_model,
                    sport=self.config.sport,
                    window_size=self.config.window_size,
                    text_sink=self.config.text_sink,
                    text_sliding_window=self.config.text_sliding_window,
                )
            elif self.config.backend == "sglang":
                from streaming.sglang_backend import SGLangStreamingBackend
                self._backend = SGLangStreamingBackend(
                    sglang_base_url=self.config.sglang_base_url,
                    model_name=self.config.sglang_model,
                    sport=self.config.sport,
                )
            elif self.config.backend == "vllm":
                self._backend = VLLMStreamingBackend(
                    vllm_base_url=self.config.vllm_base_url,
                    model_name=self.config.vllm_model,
                    sport=self.config.sport,
                )
            else:  # "auto" - use factory to pick best available
                self._backend = get_streaming_backend()

            await self._backend.initialize()
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

        if chunk is None or not self.config.auto_commentary_enabled:
            return None

        return await self._process_chunk(chunk)

    async def _process_chunk(self, chunk: VideoChunk, query_hint: Optional[str] = None) -> Dict[str, Any]:
        """Process a formed chunk through the streaming backend."""
        is_question = query_hint is not None
        result = await self._backend.process_chunk(
            chunk,
            previous_text=self._previous_text,
            query_hint=query_hint,
        )

        # Update context for next chunk
        if result.commentary and not is_question:
            self._commentary_history.append(result.commentary)
            self._previous_text = result.commentary
            if len(self._commentary_history) > 20:
                self._commentary_history = self._commentary_history[-20:]

        self.kv_cache.state.chunk_index = chunk.chunk_index
        self.kv_cache.state.total_processed_seconds += chunk.duration_seconds

        return result.to_dict()

    async def force_flush(self, query_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Force process any remaining buffered frames."""
        if query_hint is None and not self.config.auto_commentary_enabled:
            return None
        chunk = self.frame_buffer.force_chunk(
            min_frames=2 if query_hint else 1,
            include_recent=query_hint is not None,
        )
        if chunk is None:
            return None
        return await self._process_chunk(chunk, query_hint=query_hint)

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
