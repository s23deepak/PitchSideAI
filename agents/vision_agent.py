"""
Vision Agent — Amazon Nova 2 Lite
Analyzes sampled video frames to detect tactical patterns in soccer and cricket.
"""
import base64
import json
import logging
import boto3

from config import AWS_REGION, VISION_MODEL
from tools.dynamodb_tool import write_event

logger = logging.getLogger(__name__)

# Initialize Bedrock client
_bedrock = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)

SOCCER_PROMPT = """
You are an elite soccer tactical analyst. Analyze this video frame.

Identify ONE tactical label: [High Press | Low Block | Counter Attack | Build-Up Play | Set Piece | Normal Play]
Also identify formation and key observation.

Respond ONLY with valid JSON:
{"tactical_label": "...", "formation_home": "...", "formation_away": "...", "key_observation": "...", "confidence": 0.9}
"""

CRICKET_PROMPT = """
You are an elite cricket tactical analyst. Analyze this video frame.

Identify ONE tactical label: [Attacking Field | Defensive Field | Pace Attack | Spin Attack | Normal]

Respond ONLY with valid JSON:
{"tactical_label": "...", "key_observation": "...", "confidence": 0.9}
"""

class VisionAgent:
    """
    Analyzes base64 JPEG frames from a live broadcast feed using Amazon Nova 2 Lite.
    Results are written to DynamoDB for the live event feed.
    """

    def __init__(self, sport: str = "soccer"):
        self.sport = sport
        self.model_id = VISION_MODEL
        self.prompt = SOCCER_PROMPT if sport == "soccer" else CRICKET_PROMPT

    async def analyze_frame_b64(self, b64_str: str) -> dict:
        """
        Sends a JPEG frame to Nova 2 Lite for multimodal tactical analysis.
        """
        image_bytes = base64.b64decode(b64_str)
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": "jpeg",
                            "source": {"bytes": image_bytes}
                        }
                    },
                    {"text": self.prompt}
                ]
            }
        ]

        try:
            response = _bedrock.converse(
                modelId=self.model_id,
                messages=messages,
                inferenceConfig={"temperature": 0.1, "maxTokens": 300}
            )
            response_text = response['output']['message']['content'][0]['text']
            
            # Clean possible markdown formatting
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(response_text)
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            result = {
                "tactical_label": "Normal Play",
                "key_observation": "Analyzing play...",
                "confidence": 0.5,
            }

        # Write high-confidence detections to DynamoDB
        if result.get("confidence", 0) > 0.6:
            await write_event(
                "tactical_detection",
                result["key_observation"],
                {"label": result["tactical_label"], "confidence": result["confidence"]},
            )
            logger.info(f"[VisionAgent] {result['tactical_label']} — {result['key_observation']}")

        return result
