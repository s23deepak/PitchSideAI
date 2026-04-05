"""
DynamoDB Tool — PitchSide AI
Writes tactical events and retrieves recent match context from Amazon DynamoDB.
Replaces the previous Firestore implementation.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from config import AWS_REGION, DYNAMODB_TABLE_NAME

# Initialize DynamoDB resource
_dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
_table = _dynamodb.Table(DYNAMODB_TABLE_NAME)


def _slugify(value: str) -> str:
    """Normalize free-text labels into stable key segments."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return cleaned.strip("-") or "unknown"


def build_match_session_key(home_team: str, away_team: str, sport: str = "soccer") -> str:
    """Build a deterministic DynamoDB partition key for a match session."""
    return f"{_slugify(sport)}#{_slugify(home_team)}#vs#{_slugify(away_team)}"

async def write_event(
    event_type: str,
    description: str,
    metadata: dict[str, Any] | None = None,
    match_session: str | None = None,
) -> str:
    """
    Write a match event to DynamoDB.

    Args:
        event_type: Category of event (e.g., 'tactical_detection', 'fan_qa').
        description: Human-readable description of the event.
        metadata: Optional dict with extra structured data.

    Returns:
        The DynamoDB item ID.
    """
    item_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    resolved_metadata = metadata or {}
    resolved_match_session = match_session or resolved_metadata.get("match_session") or "active_match"

    item = {
        "id": item_id,
        "type": event_type,
        "description": description,
        "metadata": resolved_metadata,
        "timestamp": timestamp,
        "match_session": resolved_match_session,
    }
    
    # Run sync boto3 call in a thread if needed, but for simplicity here:
    from config import LLM_BACKEND
    if LLM_BACKEND == "bedrock":
        _table.put_item(Item=item)
    return item_id

async def get_recent_events(n: int = 10, match_session: str | None = None) -> list[dict[str, Any]]:
    """
    Retrieve the most recent N match events from DynamoDB.

    Args:
        n: Number of recent events to retrieve.

    Returns:
        List of event dicts ordered by timestamp descending.
    """
    # Assuming a Global Secondary Index (GSI) named "SessionTimestampIndex" 
    # with Partition Key: `match_session` and Sort Key: `timestamp`.
    from config import LLM_BACKEND
    if LLM_BACKEND != "bedrock":
        return []

    resolved_match_session = match_session or "active_match"
        
    try:
        response = _table.query(
            IndexName='SessionTimestampIndex',
            KeyConditionExpression=Key('match_session').eq(resolved_match_session),
            ScanIndexForward=False, # Descending
            Limit=n
        )
        return response.get('Items', [])
    except Exception as e:
        # Fallback if table/index isn't created yet (for local scaffolding limits)
        return []
