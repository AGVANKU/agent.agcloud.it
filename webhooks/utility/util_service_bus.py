"""
Service Bus utilities for webhooks layer.

Provides:
- Queue existence checking and creation
- Message publishing to queues
"""

import os
import json
import logging

SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")

# Cache for queues we've verified exist
_verified_queues: set = set()


def ensure_queue_exists(queue_name: str) -> bool:
    """
    Ensure a Service Bus queue exists, creating it if necessary.
    Uses in-memory cache to avoid repeated API calls.
    Returns True if queue exists or was created, False on error.
    """
    global _verified_queues

    if queue_name in _verified_queues:
        return True

    if not SERVICE_BUS_CONNECTION_STRING:
        logging.warning("SERVICE_BUS_CONNECTION_STRING not configured - cannot verify queue")
        return False

    try:
        from azure.servicebus.management import ServiceBusAdministrationClient

        with ServiceBusAdministrationClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as admin_client:
            try:
                admin_client.get_queue(queue_name)
                logging.info(f"Queue '{queue_name}' exists")
                _verified_queues.add(queue_name)
                return True
            except Exception as e:
                if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                    logging.info(f"Queue '{queue_name}' not found, creating...")
                    admin_client.create_queue(queue_name)
                    logging.info(f"Queue '{queue_name}' created successfully")
                    _verified_queues.add(queue_name)
                    return True
                else:
                    raise
    except Exception as e:
        logging.exception(f"Failed to ensure queue '{queue_name}' exists: {e}")
        return False


def publish_to_service_bus(queue_name: str, message: dict, ensure_queue: bool = True) -> bool:
    """
    Publish a single message to Service Bus queue.
    Returns True if successful, False otherwise.
    """
    if not SERVICE_BUS_CONNECTION_STRING:
        logging.warning("SERVICE_BUS_CONNECTION_STRING not configured - message not sent")
        return False

    if ensure_queue and not ensure_queue_exists(queue_name):
        logging.error(f"Queue '{queue_name}' does not exist and could not be created")
        return False

    try:
        from azure.servicebus import ServiceBusClient, ServiceBusMessage

        with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
            with client.get_queue_sender(queue_name) as sender:
                sb_message = ServiceBusMessage(
                    json.dumps(message),
                    content_type="application/json"
                )
                sender.send_messages(sb_message)
                logging.info(f"Message published to queue '{queue_name}'")
                return True
    except Exception as e:
        logging.exception(f"Failed to publish to Service Bus queue '{queue_name}': {e}")
        return False
