"""
Frame Buffer for managing incoming video frames and forming chunks.

Handles:
- Adaptive frame sampling based on FPS detection
- Chunk formation at configurable intervals
- Frame quality validation
- Timestamp tracking for GameState synchronization
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class FrameBufferConfig:
    """Configuration for frame buffering and chunk formation."""
    target_fps: float = 8.0            # Target frames per second for model
    chunk_interval_seconds: float = 5.0  # How often to form a chunk (seconds of video)
    max_chunk_frames: int = 24         # Max frames per chunk (at target_fps * chunk_interval)
    min_chunk_frames: int = 4          # Min frames before processing a chunk
    frame_quality_threshold: float = 0.3  # Min acceptable frame quality
    buffer_high_watermark: int = 60    # Drop frames if buffer exceeds this


@dataclass
class FrameSample:
    """A single sampled frame with metadata."""
    data: bytes                        # JPEG frame bytes
    timestamp_ms: int                  # Absolute timestamp in ms
    frame_index: int                   # Sequential frame index
    quality_score: float = 1.0         # Quality score (0-1)
    keyframe: bool = False             # Whether this is a keyframe/I-frame


@dataclass
class VideoChunk:
    """A chunk of frames ready for model processing."""
    frames: List[FrameSample]
    start_timestamp_ms: int
    end_timestamp_ms: int
    duration_seconds: float
    chunk_index: int


class FrameBuffer:
    """
    Buffers incoming video frames and forms chunks for the streaming model.

    Features:
    - Intelligent frame sampling (prefer keyframes, avoid redundant frames)
    - Adaptive chunk sizing based on motion detection
    - Quality-based frame selection
    - Overflow protection
    """

    def __init__(self, config: Optional[FrameBufferConfig] = None):
        self.config = config or FrameBufferConfig()
        self._buffer: deque[FrameSample] = deque()
        self._frame_index: int = 0
        self._chunk_index: int = 0
        self._last_chunk_time: float = 0.0
        self._frame_times: deque[float] = deque(maxlen=30)
        self._actual_fps: float = 0.0

    def reset(self):
        """Reset buffer state for a new video session."""
        self._buffer.clear()
        self._frame_index = 0
        self._chunk_index = 0
        self._last_chunk_time = 0.0
        self._frame_times.clear()
        self._actual_fps = 0.0

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    @property
    def is_ready(self) -> bool:
        """Check if buffer has enough frames to form a chunk."""
        return len(self._buffer) >= self.config.min_chunk_frames

    def add_frame(self, data: bytes, timestamp_ms: int,
                  keyframe: bool = False, quality_score: float = 1.0) -> Optional[VideoChunk]:
        """
        Add a frame to the buffer. Returns a VideoChunk if one is ready.

        Args:
            data: JPEG frame bytes
            timestamp_ms: Absolute timestamp in milliseconds
            keyframe: Whether this is a keyframe/I-frame
            quality_score: Frame quality score (0-1)

        Returns:
            VideoChunk if buffer is ready for processing, None otherwise
        """
        # Quality filtering
        if quality_score < self.config.frame_quality_threshold:
            return None

        now = time.monotonic()
        self._frame_times.append(now)
        if len(self._frame_times) > 1:
            interval = self._frame_times[-1] - self._frame_times[0]
            self._actual_fps = (len(self._frame_times) - 1) / max(interval, 0.001)

        sample = FrameSample(
            data=data,
            timestamp_ms=timestamp_ms,
            frame_index=self._frame_index,
            quality_score=quality_score,
            keyframe=keyframe,
        )
        self._frame_index += 1
        self._buffer.append(sample)

        # Overflow protection: drop oldest non-keyframe
        while len(self._buffer) > self.config.buffer_high_watermark:
            dropped = False
            for i, f in enumerate(self._buffer):
                if not f.keyframe:
                    del self._buffer[i]
                    dropped = True
                    break
            if not dropped:
                self._buffer.popleft()

        # Check if chunk is ready
        return self._try_form_chunk()

    def _try_form_chunk(self) -> Optional[VideoChunk]:
        """Try to form a chunk from the buffer."""
        if len(self._buffer) < self.config.min_chunk_frames:
            return None

        # Check if enough real time has elapsed since last chunk
        now = time.monotonic()
        time_since_last = now - self._last_chunk_time

        # Form chunk if we have enough frames OR enough time has passed
        frames_ready = len(self._buffer) >= self.config.max_chunk_frames
        time_ready = time_since_last >= self.config.chunk_interval_seconds and self.is_ready

        if not (frames_ready or time_ready):
            return None

        # Take frames for this chunk
        num_frames = min(len(self._buffer), self.config.max_chunk_frames)
        chunk_frames = [self._buffer.popleft() for _ in range(num_frames)]

        if not chunk_frames:
            return None

        self._last_chunk_time = now
        chunk = VideoChunk(
            frames=chunk_frames,
            start_timestamp_ms=chunk_frames[0].timestamp_ms,
            end_timestamp_ms=chunk_frames[-1].timestamp_ms,
            duration_seconds=(chunk_frames[-1].timestamp_ms - chunk_frames[0].timestamp_ms) / 1000.0,
            chunk_index=self._chunk_index,
        )
        self._chunk_index += 1
        return chunk

    def force_chunk(self) -> Optional[VideoChunk]:
        """Force formation of a chunk from any buffered frames."""
        if not self._buffer:
            return None
        frames = list(self._buffer)
        self._buffer.clear()
        chunk = VideoChunk(
            frames=frames,
            start_timestamp_ms=frames[0].timestamp_ms,
            end_timestamp_ms=frames[-1].timestamp_ms,
            duration_seconds=(frames[-1].timestamp_ms - frames[0].timestamp_ms) / 1000.0,
            chunk_index=self._chunk_index,
        )
        self._chunk_index += 1
        return chunk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "buffer_size": len(self._buffer),
            "chunk_index": self._chunk_index,
            "actual_fps": round(self._actual_fps, 1),
            "is_ready": self.is_ready,
        }