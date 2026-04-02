"""
Vision Agent — Amazon Nova Lite
Real-time tactical pattern recognition for video frames.
Dynamically adapts to any sport type.
"""
import base64
from typing import Dict, Any, List

from agents.base import VisionAgent as BaseVisionAgent
from config.prompts import get_frame_prompt
from tools.dynamodb_tool import write_event


class VisionAgent(BaseVisionAgent):
    """
    Analyzes video frames for tactical patterns using Nova Lite.
    Supports any sport type with dynamic prompts.
    """

    def __init__(self, model_id: str = None, sport: str = "soccer"):
        from config import VISION_MODEL
        super().__init__(model_id or VISION_MODEL, sport)

    async def execute(self, image_data: bytes) -> Dict[str, Any]:
        """Alias for analyze_frame for orchestration compatibility."""
        return await self.analyze_frame(image_data)

    async def analyze_frame(self, image_data: bytes) -> Dict[str, Any]:
        """
        Analyze a video frame for tactical patterns.

        Args:
            image_data: Raw JPEG frame bytes

        Returns:
            Tactical analysis dict with confidence scores
        """
        self.log_event("frame_analysis_started", {
            "image_size": len(image_data)
        })

        # Get dynamic prompt based on sport
        prompt = get_frame_prompt(self.sport)

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
            await self._log_detection(result)

        self.log_event("frame_analysis_completed", {
            "tactical_label": result.get("tactical_label"),
            "confidence": confidence
        })

        return result

    async def analyze_frame_b64(self, b64_str: str) -> Dict[str, Any]:
        """
        Analyze base64-encoded JPEG frame.

        Args:
            b64_str: Base64-encoded JPEG string

        Returns:
            Tactical analysis
        """
        try:
            image_bytes = base64.b64decode(b64_str)
            return await self.analyze_frame(image_bytes)
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

    async def _log_detection(self, result: Dict[str, Any]) -> None:
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
                }
            )
            self.logger.info(
                "tactical_detection_logged",
                label=result.get("tactical_label"),
                sport=self.sport
            )
        except Exception as exc:
            self.logger.error("detection_logging_failed", error=str(exc))
