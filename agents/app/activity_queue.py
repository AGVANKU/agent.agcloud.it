"""
Queue Message Activity - Send messages to Service Bus queues.
"""

import json
import logging
import os
import time

from azure.servicebus import ServiceBusClient, ServiceBusMessage

from agents.agents import bp

SERVICE_BUS_CONNECTION_STRING = os.environ.get("SERVICE_BUS_CONNECTION_STRING")


@bp.activity_trigger(input_name="queueInput")
def queue_message(queueInput: dict) -> dict:
    """
    Generic activity to send a message to any Service Bus queue.

    Input:
    - queue: Target queue name
    - payload: Message body (dict)
    """
    queue_name = queueInput.get("queue")
    payload = queueInput.get("payload", {})

    if not queue_name:
        return {"status": "error", "reason": "No queue name provided"}

    if not SERVICE_BUS_CONNECTION_STRING:
        logging.error("SERVICE_BUS_CONNECTION_STRING not configured")
        return {"status": "error", "reason": "Service Bus not configured"}

    max_retries = 3
    retry_delays = [2, 5, 10]

    for attempt in range(max_retries):
        try:
            with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
                with client.get_queue_sender(queue_name) as sender:
                    sb_message = ServiceBusMessage(
                        body=json.dumps(payload),
                        content_type="application/json"
                    )
                    sender.send_messages(sb_message)
                    logging.info(f"Queued message to '{queue_name}' (attempt {attempt + 1})")
                    return {"status": "success", "queue": queue_name, "attempts": attempt + 1}
        except Exception as e:
            is_last_attempt = (attempt == max_retries - 1)
            if is_last_attempt:
                logging.exception(f"Failed to queue message to '{queue_name}' after {max_retries} attempts: {e}")
                return {"status": "error", "reason": str(e), "attempts": max_retries}
            else:
                delay = retry_delays[attempt]
                logging.warning(f"Queue attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)
