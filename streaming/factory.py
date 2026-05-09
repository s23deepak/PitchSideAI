"""
Streaming Backend Factory with Fallback Chain

Implements a 4-level fallback chain for streaming vision:

Level 1: SGLang + StreamingVLM (full capability)
  - RadixAttention prefix reuse
  - Compact KV-cache with attention sinks
  - Temporal scrub across chunks
  - Best for: MI300X, H100 with SGLang serving

Level 2: SGLang + Custom KV Window (loses StreamingVLM optimizations)
  - RadixAttention prefix reuse
  - Standard sliding window (no attention sinks)
  - Temporal continuity maintained
  - Best for: When StreamingVLM patches fail

Level 3: Pre-computed Embeddings + vLLM (loses temporal scrub)
  - No KV-cache reuse
  - Each chunk independent
  - Fallback when SGLang unavailable

Level 4: vLLM Frame-by-Frame (no temporal continuity)
  - Basic frame-by-frame VQA
  - No temporal continuity
  - Last resort fallback

Usage:
    from streaming.factory import get_streaming_backend

    backend = get_streaming_backend(target_level=1)
    await backend.initialize()
    result = await backend.process_chunk(chunk)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from streaming.streaming_bridge import StreamingBackend

logger = logging.getLogger("pitchai.streaming.factory")


def get_streaming_backend(
    backend: Optional[str] = None,
    target_level: Optional[int] = None,
) -> StreamingBackend:
    """
    Get streaming backend with fallback chain.

    Args:
        backend: Explicit backend selection ("sglang", "vllm", "streaming_vlm")
        target_level: Fallback level (1-4). Lower is better capability.

    Returns:
        StreamingBackend instance (may be fallback wrapper)

    Fallback Chain:
        Level 1: SGLang + StreamingVLM (full capability)
        Level 2: SGLang + Custom KV Window
        Level 3: Pre-computed Embeddings + vLLM
        Level 4: vLLM Frame-by-Frame
    """
    # Explicit backend selection overrides auto-detection
    if backend == "sglang":
        return _create_sglang_backend()
    elif backend == "streaming_vlm":
        return _create_streaming_vlm_backend()
    elif backend == "vllm":
        return _create_vllm_backend()

    # Auto-detect based on environment and availability
    if target_level is not None:
        return _get_backend_by_level(target_level)

    # Default: try best available
    return _get_best_available_backend()


def _create_sglang_backend() -> StreamingBackend:
    """Create SGLang backend (Level 2 capability)."""
    from streaming.sglang_backend import SGLangStreamingBackend

    sglang_url = os.environ.get("SGLANG_BASE_URL", "http://localhost:30000")
    model_name = os.environ.get("VISION_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct")
    sport = os.environ.get("SPORT", "football")

    logger.info(f"Creating SGLang backend: {sglang_url}/{model_name}")
    return SGLangStreamingBackend(
        sglang_base_url=sglang_url,
        model_name=model_name,
        sport=sport,
    )


def _create_streaming_vlm_backend() -> StreamingBackend:
    """Create StreamingVLM backend using local streaming-vlm-qwen3-rocm package."""
    from streaming.streaming_bridge import StreamingVLMBackend

    model_path = os.environ.get(
        "STREAMING_VLM_MODEL",
        "Qwen/Qwen3-VL-4B-Instruct"  # Default for local package (Qwen3-VL, not 2.5)
    )
    sport = os.environ.get("SPORT", "football")

    logger.info(f"Creating StreamingVLM backend (local ROCm package): {model_path}")
    return StreamingVLMBackend(
        model_path=model_path,
        sport=sport,
    )


def _create_vllm_backend() -> StreamingBackend:
    """Create vLLM backend (Level 4 capability)."""
    from streaming.streaming_bridge import VLLMStreamingBackend

    vllm_url = os.environ.get("VLLM_BASE_URL", "http://localhost:8001")
    model_name = os.environ.get(
        "VISION_MODEL",
        "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"
    )
    sport = os.environ.get("SPORT", "football")

    logger.info(f"Creating vLLM backend: {vllm_url}/{model_name}")
    return VLLMStreamingBackend(
        vllm_base_url=vllm_url,
        model_name=model_name,
        sport=sport,
    )


def _get_backend_by_level(level: int) -> StreamingBackend:
    """
    Get backend for specific fallback level.

    Level 1: SGLang + StreamingVLM (full capability)
    Level 2: SGLang + Custom KV Window
    Level 3: Pre-computed Embeddings + vLLM
    Level 4: vLLM Frame-by-Frame
    """
    if level == 1:
        # Try StreamingVLM (may fail if not installed)
        try:
            backend = _create_streaming_vlm_backend()
            backend._fallback_level = 1
            return backend
        except ImportError as e:
            logger.warning(f"StreamingVLM not available: {e}. Falling back to Level 2.")
            return _get_backend_by_level(2)

    elif level == 2:
        # SGLang without StreamingVLM patches
        try:
            backend = _create_sglang_backend()
            backend._fallback_level = 2
            return backend
        except Exception as e:
            logger.warning(f"SGLang not available: {e}. Falling back to Level 3.")
            return _get_backend_by_level(3)

    elif level == 3:
        # vLLM with pre-computed embeddings (not yet implemented)
        # For now, fall through to Level 4
        logger.warning("Level 3 (pre-computed embeddings) not implemented. Using Level 4.")
        return _get_backend_by_level(4)

    elif level == 4:
        # vLLM frame-by-frame (always available)
        backend = _create_vllm_backend()
        backend._fallback_level = 4
        return backend

    else:
        raise ValueError(f"Invalid fallback level: {level}. Expected 1-4.")


def _get_best_available_backend() -> StreamingBackend:
    """
    Get the best available backend using fallback chain.

    Tries levels in order: 1 → 2 → 3 → 4
    Returns first available backend.
    """
    for level in [1, 2, 3, 4]:
        try:
            return _get_backend_by_level(level)
        except Exception as e:
            logger.debug(f"Level {level} failed: {e}")
            continue

    # Should never reach here (Level 4 should always work)
    raise RuntimeError("All streaming backends failed")


class FallbackStreamingBackend(StreamingBackend):
    """
    Wrapper that implements automatic fallback between levels.

    Usage:
        backend = FallbackStreamingBackend(start_level=1)
        await backend.initialize()

        # If process_chunk fails, automatically tries next level
        result = await backend.process_chunk(chunk)
    """

    def __init__(self, start_level: int = 1):
        self.start_level = start_level
        self.current_level = start_level
        self._backend: Optional[StreamingBackend] = None
        self._errors: list[str] = []

    async def initialize(self):
        """Initialize backend at current level."""
        while self.current_level <= 4:
            try:
                self._backend = _get_backend_by_level(self.current_level)
                await self._backend.initialize()
                logger.info(f"Initialized at fallback level {self.current_level}")
                return
            except Exception as e:
                self._errors.append(f"Level {self.current_level}: {e}")
                logger.warning(f"Fallback level {self.current_level} failed: {e}")
                self.current_level += 1

        raise RuntimeError(
            f"All fallback levels failed. Errors: {self._errors}"
        )

    async def process_chunk(self, chunk, previous_text="", query_hint=None):
        """Process chunk with automatic fallback on failure."""
        if self._backend is None:
            await self.initialize()

        try:
            return await self._backend.process_chunk(
                chunk, previous_text, query_hint
            )
        except Exception as e:
            logger.warning(
                f"Level {self.current_level} failed: {e}. "
                f"Attempting fallback to level {self.current_level + 1}"
            )

            # Try next level
            self.current_level += 1
            if self.current_level <= 4:
                self._backend = _get_backend_by_level(self.current_level)
                await self._backend.initialize()
                return await self._backend.process_chunk(
                    chunk, previous_text, query_hint
                )

            # All levels exhausted
            raise

    async def reset(self):
        if self._backend:
            await self._backend.reset()

    def get_stats(self) -> dict:
        if self._backend:
            stats = self._backend.get_stats()
            stats["fallback_level"] = self.current_level
            stats["fallback_errors"] = self._errors
            return stats
        return {"fallback_level": self.current_level, "errors": self._errors}
