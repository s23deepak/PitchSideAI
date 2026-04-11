"""
Vision Agent — Amazon Nova Lite
Real-time tactical pattern recognition for video frames.
Dynamically adapts to any sport type.
"""
import asyncio
import base64
import os
import tempfile
from typing import Dict, Any, List

import cv2

from agents.base import VisionAgent as BaseVisionAgent
from config.prompts import get_frame_prompt, get_video_clip_prompt, get_video_sequence_prompt
from tools.dynamodb_tool import write_event


class VisionAgent(BaseVisionAgent):
    """
    Analyzes video frames for tactical patterns using Nova Lite.
    Supports any sport type with dynamic prompts.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import (
            NATIVE_VIDEO_MAX_WINDOWS,
            NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS,
            NATIVE_VIDEO_WINDOW_SECONDS,
            VISION_MODEL,
        )
        super().__init__(model_id or VISION_MODEL, sport)
        self.native_video_window_seconds = max(float(NATIVE_VIDEO_WINDOW_SECONDS), 1.0)
        self.native_video_window_overlap_seconds = max(float(NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS), 0.0)
        self.native_video_max_windows = max(int(NATIVE_VIDEO_MAX_WINDOWS), 1)

    async def execute(self, image_data: bytes) -> Dict[str, Any]:
        """Alias for analyze_frame for orchestration compatibility."""
        return await self.analyze_frame(image_data)

    async def analyze_frame(self, image_data: bytes, match_session: str | None = None, temporal_context: dict | None = None) -> Dict[str, Any]:
        """
        Analyze a video frame for tactical patterns.

        Args:
            image_data: Raw JPEG frame bytes
            match_session: Optional match session key for DynamoDB scoping
            temporal_context: Optional dict with frame_index, total_frames, timestamp_ms for video sequence context

        Returns:
            Tactical analysis dict with confidence scores
        """
        self.log_event("frame_analysis_started", {
            "image_size": len(image_data)
        })

        # Get dynamic prompt based on sport (with temporal context when analyzing as part of a video)
        prompt = get_frame_prompt(self.sport, temporal_context=temporal_context)

        # Call model with image
        response_text = await self.call_bedrock(
            prompt,
            temperature=0.6,
            max_tokens=300,
            image_data=image_data,
            response_format="json"
        )

        # Parse JSON response
        try:
            result = await self.parse_json_response(response_text)
        except Exception as exc:
            self.logger.error("frame_analysis_parse_error", error=str(exc))
            # Return default result on parse error
            result = {
                "tactical_label": "Analysis Failed",
                "key_observation": "Could not analyze frame",
                "confidence": 0.0,
                "actionable_insight": "Retrying next frame"
            }

        # Index high-confidence detections
        confidence = result.get("confidence", 0.0)
        if confidence > 0.6:
            await self._log_detection(result, match_session=match_session)

        self.log_event("frame_analysis_completed", {
            "tactical_label": result.get("tactical_label"),
            "confidence": confidence
        })

        return result

    async def analyze_frame_b64(self, b64_str: str, match_session: str | None = None) -> Dict[str, Any]:
        """
        Analyze base64-encoded JPEG frame.

        Args:
            b64_str: Base64-encoded JPEG string

        Returns:
            Tactical analysis
        """
        try:
            image_bytes = base64.b64decode(b64_str)
            return await self.analyze_frame(image_bytes, match_session=match_session)
        except Exception as exc:
            self.logger.error("frame_decode_error", error=str(exc))
            raise

    async def analyze_frame_sequence(
        self,
        frames: List[bytes],
        interval: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple frames (e.g., key moments in sequence).

        Args:
            frames: List of frame bytes
            interval: Analyze every Nth frame (improves efficiency)

        Returns:
            List of analyses
        """
        self.log_event("sequence_analysis_started", {
            "frame_count": len(frames),
            "interval": interval
        })

        results = []

        for i, frame in enumerate(frames):
            if i % interval != 0:
                continue

            result = await self.analyze_frame(frame)
            result["frame_index"] = i
            results.append(result)

        self.log_event("sequence_analysis_completed", {
            "frames_analyzed": len(results)
        })

        return results

    async def analyze_video_sequence(
        self,
        frames: List[bytes],
        timestamps_ms: List[int] | None = None,
        match_session: str | None = None,
    ) -> Dict[str, Any]:
        """Analyze multiple sampled frames in parallel and summarize tactical changes."""
        timestamps_ms = timestamps_ms or [index * 1000 for index in range(len(frames))]
        clip_duration_ms = timestamps_ms[-1] if timestamps_ms else len(frames) * 1000

        # Parallel frame analysis with temporal context
        tasks = []
        for index, frame in enumerate(frames):
            ts = timestamps_ms[index] if index < len(timestamps_ms) else index * 1000
            temporal_context = {
                "frame_index": index,
                "total_frames": len(frames),
                "timestamp_ms": ts,
                "duration_ms": clip_duration_ms,
            }
            tasks.append(self.analyze_frame(frame, match_session=None, temporal_context=temporal_context))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses: List[Dict[str, Any]] = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error("frame_analysis_error", frame_index=index, error=str(result))
                continue
            result["frame_index"] = index
            result["timestamp_ms"] = timestamps_ms[index] if index < len(timestamps_ms) else index * 1000
            analyses.append(result)

        if not analyses:
            return {
                "tactical_label": "Analysis Failed",
                "key_observation": "All frames failed to analyze.",
                "confidence": 0.0,
                "actionable_insight": "Retry with a different video clip.",
                "timestamp_ms": None,
                "video_moments": [],
                "sequence_summary": "",
                "clip_start_timestamp_ms": timestamps_ms[0] if timestamps_ms else None,
                "clip_end_timestamp_ms": timestamps_ms[-1] if timestamps_ms else None,
                "native_video": False,
                "native_video_strategy": "sampled_frames",
            }

        sequence_summary = self._build_sequence_summary(analyses)
        temporal_summary = await self._summarize_sequence(sequence_summary)

        primary = self._select_primary_moment(analyses, temporal_summary)
        sequence_result = {
            "tactical_label": temporal_summary.get("primary_tactical_label") or primary.get("tactical_label") or "Video Sequence",
            "key_observation": temporal_summary.get("temporal_change") or primary.get("key_observation") or "Temporal change unavailable.",
            "confidence": temporal_summary.get("confidence", primary.get("confidence", 0.0)),
            "actionable_insight": temporal_summary.get("commentary_cue") or primary.get("actionable_insight") or "Track how the sequence evolves.",
            "timestamp_ms": temporal_summary.get("primary_timestamp_ms", primary.get("timestamp_ms")),
            "video_moments": analyses,
            "sequence_summary": sequence_summary,
            "clip_start_timestamp_ms": timestamps_ms[0] if timestamps_ms else None,
            "clip_end_timestamp_ms": timestamps_ms[-1] if timestamps_ms else None,
            "native_video": False,
            "native_video_strategy": "sampled_frames",
        }

        if sequence_result.get("confidence", 0.0) > 0.6:
            await write_event(
                "tactical_video_sequence",
                sequence_summary,
                {
                    "sport": self.sport,
                    "primary_tactical_label": sequence_result.get("tactical_label"),
                    "primary_timestamp_ms": sequence_result.get("timestamp_ms"),
                },
                match_session=match_session,
            )

        return sequence_result

    async def analyze_video_clip(
        self,
        video_data: bytes,
        video_format: str,
        match_session: str | None = None,
    ) -> Dict[str, Any]:
        """Analyze a native video clip through the active video-capable backend."""
        prompt = get_video_clip_prompt(self.sport)
        response_text = await self.call_bedrock(
            prompt,
            temperature=0.4,
            max_tokens=300,
            video_data=video_data,
            video_format=video_format,
            response_format="json",
        )

        try:
            summary = await self.parse_json_response(response_text)
        except Exception as exc:
            self.logger.error("video_clip_parse_error", error=str(exc))
            summary = {
                "temporal_change": "Native video analysis returned an unreadable response.",
                "primary_tactical_label": "Video Clip",
                "primary_timestamp_ms": 0,
                "confidence": 0.0,
                "commentary_cue": "Describe the tactical shape of the full clip.",
            }

        result = {
            "tactical_label": summary.get("primary_tactical_label") or "Video Clip",
            "key_observation": summary.get("temporal_change") or "Temporal change unavailable.",
            "confidence": summary.get("confidence", 0.0),
            "actionable_insight": summary.get("commentary_cue") or "Describe the clip as a continuous tactical sequence.",
            "timestamp_ms": summary.get("primary_timestamp_ms", 0),
            "native_video": True,
            "native_video_strategy": "full_clip",
            "video_format": video_format,
        }

        if result.get("confidence", 0.0) > 0.6:
            await write_event(
                "tactical_video_native",
                result.get("key_observation", ""),
                {
                    "label": result.get("tactical_label"),
                    "confidence": result.get("confidence"),
                    "sport": self.sport,
                    "video_format": video_format,
                },
                match_session=match_session,
            )

        return result

    async def analyze_video_sequence_b64(
        self,
        frames_b64: List[str],
        timestamps_ms: List[int] | None = None,
        match_session: str | None = None,
    ) -> Dict[str, Any]:
        """Decode multiple base64 frames and analyze the sequence."""
        try:
            frames = [base64.b64decode(frame_b64) for frame_b64 in frames_b64]
            return await self.analyze_video_sequence(frames, timestamps_ms=timestamps_ms, match_session=match_session)
        except Exception as exc:
            self.logger.error("video_sequence_decode_error", error=str(exc))
            raise

    async def analyze_chunked_frames(
        self,
        frames: List[bytes],
        timestamps_ms: List[int] | None = None,
        match_session: str | None = None,
        chunk_description: str | None = None,
    ) -> Dict[str, Any]:
        """
        Analyze a chunk of frames (e.g., 5-10 seconds of video) for live commentary.
        Similar to analyze_video_sequence but optimized for streaming chunks.

        Args:
            frames: List of frame bytes in the chunk
            timestamps_ms: Timestamps for each frame in milliseconds
            match_session: Optional match session key for DynamoDB
            chunk_description: Optional description of what this chunk represents

        Returns:
            Tactical analysis with chunk metadata
        """
        self.log_event("chunked_analysis_started", {
            "frame_count": len(frames),
            "chunk_description": chunk_description,
        })

        # Use existing video sequence analysis
        result = await self.analyze_video_sequence(
            frames,
            timestamps_ms=timestamps_ms,
            match_session=match_session,
        )

        # Add chunk-specific metadata
        result["chunk_description"] = chunk_description or f"Chunk of {len(frames)} frames"
        result["is_live_chunk"] = True

        self.log_event("chunked_analysis_completed", {
            "tactical_label": result.get("tactical_label"),
            "confidence": result.get("confidence", 0.0),
        })

        return result

    async def analyze_chunked_frames_b64(
        self,
        frames_b64: List[str],
        timestamps_ms: List[int] | None = None,
        match_session: str | None = None,
        chunk_description: str | None = None,
    ) -> Dict[str, Any]:
        """Decode and analyze a chunk of base64-encoded frames."""
        try:
            frames = [base64.b64decode(frame_b64) for frame_b64 in frames_b64]
            return await self.analyze_chunked_frames(
                frames,
                timestamps_ms=timestamps_ms,
                match_session=match_session,
                chunk_description=chunk_description,
            )
        except Exception as exc:
            self.logger.error("chunked_frames_decode_error", error=str(exc))
            raise

    async def analyze_video_clip_b64(
        self,
        video_b64: str,
        video_format: str,
        match_session: str | None = None,
    ) -> Dict[str, Any]:
        """Decode and analyze a native video clip."""
        try:
            video_bytes = base64.b64decode(video_b64)
            return await self.analyze_video_clip(video_bytes, video_format=video_format, match_session=match_session)
        except Exception as exc:
            self.logger.error("video_clip_decode_error", error=str(exc))
            raise

    async def analyze_video_clip_windowed(
        self,
        video_data: bytes,
        video_format: str,
        match_session: str | None = None,
    ) -> Dict[str, Any]:
        """Analyze a longer clip as overlapping native-video windows in parallel and merge the results."""
        windows = await asyncio.to_thread(self._build_native_video_windows, video_data, video_format)
        if len(windows) <= 1:
            return await self.analyze_video_clip(video_data, video_format=video_format, match_session=match_session)

        # Parallel per-window analysis
        tasks = [
            self.analyze_video_clip(
                window["video_bytes"],
                video_format=window["video_format"],
                match_session=None,
            )
            for window in windows
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses: List[Dict[str, Any]] = []
        for window, result in zip(windows, results):
            if isinstance(result, Exception):
                self.logger.error("window_analysis_error", window_index=window["window_index"], error=str(result))
                continue
            relative_timestamp = result.get("timestamp_ms") or 0
            result["timestamp_ms"] = window["clip_start_timestamp_ms"] + int(relative_timestamp)
            result["clip_start_timestamp_ms"] = window["clip_start_timestamp_ms"]
            result["clip_end_timestamp_ms"] = window["clip_end_timestamp_ms"]
            result["window_index"] = window["window_index"]
            analyses.append(result)

        if not analyses:
            raise ValueError("All video windows failed analysis")

        sequence_summary = self._build_sequence_summary(analyses)
        temporal_summary = await self._summarize_sequence(sequence_summary)
        primary = self._select_primary_moment(analyses, temporal_summary)
        clip_start_timestamp_ms = windows[0]["clip_start_timestamp_ms"]
        clip_end_timestamp_ms = windows[-1]["clip_end_timestamp_ms"]

        result = {
            "tactical_label": temporal_summary.get("primary_tactical_label") or primary.get("tactical_label") or "Video Sequence",
            "key_observation": temporal_summary.get("temporal_change") or primary.get("key_observation") or "Temporal change unavailable.",
            "confidence": temporal_summary.get("confidence", primary.get("confidence", 0.0)),
            "actionable_insight": temporal_summary.get("commentary_cue") or primary.get("actionable_insight") or "Describe the tactical changes across the clip windows.",
            "timestamp_ms": temporal_summary.get("primary_timestamp_ms", primary.get("timestamp_ms")),
            "video_moments": analyses,
            "sequence_summary": sequence_summary,
            "clip_start_timestamp_ms": clip_start_timestamp_ms,
            "clip_end_timestamp_ms": clip_end_timestamp_ms,
            "native_video": True,
            "native_video_strategy": "windowed",
            "video_window_count": len(analyses),
            "video_format": "mp4",
        }

        if result.get("confidence", 0.0) > 0.6:
            await write_event(
                "tactical_video_windowed",
                sequence_summary,
                {
                    "sport": self.sport,
                    "primary_tactical_label": result.get("tactical_label"),
                    "primary_timestamp_ms": result.get("timestamp_ms"),
                    "video_window_count": len(analyses),
                },
                match_session=match_session,
            )

        return result

    async def analyze_video_clip_windowed_b64(
        self,
        video_b64: str,
        video_format: str,
        match_session: str | None = None,
    ) -> Dict[str, Any]:
        """Decode and analyze a longer clip as overlapping native-video windows."""
        try:
            video_bytes = base64.b64decode(video_b64)
            return await self.analyze_video_clip_windowed(video_bytes, video_format=video_format, match_session=match_session)
        except Exception as exc:
            self.logger.error("video_clip_windowed_decode_error", error=str(exc))
            raise

    @staticmethod
    def _get_input_video_extension(video_format: str) -> str:
        normalized = (video_format or "mp4").strip().lower()
        if normalized == "three_gp":
            return "3gp"
        if normalized == "mpeg":
            return "mpg"
        return normalized

    def _build_native_video_windows(self, video_data: bytes, video_format: str) -> List[Dict[str, Any]]:
        """Split a longer clip into overlapping MP4 windows for native-video analysis."""
        window_ms = max(int(self.native_video_window_seconds * 1000), 1000)
        overlap_ms = min(
            max(int(self.native_video_window_overlap_seconds * 1000), 0),
            max(window_ms - 250, 0),
        )
        step_ms = max(window_ms - overlap_ms, 250)

        with tempfile.TemporaryDirectory(prefix="pitchai-video-") as temp_dir:
            input_path = os.path.join(
                temp_dir,
                f"input.{self._get_input_video_extension(video_format)}",
            )
            with open(input_path, "wb") as input_file:
                input_file.write(video_data)

            capture = cv2.VideoCapture(input_path)
            if not capture.isOpened():
                raise ValueError("Could not open uploaded video for native windowed analysis")

            try:
                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

                if fps <= 0 or frame_count <= 0 or frame_width <= 0 or frame_height <= 0:
                    raise ValueError("Uploaded video metadata is incomplete for native windowed analysis")

                duration_ms = max(int((frame_count / fps) * 1000), 1)
                window_starts_ms: List[int] = []
                start_ms = 0

                while len(window_starts_ms) < self.native_video_max_windows:
                    window_starts_ms.append(start_ms)
                    if start_ms + window_ms >= duration_ms:
                        break
                    start_ms += step_ms

                final_start_ms = max(duration_ms - window_ms, 0)
                if window_starts_ms:
                    if final_start_ms > window_starts_ms[-1]:
                        if len(window_starts_ms) < self.native_video_max_windows:
                            window_starts_ms.append(final_start_ms)
                        else:
                            window_starts_ms[-1] = final_start_ms
                else:
                    window_starts_ms = [0]

                window_starts_ms = sorted(set(window_starts_ms))
                windows: List[Dict[str, Any]] = []

                for window_index, clip_start_timestamp_ms in enumerate(window_starts_ms):
                    clip_end_timestamp_ms = min(clip_start_timestamp_ms + window_ms, duration_ms)
                    start_frame = int((clip_start_timestamp_ms / 1000) * fps)
                    end_frame = max(int((clip_end_timestamp_ms / 1000) * fps), start_frame + 1)
                    output_path = os.path.join(temp_dir, f"window-{window_index}.mp4")

                    writer = cv2.VideoWriter(
                        output_path,
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps,
                        (frame_width, frame_height),
                    )
                    if not writer.isOpened():
                        raise ValueError("OpenCV could not encode MP4 windows for native video analysis")

                    try:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                        current_frame = start_frame

                        while current_frame < end_frame:
                            ok, frame = capture.read()
                            if not ok:
                                break
                            writer.write(frame)
                            current_frame += 1
                    finally:
                        writer.release()

                    if not os.path.exists(output_path):
                        continue

                    with open(output_path, "rb") as window_file:
                        window_bytes = window_file.read()

                    if not window_bytes:
                        continue

                    windows.append(
                        {
                            "video_bytes": window_bytes,
                            "video_format": "mp4",
                            "clip_start_timestamp_ms": int((start_frame / fps) * 1000),
                            "clip_end_timestamp_ms": min(int((current_frame / fps) * 1000), duration_ms),
                            "window_index": window_index,
                        }
                    )

                if not windows:
                    raise ValueError("No native-video windows could be extracted from the uploaded clip")

                return windows
            finally:
                capture.release()

    def _build_sequence_summary(self, analyses: List[Dict[str, Any]]) -> str:
        """Build a timestamped sequence description from frame analyses."""
        parts = []
        for analysis in analyses:
            timestamp_ms = analysis.get("timestamp_ms", 0)
            total_seconds = int((timestamp_ms or 0) // 1000)
            minutes, seconds = divmod(total_seconds, 60)
            hours, minutes = divmod(minutes, 60)
            timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
            parts.append(
                f"{timestamp} - {analysis.get('tactical_label', 'Unknown')} "
                f"({analysis.get('confidence', 0.0):.2f}): {analysis.get('key_observation', 'No observation')}"
            )
        return "\n".join(parts)

    async def _summarize_sequence(self, sequence_summary: str) -> Dict[str, Any]:
        """Use the model to summarize the tactical evolution across a clip."""
        prompt = get_video_sequence_prompt(self.sport, sequence_summary)
        response_text = await self.call_bedrock(
            prompt,
            temperature=0.4,
            max_tokens=512,
            response_format="json",
        )
        try:
            return await self.parse_json_response(response_text)
        except Exception as exc:
            self.logger.error("video_sequence_parse_error", error=str(exc))
            return {
                "temporal_change": "The clip shows tactical movement across several moments, but the summary could not be fully parsed.",
                "primary_tactical_label": None,
                "primary_timestamp_ms": 0,
                "confidence": 0.0,
                "commentary_cue": "Describe how the clip evolves across time rather than as a single still image.",
            }

    def _select_primary_moment(
        self,
        analyses: List[Dict[str, Any]],
        temporal_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Choose the strongest moment in the clip for UI emphasis."""
        target_timestamp = temporal_summary.get("primary_timestamp_ms")
        for analysis in analyses:
            if analysis.get("timestamp_ms") == target_timestamp:
                return analysis
        return max(analyses, key=lambda item: item.get("confidence", 0.0), default={})

    async def _log_detection(self, result: Dict[str, Any], match_session: str | None = None) -> None:
        """
        Log high-confidence tactical detection to DynamoDB.

        Args:
            result: Analysis result
        """
        try:
            from decimal import Decimal
            await write_event(
                "tactical_detection",
                result.get("key_observation", ""),
                {
                    "label": result.get("tactical_label"),
                    "confidence": Decimal(str(result.get("confidence", 0.0))),
                    "sport": self.sport,
                    "actionable_insight": result.get("actionable_insight")
                },
                match_session=match_session,
            )
            self.logger.info(
                "tactical_detection_logged",
                label=result.get("tactical_label"),
                sport=self.sport
            )
        except Exception as exc:
            self.logger.error("detection_logging_failed", error=str(exc))
