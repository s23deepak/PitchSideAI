"""
Firestore Tool — ADK Tool Function
Writes tactical events and retrieves recent match context from Cloud Firestore.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from config import FIRESTORE_COLLECTION, GCP_PROJECT

_db: firestore.AsyncClient | None = None


def _get_db() -> firestore.AsyncClient:
    global _db
    if _db is None:
        _db = firestore.AsyncClient(project=GCP_PROJECT)
    return _db


async def write_event(event_type: str, description: str, metadata: dict[str, Any] | None = None) -> str:
    """
    ADK Tool: Write a match event to Firestore.

    Args:
        event_type: Category of event (e.g., 'tactical_detection', 'fan_question', 'commentary').
        description: Human-readable description of the event.
        metadata: Optional dict with extra structured data.

    Returns:
        The Firestore document ID of the written event.
    """
    db = _get_db()
    doc_id = str(uuid.uuid4())
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(doc_id)
    await doc_ref.set({
        "id": doc_id,
        "type": event_type,
        "description": description,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return doc_id


async def get_recent_events(n: int = 10) -> list[dict[str, Any]]:
    """
    ADK Tool: Retrieve the most recent N match events from Firestore.

    Args:
        n: Number of recent events to retrieve (default 10).

    Returns:
        List of event dicts ordered by timestamp descending.
    """
    db = _get_db()
    query = (
        db.collection(FIRESTORE_COLLECTION)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(n)
    )
    results = []
    async for doc in query.stream():
        results.append(doc.to_dict())
    return results


# ── CLI self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def _test():
        print("Writing test event...")
        doc_id = await write_event("test", "Firestore connectivity check", {"status": "ok"})
        print(f"  ✅ Written doc ID: {doc_id}")
        events = await get_recent_events(3)
        print(f"  ✅ Retrieved {len(events)} event(s).")
        for e in events:
            print(f"     {e['timestamp']} | {e['type']} | {e['description']}")
    asyncio.run(_test())
