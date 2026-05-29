"""
Base Agent Class
Provides common functionality and interface for all agents.
"""
import base64
import asyncio
import json
import logging
import os
import unicodedata
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime

import httpx
from core import get_logger
from data_sources.retrieval_audit import audit_llm_call
from config import (
    COMMENTARY_NOTES_LLM_BACKEND, LLM_BACKEND,
    OPENAI_API_KEY, OPENAI_MODEL,
    WAFER_API_KEY, WAFER_BASE_URL, WAFER_MODEL,
    VISION_LLM_BACKEND, VLLM_BASE_URL, VLLM_MODEL, VLLM_VISION_MODEL,
)

logger = get_logger(__name__)


RETRYABLE_LLM_STATUS_CODES = {429, 500, 502, 503, 504}
WAFER_RETRY_TEXT_PATTERNS = (
    "concurrency",
    "concurrent",
    "rate limit",
    "rate_limit",
    "too many requests",
    "temporarily overloaded",
    "overloaded",
    "capacity",
)
WAFER_CONCURRENCY_STATUS_CODES = {429, 503}
COMMENTARY_NOTES_WAFER_CONCURRENCY_ENV = "COMMENTARY_NOTES_WAFER_MAX_CONCURRENCY"
OPENAI_COMPATIBLE_NATIVE_VIDEO_BACKENDS = {"vllm"}
COMMENTARY_NOTES_AGENT_TYPES = {
    "historical_context",
    "matchup_analysis",
    "news",
    "note_organizer",
    "player_research",
    "team_form",
    "weather_context",
}
VIDEO_DATA_URL_MIME_TYPES = {
    "flv": "video/x-flv",
    "mkv": "video/x-matroska",
    "mov": "video/quicktime",
    "mp4": "video/mp4",
    "mpeg": "video/mpeg",
    "mpg": "video/mpeg",
    "three_gp": "video/3gpp",
    "webm": "video/webm",
    "wmv": "video/x-ms-wmv",
}
_COMMENTARY_NOTES_WAFER_SEMAPHORES: dict[int, asyncio.Semaphore] = {}


def _get_video_data_url_mime_type(video_format: Optional[str]) -> str:
    normalized_format = (video_format or "mp4").strip().lower()
    return VIDEO_DATA_URL_MIME_TYPES.get(normalized_format, f"video/{normalized_format}")


def _resolve_backend(agent_type: str) -> str:
    if agent_type == "vision" and VISION_LLM_BACKEND:
        return VISION_LLM_BACKEND
    if agent_type in COMMENTARY_NOTES_AGENT_TYPES and COMMENTARY_NOTES_LLM_BACKEND:
        return COMMENTARY_NOTES_LLM_BACKEND
    return LLM_BACKEND


def _get_commentary_notes_wafer_semaphore() -> Optional[asyncio.Semaphore]:
    limit = int(os.getenv(COMMENTARY_NOTES_WAFER_CONCURRENCY_ENV, "2"))
    if limit <= 0:
        return None
    semaphore = _COMMENTARY_NOTES_WAFER_SEMAPHORES.get(limit)
    if semaphore is None:
        semaphore = asyncio.Semaphore(limit)
        _COMMENTARY_NOTES_WAFER_SEMAPHORES.clear()
        _COMMENTARY_NOTES_WAFER_SEMAPHORES[limit] = semaphore
    return semaphore


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Provides common LLM API interaction, error handling, and logging.
    """

    def __init__(self, model_id: str, sport: str = "soccer", agent_type: str = "base"):
        """
        Initialize agent.

        Args:
            model_id: Model ID (OpenAI model or vLLM model)
            sport: Sport type (e.g., "soccer", "cricket")
            agent_type: Agent type for logging
        """
        self.sport = sport
        self.agent_type = agent_type
        self.logger = get_logger(f"agent.{agent_type}")
        self.backend = _resolve_backend(agent_type)
        self.model_id = model_id

        if self.backend == "openai":
            self.model_id = OPENAI_MODEL
        elif self.backend == "wafer":
            self.model_id = WAFER_MODEL
        elif self.backend == "vllm":
            self.model_id = VLLM_VISION_MODEL if self.agent_type == "vision" else VLLM_MODEL
        else:
            raise ValueError(
                f"Unknown LLM_BACKEND: '{self.backend}'. "
                "Supported backends: 'vllm', 'openai', 'wafer'. "
                "Set LLM_BACKEND in your .env file."
            )

    async def call_llm(
        self,
        prompt: str,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        image_data: Optional[bytes] = None,
        video_data: Optional[bytes] = None,
        video_format: Optional[str] = None,
        response_format: str = "text"
    ) -> str:
        """
        Call the configured OpenAI-compatible LLM API with error handling and logging.
        """
        guardrail = (
            "\n\nCRITICAL INSTRUCTION: You are generating a final output narrative. "
            "DO NOT output template placeholders. DO NOT invent or fabricate statistics, "
            "records, scores, dates, lineups, injuries, suspensions, biographies, or weather details. "
            "Only use facts explicitly provided in the prompt context. If data is unavailable, "
            "state that it is unavailable instead of guessing."
        )
        prompt = unicodedata.normalize('NFKC', prompt) + guardrail

        return await self._call_openai_compatible(
            prompt,
            temperature,
            max_tokens,
            image_data,
            video_data,
            video_format,
            response_format,
        )

    def _get_openai_config(self) -> tuple:
        """Return (base_url, api_key) for the active backend."""
        if self.backend == "openai":
            return "https://api.openai.com", OPENAI_API_KEY
        elif self.backend == "wafer":
            return WAFER_BASE_URL, WAFER_API_KEY
        elif self.backend == "vllm":
            return VLLM_BASE_URL, None
        raise ValueError(f"No OpenAI-compatible config for backend: {self.backend}")

    @staticmethod
    def _extract_message_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if text_value:
                        text_parts.append(text_value)
            return "\n".join(text_parts)
        return str(content)

    async def _call_openai_compatible(
        self,
        prompt: str,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        image_data: Optional[bytes] = None,
        video_data: Optional[bytes] = None,
        video_format: Optional[str] = None,
        response_format: str = "text"
    ) -> str:
        """Call any OpenAI-compatible API (vLLM or OpenAI)."""
        start_time = datetime.utcnow()
        base_url, api_key = self._get_openai_config()

        try:
            content = []
            if image_data:
                b64_image = base64.b64encode(image_data).decode("utf-8")
                mime_type = "image/png" if image_data.startswith(b"\x89PNG") else "image/jpeg"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}
                })
            if video_data:
                if self.backend not in OPENAI_COMPATIBLE_NATIVE_VIDEO_BACKENDS:
                    raise ValueError(f"Native video input is not supported for backend: {self.backend}")
                b64_video = base64.b64encode(video_data).decode("utf-8")
                mime_type = _get_video_data_url_mime_type(video_format)
                content.append({
                    "type": "video_url",
                    "video_url": {"url": f"data:{mime_type};base64,{b64_video}"}
                })
            content.append({"type": "text", "text": prompt})

            payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": content}],
                "temperature": temperature,
                "stream": False,
            }
            if max_tokens:
                max_tokens_key = "max_completion_tokens" if self.backend == "vllm" else "max_tokens"
                payload[max_tokens_key] = max_tokens
            if response_format == "json":
                payload["response_format"] = {"type": "json_object"}
            if self.backend == "wafer":
                payload["chat_template_kwargs"] = {"enable_thinking": False}

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            semaphore = self._get_llm_call_semaphore()
            if semaphore is None:
                response = await self._post_chat_completion_with_retries(base_url, payload, headers)
            else:
                async with semaphore:
                    response = await self._post_chat_completion_with_retries(base_url, payload, headers)
            if response.is_error:
                response_text = response.text.strip()
                error_message = (
                    f"{self.backend} chat completion failed with status {response.status_code}: {response_text}"
                    if response_text
                    else f"{self.backend} chat completion failed with status {response.status_code}"
                )
                raise ValueError(error_message)

            result = self._extract_message_text(response.json()["choices"][0]["message"]["content"])

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await audit_llm_call(
                agent_type=self.agent_type,
                backend=self.backend,
                model_id=self.model_id,
                prompt=prompt,
                response=result,
                duration_ms=duration_ms,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            self.logger.log_performance(
                f"{self.agent_type}.{self.backend}_call", duration_ms, success=True
            )
            return result

        except Exception as exc:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.logger.log_performance(
                f"{self.agent_type}.{self.backend}_call", duration_ms, success=False
            )
            await audit_llm_call(
                agent_type=self.agent_type,
                backend=self.backend,
                model_id=self.model_id,
                prompt=prompt,
                error=exc,
                duration_ms=duration_ms,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            self.logger.error(
                f"{self.agent_type}_{self.backend}_error", error=str(exc), exc_info=True
            )
            raise

    def _get_llm_call_semaphore(self) -> Optional[asyncio.Semaphore]:
        if self.backend == "wafer" and self.agent_type in COMMENTARY_NOTES_AGENT_TYPES:
            return _get_commentary_notes_wafer_semaphore()
        return None

    def _is_wafer_concurrency_or_rate_response(self, response: httpx.Response) -> bool:
        if self.backend != "wafer":
            return False
        response_text = response.text.lower()
        return any(pattern in response_text for pattern in WAFER_RETRY_TEXT_PATTERNS)

    def _is_retryable_llm_response(self, response: httpx.Response) -> bool:
        return (
            response.status_code in RETRYABLE_LLM_STATUS_CODES
            or self._is_wafer_concurrency_or_rate_response(response)
        )

    async def _post_chat_completion_with_retries(
        self,
        base_url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> httpx.Response:
        max_attempts = int(os.getenv("LLM_MAX_RETRY_ATTEMPTS", "5"))
        retry_base_seconds = float(os.getenv("LLM_RETRY_BASE_SECONDS", "1.0"))
        timeout_seconds = float(os.getenv("LLM_HTTP_TIMEOUT_SECONDS", "300.0"))

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            last_response: Optional[httpx.Response] = None
            for attempt in range(max(1, max_attempts)):
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                last_response = response
                if not self._is_retryable_llm_response(response):
                    return response
                if attempt == max_attempts - 1:
                    return response

                if (
                    self._is_wafer_concurrency_or_rate_response(response)
                    or (self.backend == "wafer" and response.status_code in WAFER_CONCURRENCY_STATUS_CODES)
                ):
                    delay_seconds = 1.0
                else:
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        try:
                            delay_seconds = float(retry_after)
                        except ValueError:
                            delay_seconds = retry_base_seconds
                    else:
                        delay_seconds = retry_base_seconds * (2 ** attempt)
                await asyncio.sleep(min(delay_seconds, 20.0))

        return last_response  # type: ignore[return-value]

    async def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response from model with error handling.

        Args:
            response: Raw response text from model

        Returns:
            Parsed JSON dict
        """
        try:
            # Clean markdown formatting if present
            cleaned = response.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            self.logger.error(
                "json_parse_failed",
                response=response[:200],  # Log first 200 chars
                exc_info=True
            )
            raise

    def _chunk_text(self, text: str, chunk_size: int = 500) -> list[str]:
        """
        Chunk text into smaller pieces for storage/processing.

        Args:
            text: Text to chunk
            chunk_size: Size of each chunk (in words)

        Returns:
            List of text chunks
        """
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():  # Only add non-empty chunks
                chunks.append(chunk)

        return chunks

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log an agent event."""
        self.logger.log_event(event_type, {
            **details,
            "agent_type": self.agent_type,
            "sport": self.sport
        })

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the agent's primary task. Must be implemented by subclass."""
        pass


class ResearchAgent(BaseAgent):
    """Research agent base - to be implemented by specific research agents."""

    def __init__(self, model_id: str, sport: str = "soccer"):
        super().__init__(model_id, sport, agent_type="research")

    async def execute(self, home_team: str, away_team: str) -> str:
        """Execute research task."""
        raise NotImplementedError("Subclass must implement execute()")


class VisionAgent(BaseAgent):
    """Vision agent base - to be implemented by specific vision agents."""

    def __init__(self, model_id: str, sport: str = "soccer"):
        super().__init__(model_id, sport, agent_type="vision")

    async def execute(self, image_data: bytes) -> Dict[str, Any]:
        """Execute vision task."""
        raise NotImplementedError("Subclass must implement execute()")


class LiveAgent(BaseAgent):
    """Live agent base - handles real-time interactions."""

    def __init__(self, model_id: str, sport: str = "soccer"):
        super().__init__(model_id, sport, agent_type="live")

    async def execute(self, query: str) -> str:
        """Execute live query task."""
        raise NotImplementedError("Subclass must implement execute()")


class CommentaryAgent(BaseAgent):
    """Commentary generation agent."""

    def __init__(self, model_id: str, sport: str = "soccer"):
        super().__init__(model_id, sport, agent_type="commentary")

    async def execute(self, match_context: str, recent_events: str) -> str:
        """Execute commentary generation task."""
        raise NotImplementedError("Subclass must implement execute()")
