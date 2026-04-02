"""
Production configuration for PitchSide AI.
Load environment-specific settings and secrets.
"""
import os
from typing import Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()


# ── Environment ──────────────────────────────────────────────────────────────

ENV = os.getenv("ENVIRONMENT", "development")
DEBUG = ENV == "development"


# ── AWS Configuration ────────────────────────────────────────────────────────

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


# ── API Server Configuration ────────────────────────────────────────────────

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info" if not DEBUG else "debug")


# ── Amazon Nova Models ──────────────────────────────────────────────────────

LIVE_AUDIO_MODEL = os.getenv("LIVE_AUDIO_MODEL", "amazon.nova-sonic-v2:0")
VISION_MODEL = os.getenv("VISION_MODEL", "amazon.nova-lite-v2:0")
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "amazon.nova-pro-v2:0")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")


# ── OpenSearch RAG Configuration ───────────────────────────────────────────

OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "pitchside-match-notes")
OPENSEARCH_AUTH = os.getenv("OPENSEARCH_AUTH", "aws_sig4")  # or "basic"


# ── DynamoDB Configuration ────────────────────────────────────────────────

DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "PitchSideMatchEvents")
DYNAMODB_REGION = os.getenv("DYNAMODB_REGION", AWS_REGION)


# ── Bedrock AgentCore ────────────────────────────────────────────────────

AGENT_ID = os.getenv("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID", "")


# ── Redis Configuration ──────────────────────────────────────────────────

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)


# ── Rate Limiting ────────────────────────────────────────────────────────

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "100"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))


# ── Concurrency Configuration ────────────────────────────────────────────

MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "20"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))


# ── Audio Configuration ─────────────────────────────────────────────────

AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
FRAME_SAMPLE_INTERVAL = int(os.getenv("FRAME_SAMPLE_INTERVAL", "5"))


# ── CORS Configuration ──────────────────────────────────────────────────

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")


# ── Monitoring & Logging ────────────────────────────────────────────────

LOG_FILE = os.getenv("LOG_FILE", "logs/pitchside.log" if not DEBUG else None)
USE_JSON_LOGS = os.getenv("USE_JSON_LOGS", "true").lower() == "true"


# Configuration validation
def validate_config() -> None:
    """Validate critical configuration."""
    required_aws_vars = ["AWS_REGION"]
    missing = [v for v in required_aws_vars if not os.getenv(v)]

    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")

    if not OPENSEARCH_ENDPOINT:
        print("⚠️  Warning: OPENSEARCH_ENDPOINT not configured. RAG will use local storage.")


if __name__ == "__main__":
    validate_config()
    print(" PitchSide AI Configuration Loaded")
    print(f"Environment: {ENV}")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"Max Concurrent Tasks: {MAX_CONCURRENT_TASKS}")
