"""
Webhooks Blueprint - Ingest layer for external webhook events.

This layer:
- Receives HTTP webhook events from external sources
- Publishes messages to Service Bus queues for async processing
- Returns 200 immediately to prevent webhook retries
- Manages scheduled tasks via timer triggers
"""

import azure.functions as func
import logging

from shared import json_response
from webhooks.utility.util_service_bus import publish_to_service_bus

bp = func.Blueprint()


# CONFIGURATION - Map webhook sources to queues and handlers
WEBHOOK_CONFIG = {
    # Add webhook sources here:
    # "source_name": {
    #     "queue": "webhook-ingest",
    #     "handler": process_source_webhook,
    # },
}


# =============================================================================
# WEBHOOK ENDPOINT
# =============================================================================

@bp.route(route="webhooks/{*source}", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def webhook_handler(req: func.HttpRequest) -> func.HttpResponse:
    """
    Unified webhook handler for all registered sources.

    Flow:
        1. Identify source from URL path
        2. Call source-specific handler to get messages
        3. Publish each message to corresponding Service Bus queue
        4. Return 200 immediately

    Always returns 200 to prevent webhook retries (even on errors).
    """
    source = req.route_params.get('source', '').lower()
    logging.info(f"Webhook received: source={source}")

    if source not in WEBHOOK_CONFIG:
        logging.warning(f"Unknown webhook source: {source}")
        return json_response({
            "status": "ignored",
            "reason": f"unknown source: {source}"
        }, 200)

    config = WEBHOOK_CONFIG[source]
    queue_name = config["queue"]
    handler = config["handler"]

    try:
        body = req.get_json() if req.get_body() else {}
    except Exception as e:
        logging.warning(f"Failed to parse webhook body: {e}")
        body = {}

    try:
        result = handler(body)
    except Exception as e:
        logging.exception(f"Error in {source} webhook handler: {e}")
        return json_response({
            "status": "error",
            "source": source,
            "message": str(e)
        }, 200)

    if not result.get("success"):
        return json_response({
            "status": "error",
            "source": source,
            "message": result.get("error", "Unknown error"),
        }, 200)

    message = result.get("message")
    if not message:
        return json_response({
            "status": "ok",
            "source": source,
            "queued": False,
        }, 200)

    success = publish_to_service_bus(queue_name, message, ensure_queue=False)

    return json_response({
        "status": "processed" if success else "error",
        "source": source,
        "queue": queue_name,
        "queued": success,
    }, 200)


# =============================================================================
# IMPORT TIMER TRIGGERS
# =============================================================================

from webhooks import timers  # noqa: F401, E402
