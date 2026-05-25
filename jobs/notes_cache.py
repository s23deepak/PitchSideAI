"""Redis cache and notification helpers for production notes lifecycle."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import redis.asyncio as redis

from config import REDIS_URL
from models.notes_jobs import NotesVersion, build_vlm_context_payload
from models.notes_store import NotesStore


def notes_cache_key(match_id: str) -> str:
    return f"notes:latest:{match_id}"


def vlm_context_cache_key(match_id: str) -> str:
    return f"notes:vlm-context:{match_id}"


def notes_update_channel(match_id: str) -> str:
    return f"notes:updated:{match_id}"


def notes_lock_key(match_id: str) -> str:
    return f"notes:lock:{match_id}"


async def cache_notes_version(version: NotesVersion, ttl_seconds: int = 6 * 60 * 60) -> None:
    """Cache latest NotesStore and VLM context for fast live-path retrieval."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        payload = {
            "match_id": version.match_id,
            "match_session": version.match_session,
            "notes_version": version.notes_version,
            "vlm_context_version": version.vlm_context_version,
            "update_type": version.update_type,
            "source_event_id": version.source_event_id,
            "notes_store": version.notes_store_json,
            "warnings": version.warnings,
            "errors": version.errors,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
        await client.setex(notes_cache_key(version.match_id), ttl_seconds, json.dumps(payload, default=str))
        await client.setex(vlm_context_cache_key(version.match_id), ttl_seconds, json.dumps(version.vlm_context_json, default=str))
    finally:
        await client.aclose()


async def get_cached_vlm_context(match_id: str) -> dict[str, Any] | None:
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        raw = await client.get(vlm_context_cache_key(match_id))
        if not raw:
            return None
        return json.loads(raw)
    finally:
        await client.aclose()


async def publish_notes_updated(version: NotesVersion) -> None:
    """Notify API/VLM workers that a newer notes context is available."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        event = {
            "type": "notes_updated",
            "match_id": version.match_id,
            "match_session": version.match_session,
            "notes_version": version.notes_version,
            "vlm_context_version": version.vlm_context_version,
            "update_type": version.update_type,
            "source_event_id": version.source_event_id,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
        await client.publish(notes_update_channel(version.match_id), json.dumps(event, default=str))
    finally:
        await client.aclose()


def build_vlm_context(notes_store: NotesStore, notes_version: int, vlm_context_version: int) -> dict[str, Any]:
    return build_vlm_context_payload(notes_store, notes_version, vlm_context_version)


@asynccontextmanager
async def notes_update_lock(match_id: str, ttl_seconds: int = 300) -> AsyncIterator[bool]:
    """Best-effort distributed lock around notes version creation."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    acquired = False
    try:
        acquired = bool(await client.set(notes_lock_key(match_id), "1", ex=ttl_seconds, nx=True))
        yield acquired
    finally:
        if acquired:
            await client.delete(notes_lock_key(match_id))
        await client.aclose()
