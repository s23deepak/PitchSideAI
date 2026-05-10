"""
config/defaults.py — Non-secret application defaults.

These values are safe to commit to version control.
Secrets and deployment-specific overrides belong in .env
"""

# ── Model ID Defaults (override via .env or per-backend config) ───────────────
# These are used only when no backend-specific model is configured.
LIVE_AUDIO_MODEL = ""        # Unused: audio goes through Qwen2-Audio / AUDIO_VLLM_BASE_URL
VISION_MODEL = ""             # Override with VLLM_VISION_MODEL
RESEARCH_MODEL = ""           # Override with VLLM_MODEL / OPENAI_MODEL
EMBEDDING_MODEL = ""          # Override with VLLM_EMBED_MODEL

# ── Search / Vector Store ─────────────────────────────────────────────────────
OPENSEARCH_INDEX = "pitchside-match-notes"
OPENSEARCH_AUTH = "none"   # Options: "none", "basic", "aws_sig4"

# ── Event Store ───────────────────────────────────────────────────────────────
DYNAMODB_TABLE_NAME = "PitchSideMatchEvents"

# ── API Server ────────────────────────────────────────────────────────────────
PORT = 8080
HOST = "0.0.0.0"
LOG_LEVEL = "info"
USE_JSON_LOGS = True
LOG_FILE = "logs/pitchside.log"

# ── LLM Backend ───────────────────────────────────────────────────────────────
# Options: "openai", "vllm"
# Streaming/video pipeline uses: "streaming_vlm", "vllm", "auto"
LLM_BACKEND = "vllm"
VISION_LLM_BACKEND = "vllm"
COMMENTARY_NOTES_LLM_BACKEND = "vllm"
STREAMING_BACKEND = "vllm"  # Default video/streaming inference backend
# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_EMBED_MODEL = "text-embedding-3-small"

# ── vLLM (Self-Hosted, OpenAI-compatible) ────────────────────────────────────
# Point VLLM_BASE_URL at your running vLLM server
VLLM_BASE_URL = "http://localhost:8001"
VLLM_MODEL = ""
VLLM_VISION_MODEL = ""
VLLM_EMBED_MODEL = ""

# ── Qwen2-Audio / Whisper ASR (separate vLLM instance) ───────────────────────
# AUDIO_API_TYPE controls which endpoint format _transcribe_audio uses:
#   "whisper" → POST /v1/audio/transcriptions (multipart, standard Whisper API)
#   "chat"    → POST /v1/chat/completions     (multimodal, Qwen2-Audio format)
#
# Recommended local models by VRAM budget:
#   openai/whisper-large-v3-turbo   ~2 GB  (best quality/size ratio)  ← default
#   distil-whisper/distil-large-v3  ~1.5GB (fastest)
#   openai/whisper-small            ~0.5GB (minimum viable)
#   Qwen/Qwen2-Audio-7B-Instruct    ~14GB  (most capable, needs A100)
AUDIO_VLLM_BASE_URL = "http://localhost:8001"
AUDIO_MODEL         = "openai/whisper-large-v3-turbo"
AUDIO_API_TYPE      = "whisper"   # "whisper" | "chat"

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
