"""
Agents Blueprint - AI agent orchestration layer with Durable Functions.

Structure:
- agents.py                     -> Blueprint + Service Bus triggers (this file)
- orchestrators/orchestrator_main.py -> Main orchestrator
- app/activity_workflow.py      -> Unified agent execution activity
- app/activity_queue.py         -> Queue message activity
"""

import json
import logging
import azure.functions as func
import azure.durable_functions as df

from shared import json_response
from webhooks.utility.util_service_bus import ensure_queue_exists


# =============================================================================
# BLUEPRINT
# =============================================================================

bp = df.Blueprint()


# =============================================================================
# SERVICE BUS QUEUE INITIALIZATION
# =============================================================================

REQUIRED_QUEUES = [
    "webhook-ingest",
    "agent-orchestrator",
    "agent-tasks",
    "agent-results",
]
for queue_name in REQUIRED_QUEUES:
    ensure_queue_exists(queue_name)


# =============================================================================
# SERVICE BUS TRIGGERS
# =============================================================================

@bp.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="agent-orchestrator",
    connection="SERVICE_BUS_CONNECTION_STRING"
)
@bp.durable_client_input(client_name="client")
async def orchestrator_queue_consumer(msg: func.ServiceBusMessage, client: df.DurableOrchestrationClient):
    """
    Main orchestrator queue consumer.
    Receives triage requests and starts the main orchestration.
    """
    try:
        body = json.loads(msg.get_body().decode('utf-8'))
        event_type = body.get("event_type", "unknown")
        event_id = body.get("event_id", "unknown")

        logging.info(f"Orchestrator queue: event_type={event_type}, event_id={event_id}")

        instance_id = f"orchestrate-{event_type}-{event_id}"

        # Check if already running
        status = await client.get_status(instance_id)
        if status and status.runtime_status in [
            df.OrchestrationRuntimeStatus.Running,
            df.OrchestrationRuntimeStatus.Pending,
        ]:
            logging.warning(f"Orchestration {instance_id} already running")
            return

        await client.start_new(
            "main_orchestrator",
            instance_id=instance_id,
            client_input=body
        )

        logging.info(f"Started orchestration: {instance_id}")

    except Exception as e:
        logging.exception(f"Failed to process orchestrator queue message: {e}")
        raise


@bp.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="agent-tasks",
    connection="SERVICE_BUS_CONNECTION_STRING"
)
@bp.durable_client_input(client_name="client")
async def task_queue_consumer(msg: func.ServiceBusMessage, client: df.DurableOrchestrationClient):
    """
    Task queue consumer.
    Receives sub-agent task requests from the orchestrator.
    """
    try:
        body = json.loads(msg.get_body().decode('utf-8'))
        agent_type = body.get("agent_type")
        task_id = body.get("task_id", "unknown")

        logging.info(f"Task queue: agent={agent_type}, task_id={task_id}")

        instance_id = f"task-{agent_type}-{task_id}"

        status = await client.get_status(instance_id)
        if status and status.runtime_status in [
            df.OrchestrationRuntimeStatus.Running,
            df.OrchestrationRuntimeStatus.Pending,
        ]:
            logging.warning(f"Task orchestration {instance_id} already running")
            return

        await client.start_new(
            "main_orchestrator",
            instance_id=instance_id,
            client_input=body
        )

        logging.info(f"Started task orchestration: {instance_id}")

    except Exception as e:
        logging.exception(f"Failed to process task queue message: {e}")
        raise


@bp.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="agent-results",
    connection="SERVICE_BUS_CONNECTION_STRING"
)
async def result_queue_consumer(msg: func.ServiceBusMessage):
    """
    Results queue consumer.
    Receives completed task results for logging and downstream processing.
    """
    try:
        body = json.loads(msg.get_body().decode('utf-8'))
        agent_type = body.get("agent_type", "unknown")
        status = body.get("status", "unknown")

        logging.info(f"Result received: agent={agent_type}, status={status}")

        # Log to Cosmos DB for audit trail
        try:
            from shared.util_cosmos import log_event
            log_event("agent-events", {
                "event_type": "agent_result",
                **body
            })
        except Exception as e:
            logging.warning(f"Failed to log result to Cosmos: {e}")

    except Exception as e:
        logging.exception(f"Failed to process result queue message: {e}")
        raise


# =============================================================================
# HTTP TRIGGERS (testing/management)
# =============================================================================

@bp.route(route="agents/status/{instanceId}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
@bp.durable_client_input(client_name="client")
async def get_orchestration_status(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    """Get orchestration status."""
    instance_id = req.route_params.get("instanceId")

    if not instance_id:
        return json_response({"error": "Missing instanceId"}, 400)

    status = await client.get_status(instance_id)

    if not status:
        return json_response({"error": "Instance not found"}, 404)

    return json_response({
        "instance_id": instance_id,
        "runtime_status": status.runtime_status.name,
        "output": status.output,
    })


# =============================================================================
# IMPORT MODULES - Their decorators register on bp when imported
# =============================================================================

from agents.orchestrators import orchestrator_main      # noqa: F401, E402
from agents.app import activity_workflow                 # noqa: F401, E402
from agents.app import activity_queue                    # noqa: F401, E402
