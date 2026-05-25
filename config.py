"""
config.py — Runtime configuration for PitchSideAI.

Loads non-secret defaults from config/defaults.py, then overlays
secrets and deployment-specific values from .env (via python-dotenv).
"""
import os
from dotenv import load_dotenv
import config.defaults as _d
from config.defaults import *  # noqa: F401, F403 — import all defaults first

load_dotenv()  # Secrets/overrides in .env win over module-level defaults



# ── Amazon OpenSearch (deployment-specific) ───────────────────────────────────
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "")

# ── DynamoDB region override (deployment-specific) ────────────────────────────
DYNAMODB_REGION = os.getenv("DYNAMODB_REGION", AWS_REGION)

# ── Redis (deployment-specific) ───────────────────────────────────────────────
REDIS_HOST     = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB       = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_URL      = os.getenv("REDIS_URL", _d.REDIS_URL)
DATABASE_URL   = os.getenv("DATABASE_URL", _d.DATABASE_URL)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", _d.CELERY_BROKER_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", _d.CELERY_RESULT_BACKEND)

# ── OpenAI API key (secret) ───────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WAFER_API_KEY = os.getenv("WAFER_API_KEY", "")
BRIGHTDATA_MCP_TOKEN = os.getenv("BRIGHTDATA_MCP_TOKEN", "")

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

OPENAI_MODEL      = os.getenv("OPENAI_MODEL",      _d.OPENAI_MODEL)
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
AUDIO_API_TYPE      = os.getenv("AUDIO_API_TYPE",      _d.AUDIO_API_TYPE)

RATE_LIMIT_RPM         = int(os.getenv("RATE_LIMIT_RPM",         _d.RATE_LIMIT_RPM))
RATE_LIMIT_BURST       = int(os.getenv("RATE_LIMIT_BURST",       _d.RATE_LIMIT_BURST))
MAX_CONCURRENT_TASKS   = int(os.getenv("MAX_CONCURRENT_TASKS",   _d.MAX_CONCURRENT_TASKS))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", _d.REQUEST_TIMEOUT_SECONDS))
COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY = int(
	os.getenv("COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY", _d.COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY)
)

AUDIO_SAMPLE_RATE    = int(os.getenv("AUDIO_SAMPLE_RATE",    _d.AUDIO_SAMPLE_RATE))
FRAME_SAMPLE_INTERVAL = int(os.getenv("FRAME_SAMPLE_INTERVAL", _d.FRAME_SAMPLE_INTERVAL))
NATIVE_VIDEO_WINDOW_SECONDS = float(os.getenv("NATIVE_VIDEO_WINDOW_SECONDS", _d.NATIVE_VIDEO_WINDOW_SECONDS))
NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS = float(
	os.getenv("NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS", _d.NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS)
)
NATIVE_VIDEO_MAX_WINDOWS = int(os.getenv("NATIVE_VIDEO_MAX_WINDOWS", _d.NATIVE_VIDEO_MAX_WINDOWS))

_cors_env = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = _cors_env.split(",") if _cors_env else _d.CORS_ORIGINS
