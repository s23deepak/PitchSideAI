"""
config.py — Runtime configuration for PitchSide AI.

Loads non-secret defaults from config/defaults.py, then overlays
secrets and deployment-specific values from .env (via python-dotenv).
"""
import os
from dotenv import load_dotenv
from config.defaults import *  # noqa: F401, F403 — import all defaults first

load_dotenv()  # Secrets/overrides in .env win over module-level defaults

# ── AWS Credentials (secrets — must come from .env / environment) ─────────────
AWS_REGION          = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID   = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ── Bedrock AgentCore (deployment-specific) ───────────────────────────────────
AGENT_ID       = os.getenv("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID", "")

# ── Amazon OpenSearch (deployment-specific) ───────────────────────────────────
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")

# ── DynamoDB region override (deployment-specific) ────────────────────────────
DYNAMODB_REGION = os.getenv("DYNAMODB_REGION", AWS_REGION)

# ── Redis (deployment-specific) ───────────────────────────────────────────────
REDIS_HOST     = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB       = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# ── OpenAI API key (secret) ───────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Runtime overrides (allow .env to override defaults.py values) ─────────────
import config.defaults as _d  # noqa: E402

LLM_BACKEND    = os.getenv("LLM_BACKEND",    _d.LLM_BACKEND)
PORT           = int(os.getenv("PORT",        _d.PORT))
HOST           = os.getenv("HOST",            _d.HOST)
LOG_LEVEL      = os.getenv("LOG_LEVEL",       _d.LOG_LEVEL)
USE_JSON_LOGS  = os.getenv("USE_JSON_LOGS",   str(_d.USE_JSON_LOGS)).lower() == "true"
LOG_FILE       = os.getenv("LOG_FILE",        _d.LOG_FILE)

OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL",   _d.OLLAMA_BASE_URL)
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL",      _d.OLLAMA_MODEL)
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", _d.OLLAMA_EMBED_MODEL)

OPENAI_MODEL      = os.getenv("OPENAI_MODEL",      _d.OPENAI_MODEL)
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", _d.OPENAI_EMBED_MODEL)

VLLM_BASE_URL    = os.getenv("VLLM_BASE_URL",    _d.VLLM_BASE_URL)
VLLM_MODEL       = os.getenv("VLLM_MODEL",       _d.VLLM_MODEL)
VLLM_EMBED_MODEL = os.getenv("VLLM_EMBED_MODEL", _d.VLLM_EMBED_MODEL)

RATE_LIMIT_RPM         = int(os.getenv("RATE_LIMIT_RPM",         _d.RATE_LIMIT_RPM))
RATE_LIMIT_BURST       = int(os.getenv("RATE_LIMIT_BURST",       _d.RATE_LIMIT_BURST))
MAX_CONCURRENT_TASKS   = int(os.getenv("MAX_CONCURRENT_TASKS",   _d.MAX_CONCURRENT_TASKS))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", _d.REQUEST_TIMEOUT_SECONDS))

AUDIO_SAMPLE_RATE    = int(os.getenv("AUDIO_SAMPLE_RATE",    _d.AUDIO_SAMPLE_RATE))
FRAME_SAMPLE_INTERVAL = int(os.getenv("FRAME_SAMPLE_INTERVAL", _d.FRAME_SAMPLE_INTERVAL))

_cors_env = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = _cors_env.split(",") if _cors_env else _d.CORS_ORIGINS
