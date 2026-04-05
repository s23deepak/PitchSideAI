"""
Configuration package for PitchSide AI.

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

# ── Bedrock AgentCore (deployment-specific) ───────────────────────────────────
AGENT_ID       = os.getenv("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID", "")

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

# ── Runtime overrides (env wins over defaults.py) ─────────────────────────────
LLM_BACKEND    = os.getenv("LLM_BACKEND",    _d.LLM_BACKEND)
VISION_LLM_BACKEND = os.getenv("VISION_LLM_BACKEND", _d.VISION_LLM_BACKEND)
COMMENTARY_NOTES_LLM_BACKEND = os.getenv(
    "COMMENTARY_NOTES_LLM_BACKEND",
    _d.COMMENTARY_NOTES_LLM_BACKEND,
)
PORT           = int(os.getenv("PORT",        _d.PORT))
HOST           = os.getenv("HOST",            _d.HOST)
LOG_LEVEL      = os.getenv("LOG_LEVEL",       _d.LOG_LEVEL)
USE_JSON_LOGS  = os.getenv("USE_JSON_LOGS",   str(_d.USE_JSON_LOGS)).lower() == "true"
LOG_FILE       = os.getenv("LOG_FILE",        _d.LOG_FILE)

OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL",    _d.OLLAMA_BASE_URL)
OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL",       _d.OLLAMA_MODEL)
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", _d.OLLAMA_VISION_MODEL)
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", _d.OLLAMA_EMBED_MODEL)

OPENAI_MODEL       = os.getenv("OPENAI_MODEL",       _d.OPENAI_MODEL)
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", _d.OPENAI_EMBED_MODEL)

VLLM_BASE_URL    = os.getenv("VLLM_BASE_URL",    _d.VLLM_BASE_URL)
VLLM_MODEL       = os.getenv("VLLM_MODEL",       _d.VLLM_MODEL)
VLLM_VISION_MODEL = os.getenv("VLLM_VISION_MODEL", VLLM_MODEL or _d.VLLM_VISION_MODEL)
VLLM_EMBED_MODEL = os.getenv("VLLM_EMBED_MODEL", _d.VLLM_EMBED_MODEL)

RATE_LIMIT_RPM          = int(os.getenv("RATE_LIMIT_RPM",          _d.RATE_LIMIT_RPM))
RATE_LIMIT_BURST        = int(os.getenv("RATE_LIMIT_BURST",        _d.RATE_LIMIT_BURST))
MAX_CONCURRENT_TASKS    = int(os.getenv("MAX_CONCURRENT_TASKS",    _d.MAX_CONCURRENT_TASKS))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", _d.REQUEST_TIMEOUT_SECONDS))

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
