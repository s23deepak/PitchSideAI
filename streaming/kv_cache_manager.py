"""
KV Cache Manager for streaming video inference.

Manages the lifecycle of key-value caches across video chunks:
- Attention sinks (stable tokens that anchor the KV cache)
- Sliding windows (recent vision + text tokens)
- Pruning and contiguous memory management

Based on StreamingVLM's KV cache strategy (MIT HAN Lab, arXiv 2510.09608).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch


@dataclass
class KVCacheConfig:
    """Configuration for KV cache management strategy."""
    window_size: int = 16              # Seconds of video to keep in visual window
    chunk_duration: int = 1            # Duration of each video chunk in seconds
    text_round: int = 16               # Rounds of text history to retain
    text_sink: int = 512               # Tokens kept as attention sink (stable prefix)
    text_sliding_window: int = 512     # Recent text tokens to keep
    max_total_tokens: int = 8192       # Hard cap on total KV cache size


@dataclass
class KVCacheState:
    """Running state of the KV cache across chunks."""
    past_key_values: Optional[Any] = None
    generated_ids: Optional[torch.Tensor] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    video_window_clips: List[Any] = field(default_factory=list)
    pixel_values_videos: List[torch.Tensor] = field(default_factory=list)
    chunk_index: int = 0
    total_processed_seconds: float = 0.0

    def get_cache_length(self) -> int:
        if self.past_key_values is None:
            return 0
        try:
            return self.past_key_values.get_seq_length()
        except Exception:
            return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "total_processed_seconds": self.total_processed_seconds,
            "cache_length": self.get_cache_length(),
            "window_clips": len(self.video_window_clips),
        }


class KVCacheManager:
    """
    Manages KV cache lifecycle for streaming video inference.

    Implements the three retention zones from StreamingVLM:
    1. Attention sinks: stable initial tokens (never pruned)
    2. Visual sliding window: recent N seconds of video tokens
    3. Text sliding window: recent M text tokens for conversation continuity
    """

    def __init__(self, config: Optional[KVCacheConfig] = None):
        self.config = config or KVCacheConfig()
        self.state = KVCacheState()

    def reset(self):
        """Reset all cache state for a new video session."""
        self.state = KVCacheState()

    @property
    def num_visual_windows(self) -> int:
        """Number of video chunks kept in the visual window."""
        return max(self.config.window_size // self.config.chunk_duration, 1)

    def should_prune_visual(self) -> bool:
        """Check if oldest visual chunk should be dropped."""
        return len(self.state.video_window_clips) > self.num_visual_windows

    def should_prune_text(self) -> bool:
        """Check if text history exceeds configured bounds."""
        return self.state.chunk_index >= self.config.text_round

    def prune_visual_window(self):
        """Drop oldest visual chunk from the window."""
        if self.state.video_window_clips:
            self.state.video_window_clips.pop(0)
        if self.state.pixel_values_videos:
            self.state.pixel_values_videos.pop(0)

    def add_visual_chunk(self, video_chunk: Any, pixel_values: torch.Tensor):
        """Add a new video chunk to the visual window."""
        self.state.video_window_clips.append(video_chunk)
        self.state.pixel_values_videos.append(pixel_values)
        if self.should_prune_visual():
            self.prune_visual_window()

    def add_conversation_turn(self, role: str, content: str):
        """Record a conversation turn for text window management."""
        self.state.conversation_history.append({"role": role, "content": content})

    def estimate_memory_bytes(self) -> int:
        """Rough estimate of KV cache memory usage in bytes."""
        cache_len = self.state.get_cache_length()
        if cache_len == 0:
            return 0
        # Qwen2.5-VL-3B: ~36 layers, ~16 heads, 128 head_dim
        # Rough: layers * 2 (K+V) * seq_len * head_dim * num_heads * 2 bytes (bf16)
        layers = 28  # 3B model
        num_kv_heads = 4  # GQA
        head_dim = 128
        bytes_per_element = 2  # bf16
        per_layer_cache = 2 * cache_len * head_dim * num_kv_heads * bytes_per_element
        return layers * per_layer_cache

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.state.to_dict(),
            "config": {
                "window_size": self.config.window_size,
                "chunk_duration": self.config.chunk_duration,
                "text_round": self.config.text_round,
            },
            "estimated_memory_mb": self.estimate_memory_bytes() / (1024 * 1024),
        }