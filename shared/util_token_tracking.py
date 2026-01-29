"""
Token tracking utility for LLM usage analytics.

Provides fail-safe token usage tracking via SQL Server,
with Cosmos DB fallback for event logging.
"""

import json
import logging
from datetime import datetime
from typing import Optional


def ensure_token_usage_table() -> None:
    """
    Ensure the LLMTokenUsage table exists in the database.
    Called on application startup.
    """
    try:
        from tools.utility.util_datamodel import LLMTokenUsage
        from tools.utility.util_database import ensure_table
        ensure_table(LLMTokenUsage)
        logging.info("LLMTokenUsage table verified/created")
    except Exception as e:
        logging.warning(f"Could not ensure LLMTokenUsage table: {e}")


def track_token_usage(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    agent_type: str,
    started_at: datetime,
    agent_operation: Optional[str] = None,
    inference_rounds: Optional[int] = None,
    description: Optional[str] = None,
    completed_at: Optional[datetime] = None
) -> dict:
    """
    Track LLM token usage for analytics.

    Fail-safe: errors are logged but never propagated.
    Falls back to Cosmos DB if SQL write fails.
    """
    try:
        if not model_name or not agent_type:
            return {"success": False, "error": "model_name and agent_type are required"}

        if input_tokens < 0 or output_tokens < 0:
            return {"success": False, "error": "Token counts cannot be negative"}

        if completed_at is None:
            completed_at = datetime.utcnow()

        if description and len(description) > 500:
            description = description[:497] + "..."

        from tools.utility.util_database import SessionLocal
        from tools.utility.util_datamodel import LLMTokenUsage

        if SessionLocal is None:
            return _fallback_to_cosmos(
                model_name, input_tokens, output_tokens, agent_type,
                started_at, agent_operation, inference_rounds, description, completed_at
            )

        session = SessionLocal()
        try:
            record = LLMTokenUsage(
                agent_type=agent_type,
                agent_operation=agent_operation,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                inference_rounds=inference_rounds or 0,
                description=description,
                started_at=started_at,
                completed_at=completed_at
            )
            session.add(record)
            session.commit()
            record_id = record.id
            session.close()

            logging.debug(
                f"Token usage tracked: agent={agent_type}, model={model_name}, "
                f"tokens={input_tokens + output_tokens}, id={record_id}"
            )
            return {"success": True, "id": record_id}

        except Exception as e:
            session.rollback()
            session.close()
            raise e

    except Exception as e:
        error_msg = f"Failed to track token usage: {e}"
        logging.warning(error_msg)

        # Fallback to Cosmos DB
        try:
            return _fallback_to_cosmos(
                model_name, input_tokens, output_tokens, agent_type,
                started_at, agent_operation, inference_rounds, description,
                completed_at, error=str(e)
            )
        except Exception as fallback_error:
            logging.warning(f"Cosmos fallback also failed: {fallback_error}")

        return {"success": False, "error": error_msg}


def _fallback_to_cosmos(
    model_name, input_tokens, output_tokens, agent_type,
    started_at, agent_operation=None, inference_rounds=None,
    description=None, completed_at=None, error=None
) -> dict:
    """Fallback: write token usage to Cosmos DB event log."""
    try:
        from shared.util_cosmos import log_event
        event = {
            "event_type": "token_usage",
            "agent_type": agent_type,
            "agent_operation": agent_operation,
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "inference_rounds": inference_rounds,
            "description": description,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "sql_error": error,
        }
        result = log_event("token-usage", event)
        if result.get("success"):
            return {"success": True, "id": result.get("id"), "store": "cosmos"}
        return {"success": False, "error": f"Cosmos fallback failed: {result.get('error')}"}
    except Exception as e:
        return {"success": False, "error": f"Cosmos fallback failed: {e}"}
