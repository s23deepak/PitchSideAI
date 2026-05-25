"""
Provider-agnostic retrieval and LLM audit dumps.

Enabled with:
    RETRIEVAL_DEBUG_DUMP=true
    LLM_DEBUG_DUMP=true
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_RUN_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("retrieval_audit_run_id", default=None)

_SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|authorization|bearer)", re.IGNORECASE)
_COUNTER_LOCK = threading.Lock()
_COUNTERS: Dict[str, int] = {}


def retrieval_audit_enabled() -> bool:
    return os.getenv("RETRIEVAL_DEBUG_DUMP", "false").lower() in {"1", "true", "yes", "on"}


def llm_audit_enabled() -> bool:
    return os.getenv("LLM_DEBUG_DUMP", "false").lower() in {"1", "true", "yes", "on"}


def raw_dump_enabled() -> bool:
    return os.getenv("RETRIEVAL_DEBUG_INCLUDE_RAW", "true").lower() in {"1", "true", "yes", "on"}


def set_audit_run_id(run_id: Optional[str] = None) -> str:
    """Set the current async-context audit run id and return it."""
    resolved = _safe_name(run_id or _new_run_id())
    _RUN_ID.set(resolved)
    return resolved


def get_audit_run_id() -> str:
    current = _RUN_ID.get()
    if current:
        return current
    return set_audit_run_id()


def get_audit_dir() -> Path:
    root = Path(os.getenv("RETRIEVAL_DEBUG_DIR", "debug/retrievals"))
    return root / get_audit_run_id()


async def audit_retrieval(
    *,
    provider: str,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    result: Any = None,
    error: Optional[BaseException] = None,
    duration_ms: Optional[float] = None,
    source: str = "retriever",
) -> None:
    """Append a retriever/search event to the current audit run."""
    if not retrieval_audit_enabled():
        return

    success = error is None
    event = {
        "type": "retrieval",
        "timestamp": _now_iso(),
        "source": source,
        "provider": provider,
        "method": method,
        "params": _sanitize(params or {}),
        "success": success,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "error": _error_payload(error) if error else None,
        "raw_response": _sanitize(result) if raw_dump_enabled() else None,
        "summary": _summarize(result),
    }
    await _write_event(event, f"{provider}_{method}")


async def audit_llm_call(
    *,
    agent_type: str,
    backend: str,
    model_id: str,
    prompt: str,
    response: Optional[str] = None,
    error: Optional[BaseException] = None,
    duration_ms: Optional[float] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: str = "text",
) -> None:
    """Append an LLM prompt/response event to the current audit run."""
    if not llm_audit_enabled():
        return

    event = {
        "type": "llm",
        "timestamp": _now_iso(),
        "agent_type": agent_type,
        "backend": backend,
        "model_id": model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": response_format,
        "success": error is None,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "error": _error_payload(error) if error else None,
        "prompt": _truncate(prompt),
        "response": _truncate(response) if response is not None else None,
    }
    await _write_event(event, f"{agent_type}_{backend}_llm")


async def _write_event(event: Dict[str, Any], label: str) -> None:
    await asyncio.to_thread(_write_event_sync, event, label)


def _write_event_sync(event: Dict[str, Any], label: str) -> None:
    audit_dir = get_audit_dir()
    audit_dir.mkdir(parents=True, exist_ok=True)

    run_id = get_audit_run_id()
    with _COUNTER_LOCK:
        counter = _COUNTERS.get(run_id, 0) + 1
        _COUNTERS[run_id] = counter
        event_id = f"{counter:04d}_{_safe_name(label)}"
        event = {"event_id": event_id, **event}

        manifest_path = audit_dir / "manifest.jsonl"
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

        event_path = audit_dir / f"{event_id}.json"
        with event_path.open("w", encoding="utf-8") as handle:
            json.dump(event, handle, ensure_ascii=False, indent=2, default=str)

        if event.get("type") == "llm":
            prompt_path = audit_dir / f"{event_id}_prompt.txt"
            prompt_path.write_text(event.get("prompt") or "", encoding="utf-8")
            response = event.get("response")
            if response is not None:
                response_path = audit_dir / f"{event_id}_response.txt"
                response_path.write_text(response, encoding="utf-8")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _truncate(value) if isinstance(value, str) else value
    return _truncate(str(value))


def _summarize(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return {
            "kind": "dict",
            "keys": list(value.keys())[:20],
            "size": len(value),
        }
    if isinstance(value, list):
        first = value[0] if value else None
        return {
            "kind": "list",
            "size": len(value),
            "first_item_keys": list(first.keys())[:20] if isinstance(first, dict) else None,
        }
    if isinstance(value, str):
        return {"kind": "str", "chars": len(value)}
    if value is None:
        return {"kind": "none"}
    return {"kind": type(value).__name__}


def _error_payload(error: BaseException) -> Dict[str, str]:
    return {
        "type": type(error).__name__,
        "message": str(error),
    }


def _truncate(value: str) -> str:
    max_string_chars = int(os.getenv("RETRIEVAL_DEBUG_MAX_STRING_CHARS", "20000"))
    if len(value) <= max_string_chars:
        return value
    return value[:max_string_chars] + "\n...[truncated]"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")[:120] or "audit"


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{os.getpid()}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def monotonic_ms() -> float:
    return time.monotonic() * 1000


class AuditedRetrieverProxy:
    """Transparent proxy that audits async method calls on a retriever object."""

    def __init__(self, provider: str, retriever: Any):
        self._audit_provider = provider
        self._audit_retriever = retriever

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._audit_retriever, name)
        if not inspect.iscoroutinefunction(attr):
            return attr

        @functools.wraps(attr)
        async def audited_method(*args: Any, **kwargs: Any) -> Any:
            start_ms = monotonic_ms()
            params = {"args": list(args), "kwargs": kwargs}
            try:
                result = await attr(*args, **kwargs)
                await audit_retrieval(
                    provider=self._audit_provider,
                    method=name,
                    params=params,
                    result=result,
                    duration_ms=monotonic_ms() - start_ms,
                    source="retriever_proxy",
                )
                return result
            except Exception as exc:
                await audit_retrieval(
                    provider=self._audit_provider,
                    method=name,
                    params=params,
                    error=exc,
                    duration_ms=monotonic_ms() - start_ms,
                    source="retriever_proxy",
                )
                raise

        return audited_method
