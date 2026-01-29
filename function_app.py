"""
AG Cloud Agent Platform

Main Function App entry point that registers all blueprints:

1. WEBHOOKS - Ingest layer for external events (HTTP, Timer triggers)
   Routes: /api/webhooks/*
   Publishes events to Service Bus for async processing

2. AGENTS - AI agent orchestration layer
   Routes: /api/agents/*
   Consumes Service Bus, manages agents, orchestrates workflows

3. TOOLS - Agent capabilities layer
   Routes: /api/tools/*
   HTTP endpoints that agents can call to perform actions
"""

import json
import logging
import azure.functions as func
import azure.durable_functions as df

# Import blueprints from each layer
from webhooks.webhooks import bp as webhooks_bp
from agents.agents import bp as agents_bp
from tools.tools import bp as tools_bp

# Initialize database tables on startup
try:
    from shared.util_token_tracking import ensure_token_usage_table
    ensure_token_usage_table()
except Exception as e:
    logging.warning(f"Could not initialize token usage table: {e}")

# Create main app with Durable Functions support
app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

# Register all blueprints (order: webhooks -> agents -> tools)
app.register_functions(webhooks_bp)
app.register_functions(agents_bp)
app.register_functions(tools_bp)


# =============================================================================
# HEALTH CHECK (root level)
# =============================================================================

@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Root health check endpoint."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "app": "agent-agcloud",
            "layers": ["webhooks", "agents", "tools"]
        }),
        mimetype="application/json"
    )
