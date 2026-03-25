"""
PitchSide AI — AWS Configuration
Loads all environment variables and defines constants for each AWS service.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── AWS Cloud ─────────────────────────────────────────────────────────────────
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ── Amazon Nova Model IDs (Bedrock) ───────────────────────────────────────────
# Real-time spoken commentary translation
LIVE_AUDIO_MODEL = "amazon.nova-sonic-v2:0"

# Vision & multimodal frame analysis
VISION_MODEL = "amazon.nova-lite-v2:0"

# Deep tactical reasoning & research (1M token context)
RESEARCH_MODEL = "amazon.nova-pro-v2:0"

# ── Amazon OpenSearch (Vector Store) ──────────────────────────────────────────
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "pitchside-match-notes")
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

# ── Amazon DynamoDB (Match Events) ────────────────────────────────────────────
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "PitchSideMatchEvents")

# ── Bedrock AgentCore ─────────────────────────────────────────────────────────
AGENT_ID = os.getenv("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID", "")

# ── API Server ─────────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", 8080))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# ── Audio Config ───────────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE = 16000   # Hz
FRAME_SAMPLE_INTERVAL = 5   # seconds
