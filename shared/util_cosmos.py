"""
Cosmos DB client for event and execution logs.

Container: agent-events
Used for execution traces, token usage fallback, and audit logs.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from shared.util_config import get_config


_client = None
_database = None


def _get_database():
    """Lazy-initialize Cosmos DB client and database reference."""
    global _client, _database
    if _database is not None:
        return _database

    config = get_config()
    if not config.cosmos_endpoint or not config.cosmos_key:
        return None

    try:
        from azure.cosmos import CosmosClient
        _client = CosmosClient(config.cosmos_endpoint, credential=config.cosmos_key)
        _database = _client.get_database_client(config.cosmos_database)
        return _database
    except Exception as e:
        logging.warning(f"Failed to initialize Cosmos DB: {e}")
        return None


def log_event(container_name: str, event: dict, partition_key: Optional[str] = None) -> dict:
    """
    Write an event document to Cosmos DB.

    Args:
        container_name: Target container (e.g., "agent-events")
        event: Event data dict
        partition_key: Optional partition key value (defaults to event_type)

    Returns:
        {"success": bool, "id": str or None, "error": str or None}
    """
    db = _get_database()
    if db is None:
        return {"success": False, "error": "Cosmos DB not configured"}

    try:
        container = db.get_container_client(container_name)

        # Add metadata
        event["id"] = event.get("id") or str(uuid.uuid4())
        event["timestamp"] = event.get("timestamp") or datetime.utcnow().isoformat()
        event["_partition_key"] = partition_key or event.get("event_type", "default")

        container.upsert_item(event)
        return {"success": True, "id": event["id"]}

    except Exception as e:
        logging.warning(f"Failed to log event to Cosmos DB: {e}")
        return {"success": False, "error": str(e)}


def query_events(container_name: str, query: str, parameters: list = None) -> dict:
    """
    Query events from Cosmos DB.

    Args:
        container_name: Container to query
        query: SQL query string
        parameters: Query parameters

    Returns:
        {"success": bool, "items": list, "error": str or None}
    """
    db = _get_database()
    if db is None:
        return {"success": False, "items": [], "error": "Cosmos DB not configured"}

    try:
        container = db.get_container_client(container_name)
        items = list(container.query_items(
            query=query,
            parameters=parameters or [],
            enable_cross_partition_query=True
        ))
        return {"success": True, "items": items}

    except Exception as e:
        logging.warning(f"Failed to query Cosmos DB: {e}")
        return {"success": False, "items": [], "error": str(e)}
