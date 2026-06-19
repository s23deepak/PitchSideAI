"""
config/settings.py — Pydantic-settings loader for all runtime configuration.

Non-secret defaults live in config/defaults.py (safe to commit).
Secrets and deployment overrides come from .env (never commit).
"""
from __future__ import annotations

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM Backend ──
    LLM_BACKEND: str = Field(default="vllm", description="openai | anthropic | vllm | deepseek | wafer")
    VISION_LLM_BACKEND: str = Field(default="vllm", description="Backend for vision/video agents")
    COMMENTARY_NOTES_LLM_BACKEND: str = Field(default="vllm", description="Backend for commentary notes agents")
    STREAMING_BACKEND: str = Field(default="vllm")

    # ── API Keys ──
    OPENAI_API_KEY: str = Field(default="")
    TAVILY_API_KEY: str = Field(default="")
    EXA_API_KEY: str = Field(default="")
    FOOTBALL_DATA_API_KEY: str = Field(default="")
    FIRECRAWL_API_KEY: str = Field(default="")
    BRAVE_SEARCH_API_KEY: str = Field(default="")
    BRIGHTDATA_MCP_TOKEN: str = Field(default="")
    ANTHROPIC_API_KEY: str = Field(default="")
    DEEPSEEK_API_KEY: str = Field(default="")
    FORVO_API_KEY: str = Field(default="")
    YOUGLISH_API_KEY: str = Field(default="")
    SPORTMONKS_API_TOKEN: str = Field(default="")
    ONEVSONE_EMAIL: str = Field(default="")
    ONEVSONE_PASSWORD: str = Field(default="")

    # ── vLLM / Self-Hosted ──
    VLLM_BASE_URL: str = Field(default="http://localhost:8001")
    VLLM_MODEL: str = Field(default="")
    VLLM_VISION_MODEL: str = Field(default="")
    VLLM_EMBED_MODEL: str = Field(default="")

    # ── WAFER ──
    WAFER_BASE_URL: str = Field(default="https://pass.wafer.ai/")
    WAFER_MODEL: str = Field(default="MiniMax-M3")
    WAFER_API_KEY: str = Field(default="")

    # ── OpenAI Model ──
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    OPENAI_EMBED_MODEL: str = Field(default="text-embedding-3-small")

    # ── Audio ──
    AUDIO_VLLM_BASE_URL: str = Field(default="http://localhost:8001")
    AUDIO_MODEL: str = Field(default="openai/whisper-large-v3-turbo")
    AUDIO_API_TYPE: str = Field(default="whisper")
    AUDIO_SAMPLE_RATE: int = Field(default=16000)

    # ── Feature Flags ──
    RETRIEVAL_AUDIT_ENABLED: bool = Field(default=True)
    AUDIT_LOG_LEVEL: str = Field(default="verbose", description="verbose | summary | silent")
    SOURCE_HEALTH_TRACKING: bool = Field(default=True)
    BRIGHTDATA_MCP_ENABLED: bool = Field(default=False)
    OPEN_METEO_ENABLED: bool = Field(default=True)
    PARALLEL_RACE_ENABLED: bool = Field(default=True)
    CACHE_BACKEND: str = Field(default="memory", description="memory | redis")

    # ── Thresholds ──
    EVIDENCE_GAP_THRESHOLD: int = Field(default=4)
    MAX_RETRIES_PER_SOURCE: int = Field(default=2)
    MAX_SOURCES_PER_FETCH: int = Field(default=5)
    CACHE_DEFAULT_TTL: int = Field(default=1800)

    # ── Concurrency ──
    RATE_LIMIT_RPM: int = Field(default=100)
    RATE_LIMIT_BURST: int = Field(default=10)
    MAX_CONCURRENT_TASKS: int = Field(default=20)
    REQUEST_TIMEOUT_SECONDS: int = Field(default=300)

    # ── Server ──
    PORT: int = Field(default=8080)
    HOST: str = Field(default="0.0.0.0")
    LOG_LEVEL: str = Field(default="info")
    USE_JSON_LOGS: bool = Field(default=True)

    # ── Redis ──
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str = Field(default="")

    # ── Database ──
    DATABASE_URL: str = Field(default="postgresql+asyncpg://pitchai:pitchai@localhost:5432/pitchai")
    RETRIEVAL_LEDGER_DB_PATH: str = Field(default="data/retrieval_ledger.db")

    # ── Vision / Video ──
    FRAME_SAMPLE_INTERVAL: int = Field(default=5)
    NATIVE_VIDEO_WINDOW_SECONDS: float = Field(default=3.0)
    NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS: float = Field(default=0.75)
    NATIVE_VIDEO_MAX_WINDOWS: int = Field(default=6)

    # ── CORS ──
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000")


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings