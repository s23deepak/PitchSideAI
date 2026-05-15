"""Redis event helpers for commentary-notes job progress."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from config import REDIS_URL


def notes_job_channel(job_id: str) -> str:
    return f"notes_job:{job_id}"


async def publish_notes_job_event(job_id: str, event: dict[str, Any]) -> None:
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.publish(notes_job_channel(job_id), json.dumps(event, default=str))
    finally:
        await client.aclose()
