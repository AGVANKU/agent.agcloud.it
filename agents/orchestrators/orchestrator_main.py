"""
Main Orchestrator - Triage incoming events and route to appropriate agents.

Flow:
1. Receive event from queue (webhook-ingest or agent-orchestrator)
2. Run triage agent to classify and route
3. Execute routed agent via activity
4. Queue results or next action
"""

import json
import logging

from agents.agents import bp


@bp.orchestration_trigger(context_name="context")
def main_orchestrator(context):
    """
    Main orchestration flow.

    Input: dict with event_type, event_id, payload, etc.
    """
    input_data = context.get_input()
    event_type = input_data.get("event_type", "unknown")

    logging.info(f"Main orchestrator started: event_type={event_type}")

    # Step 1: Triage - determine which agent should handle this
    triage_result = yield context.call_activity(
        "run_agent_workflow",
        {
            "agent_type": "triage",
            "payload": input_data,
        }
    )

    if triage_result.get("status") == "error":
        logging.error(f"Triage failed: {triage_result.get('reason')}")
        return {"status": "error", "reason": triage_result.get("reason")}

    # Step 2: Check for next_action routing
    next_action = triage_result.get("next_action")
    if next_action:
        target_queue = next_action.get("target_queue")
        payload = next_action.get("payload", {})

        if target_queue and target_queue != "none":
            yield context.call_activity(
                "queue_message",
                {"queue": target_queue, "payload": payload}
            )
            logging.info(f"Routed to queue: {target_queue}")

    return {
        "status": "completed",
        "event_type": event_type,
        "triage_result": triage_result,
    }
