"""
Tools Blueprint - HTTP endpoints for agent capabilities.

Route pattern: /api/tools/{resource_type}
- GET: Query/retrieve resources
- POST: Create/execute operations
- DELETE: Remove resources
"""

import azure.functions as func
import azure.durable_functions as df
import logging

from shared import json_response

bp = df.Blueprint()


# =============================================================================
# ROUTE CONFIGURATION
# =============================================================================

ROUTES = {
    # Add tool routes here:
    # "resource_type": {
    #     "handler": handler_function,
    #     "info_handler": info_function,
    #     "delete_handler": delete_function,
    # },
}


# =============================================================================
# HTTP TRIGGERS
# =============================================================================

@bp.route(route="tools/{*resource_path}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
@bp.durable_client_input(client_name="client")
async def tools_api_handler(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    """
    HTTP handler for GET requests on tools routes.

    GET without params -> returns resource info/schema
    GET with ?id=xxx   -> returns specific resource info
    """
    resource_type = req.route_params.get('resource_path')
    logging.info(f"Tools API request: GET /tools/{resource_type}")

    # Status endpoint for durable orchestrations
    if resource_type and resource_type.startswith('status/'):
        instance_id = resource_type.replace('status/', '', 1)
        status = await client.get_status(instance_id)

        if not status:
            return json_response({"error": f"Instance not found: {instance_id}"}, 404)

        return json_response({
            "instance_id": instance_id,
            "runtime_status": status.runtime_status.name if status.runtime_status else None,
            "output": status.output,
            "created_time": status.created_time.isoformat() if status.created_time else None,
            "last_updated_time": status.last_updated_time.isoformat() if status.last_updated_time else None,
        })

    config = ROUTES.get(resource_type)
    if not config:
        return json_response({"error": f"Unknown resource type: {resource_type}"}, 404)

    # Check for query parameter lookup
    query_param = config.get("query_param", "id")
    param_value = req.params.get(query_param)

    if param_value:
        handler_fn = config.get("info_handler") or config.get("handler")
        if not handler_fn:
            return json_response({"error": f"Info lookup not supported for {resource_type}"}, 400)
        result = handler_fn(param_value)
        return json_response(result, result.get('status_code', 200))

    return json_response({"error": f"Missing '{query_param}' query parameter"}, 400)


@bp.route(route="tools/{*resource_path}", methods=["POST", "DELETE"], auth_level=func.AuthLevel.FUNCTION)
@bp.durable_client_input(client_name="client")
async def tools_post_delete_handler(req: func.HttpRequest, client: df.DurableOrchestrationClient) -> func.HttpResponse:
    """HTTP handler for POST/DELETE on tools routes."""
    resource_type = req.route_params.get('resource_path')
    method = req.method

    logging.info(f"Tools request: {method} /tools/{resource_type}")

    try:
        req_body = req.get_json()
    except Exception as e:
        return json_response({"error": f"Invalid JSON: {e}"}, 400)

    config = ROUTES.get(resource_type)
    if not config:
        return json_response({"error": f"Unknown resource type: {resource_type}"}, 404)

    if method == "DELETE":
        delete_handler = config.get("delete_handler")
        if not delete_handler:
            return json_response({"error": f"Delete not supported for {resource_type}"}, 405)
        result = delete_handler(req_body)
        return json_response(result, result.get('status_code', 200))

    handler = config.get("handler")
    if not handler:
        return json_response({"error": f"POST not supported for {resource_type}"}, 405)

    result = handler(req_body)
    return json_response(result, result.get('status_code', 200))
