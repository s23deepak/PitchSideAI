"""
Configuration package for PitchSideAI.

Non-secret defaults live in config/defaults.py (safe to commit).
Secrets and deployment overrides come from .env (never commit).
"""
import os
from dotenv import load_dotenv
from config.defaults import *  # noqa: F401, F403

load_dotenv()

# ── AWS Credentials (secrets) ─────────────────────────────────────────────────
import config.defaults as _d  # noqa: E402

AWS_REGION          = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID   = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ── Amazon OpenSearch (deployment-specific) ───────────────────────────────────
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")

# ── DynamoDB region override ──────────────────────────────────────────────────
DYNAMODB_REGION = os.getenv("DYNAMODB_REGION", AWS_REGION)

# ── Redis (deployment-specific) ───────────────────────────────────────────────
REDIS_HOST     = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB       = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# ── OpenAI API key (secret) ───────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WAFER_API_KEY = os.getenv("WAFER_API_KEY", "")
BRIGHTDATA_MCP_TOKEN = os.getenv("BRIGHTDATA_MCP_TOKEN", "")

# ── Runtime overrides (env wins over defaults.py) ─────────────────────────────
LLM_BACKEND    = os.getenv("LLM_BACKEND",    _d.LLM_BACKEND)
VISION_LLM_BACKEND = os.getenv("VISION_LLM_BACKEND", _d.VISION_LLM_BACKEND)
COMMENTARY_NOTES_LLM_BACKEND = os.getenv(
    "COMMENTARY_NOTES_LLM_BACKEND",
    _d.COMMENTARY_NOTES_LLM_BACKEND,
)
STREAMING_BACKEND = os.getenv("STREAMING_BACKEND", _d.STREAMING_BACKEND)
PORT           = int(os.getenv("PORT",        _d.PORT))
HOST           = os.getenv("HOST",            _d.HOST)
LOG_LEVEL      = os.getenv("LOG_LEVEL",       _d.LOG_LEVEL)
USE_JSON_LOGS  = os.getenv("USE_JSON_LOGS",   str(_d.USE_JSON_LOGS)).lower() == "true"
LOG_FILE       = os.getenv("LOG_FILE",        _d.LOG_FILE)

OPENAI_MODEL       = os.getenv("OPENAI_MODEL",       _d.OPENAI_MODEL)
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", _d.OPENAI_EMBED_MODEL)
WAFER_BASE_URL = os.getenv("WAFER_BASE_URL", _d.WAFER_BASE_URL).rstrip("/")
WAFER_MODEL = os.getenv("WAFER_MODEL", _d.WAFER_MODEL)
BRIGHTDATA_MCP_BASE_URL = os.getenv("BRIGHTDATA_MCP_BASE_URL", _d.BRIGHTDATA_MCP_BASE_URL).rstrip("/")
BRIGHTDATA_MCP_GROUPS = os.getenv("BRIGHTDATA_MCP_GROUPS", _d.BRIGHTDATA_MCP_GROUPS)
VLLM_BASE_URL    = os.getenv("VLLM_BASE_URL",    _d.VLLM_BASE_URL)
VLLM_MODEL       = os.getenv("VLLM_MODEL",       _d.VLLM_MODEL)
VLLM_VISION_MODEL = os.getenv("VLLM_VISION_MODEL", VLLM_MODEL or _d.VLLM_VISION_MODEL)
VLLM_EMBED_MODEL = os.getenv("VLLM_EMBED_MODEL", _d.VLLM_EMBED_MODEL)

AUDIO_VLLM_BASE_URL = os.getenv("AUDIO_VLLM_BASE_URL", os.getenv("VLLM_BASE_URL", _d.AUDIO_VLLM_BASE_URL))
AUDIO_MODEL         = os.getenv("AUDIO_MODEL",         _d.AUDIO_MODEL)

RATE_LIMIT_RPM          = int(os.getenv("RATE_LIMIT_RPM",          _d.RATE_LIMIT_RPM))
RATE_LIMIT_BURST        = int(os.getenv("RATE_LIMIT_BURST",        _d.RATE_LIMIT_BURST))
MAX_CONCURRENT_TASKS    = int(os.getenv("MAX_CONCURRENT_TASKS",    _d.MAX_CONCURRENT_TASKS))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", _d.REQUEST_TIMEOUT_SECONDS))
COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY = int(
    os.getenv("COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY", _d.COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY)
)

RETRIEVAL_DEBUG_DUMP = os.getenv("RETRIEVAL_DEBUG_DUMP", str(_d.RETRIEVAL_DEBUG_DUMP)).lower() == "true"
LLM_DEBUG_DUMP = os.getenv("LLM_DEBUG_DUMP", str(_d.LLM_DEBUG_DUMP)).lower() == "true"
RETRIEVAL_DEBUG_DIR = os.getenv("RETRIEVAL_DEBUG_DIR", _d.RETRIEVAL_DEBUG_DIR)
RETRIEVAL_DEBUG_INCLUDE_RAW = (
    os.getenv("RETRIEVAL_DEBUG_INCLUDE_RAW", str(_d.RETRIEVAL_DEBUG_INCLUDE_RAW)).lower() == "true"
)
RETRIEVAL_DEBUG_MAX_STRING_CHARS = int(
    os.getenv("RETRIEVAL_DEBUG_MAX_STRING_CHARS", _d.RETRIEVAL_DEBUG_MAX_STRING_CHARS)
)

AUDIO_SAMPLE_RATE     = int(os.getenv("AUDIO_SAMPLE_RATE",     _d.AUDIO_SAMPLE_RATE))
FRAME_SAMPLE_INTERVAL = int(os.getenv("FRAME_SAMPLE_INTERVAL", _d.FRAME_SAMPLE_INTERVAL))
NATIVE_VIDEO_WINDOW_SECONDS = float(os.getenv("NATIVE_VIDEO_WINDOW_SECONDS", _d.NATIVE_VIDEO_WINDOW_SECONDS))
NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS = float(
    os.getenv("NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS", _d.NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS)
)
NATIVE_VIDEO_MAX_WINDOWS = int(os.getenv("NATIVE_VIDEO_MAX_WINDOWS", _d.NATIVE_VIDEO_MAX_WINDOWS))

_cors_env    = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = _cors_env.split(",") if _cors_env else _d.CORS_ORIGINS

# ── Sports & Prompts ──────────────────────────────────────────────────────────
from config.sports import (  # noqa: E402
    SportType,
    SportConfig,
    get_sport_config,
    get_tactical_labels,
    get_research_topics,
    get_team_positions,
)
from config.prompts import (  # noqa: E402
    SystemPrompts,
    get_research_prompt,
    get_query_prompt,
    get_frame_prompt,
    get_commentary_prompt,
    get_tactical_prompt,
)
