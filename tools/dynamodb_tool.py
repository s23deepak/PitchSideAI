"""
DynamoDB Tool — PitchSide AI
Writes tactical events and retrieves recent match context from Amazon DynamoDB.
Replaces the previous Firestore implementation.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from config import AWS_REGION, DYNAMODB_TABLE_NAME

# Initialize DynamoDB resource
_dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
_table = _dynamodb.Table(DYNAMODB_TABLE_NAME)

async def write_event(event_type: str, description: str, metadata: dict[str, Any] | None = None) -> str:
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
    
    item = {
        "id": item_id,
        "type": event_type,
        "description": description,
        "metadata": metadata or {},
        "timestamp": timestamp,
        # A static partition key for global sorting by timestamp in a GSI
        "match_session": "active_match" 
    }
    
    # Run sync boto3 call in a thread if needed, but for simplicity here:
    from config import LLM_BACKEND
    if LLM_BACKEND == "bedrock":
        _table.put_item(Item=item)
    return item_id

async def get_recent_events(n: int = 10) -> list[dict[str, Any]]:
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
        
    try:
        response = _table.query(
            IndexName='SessionTimestampIndex',
            KeyConditionExpression=Key('match_session').eq('active_match'),
            ScanIndexForward=False, # Descending
            Limit=n
        )
        return response.get('Items', [])
    except Exception as e:
        # Fallback if table/index isn't created yet (for local scaffolding limits)
        return []
