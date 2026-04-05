"""
config/defaults.py — Non-secret application defaults.

These values are safe to commit to version control.
Secrets and deployment-specific overrides belong in .env
"""

# ── Amazon Bedrock Model IDs ──────────────────────────────────────────────────
LIVE_AUDIO_MODEL = "amazon.nova-sonic-v2:0"
VISION_MODEL = "amazon.nova-lite-v2:0"
RESEARCH_MODEL = "amazon.nova-pro-v2:0"
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

# ── Amazon OpenSearch ─────────────────────────────────────────────────────────
OPENSEARCH_INDEX = "pitchside-match-notes"
OPENSEARCH_AUTH = "aws_sig4"

# ── DynamoDB ──────────────────────────────────────────────────────────────────
DYNAMODB_TABLE_NAME = "PitchSideMatchEvents"

# ── API Server ────────────────────────────────────────────────────────────────
PORT = 8080
HOST = "0.0.0.0"
LOG_LEVEL = "info"
USE_JSON_LOGS = True
LOG_FILE = "logs/pitchside.log"

# ── LLM Backend ───────────────────────────────────────────────────────────────
# Options: "bedrock", "ollama", "openai", "vllm"
LLM_BACKEND = "bedrock"
VISION_LLM_BACKEND = ""
COMMENTARY_NOTES_LLM_BACKEND = ""

# ── Ollama (Local) ────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:9b"
OLLAMA_VISION_MODEL = "llama3.2-vision"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_EMBED_MODEL = "text-embedding-3-small"

# ── vLLM (Self-Hosted) ────────────────────────────────────────────────────────
VLLM_BASE_URL = "http://localhost:8000"
VLLM_MODEL = ""
VLLM_VISION_MODEL = ""
VLLM_EMBED_MODEL = ""

# ── Rate Limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_RPM = 100
RATE_LIMIT_BURST = 10

# ── Concurrency ───────────────────────────────────────────────────────────────
MAX_CONCURRENT_TASKS = 20
REQUEST_TIMEOUT_SECONDS = 300

# ── Audio / Vision ────────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE = 16000   # Hz
FRAME_SAMPLE_INTERVAL = 5   # seconds
NATIVE_VIDEO_WINDOW_SECONDS = 3.0
NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS = 0.75
NATIVE_VIDEO_MAX_WINDOWS = 6

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
