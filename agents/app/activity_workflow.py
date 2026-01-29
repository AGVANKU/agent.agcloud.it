"""
Unified Agent Workflow Activity - Standardized agent execution.

Single activity that can run any agent type with consistent:
- Input handling (AgentWorkflowInput)
- Agent execution via pluggable AI backend
- Output with routing (AgentResponse with next_action)
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime

from agents.agents import bp
from agents.utility.util_classes import AgentResponse, AgentWorkflowInput, NextAction
from agents.utility.util_agents import get_backend


@bp.activity_trigger(input_name="workflowInput")
def run_agent_workflow(workflowInput: dict) -> dict:
    """
    Universal agent execution activity.

    Input (AgentWorkflowInput):
    - agent_type: Which agent to run ("triage", etc.)
    - payload: All input data for the agent

    Output: dict representation of AgentResponse
    """
    input_data = AgentWorkflowInput(
        agent_type=workflowInput.get("agent_type"),
        payload=workflowInput.get("payload", {})
    )

    agent_type = input_data.agent_type
    logging.info(f"Running agent workflow: {agent_type}")

    started_at = datetime.utcnow()

    try:
        # Load system prompt
        system_prompt = _load_system_prompt(agent_type)

        # Get AI backend
        backend = get_backend()

        # Execute agent
        messages = [{"role": "user", "content": json.dumps(input_data.payload)}]
        agent_response = backend.execute(
            system_prompt=system_prompt,
            messages=messages,
            tools=[]  # Add per-agent tools here
        )

        if not agent_response:
            logging.error(f"No response from agent: {agent_type}")
            return asdict(AgentResponse(
                status="error",
                responses=[],
                reason=f"No response from agent: {agent_type}",
                agent_type=agent_type
            ))

        # Enrich response with workflow metadata
        agent_response.agent_type = agent_type
        agent_response.next_action = _determine_next_action(agent_type, agent_response)

        # Track token usage
        _track_usage(agent_response, agent_type, started_at)

        logging.info(
            f"Agent workflow completed: {agent_type} | status={agent_response.status} | "
            f"responses={len(agent_response.responses)} | "
            f"next={agent_response.next_action.target_queue if agent_response.next_action else 'none'}"
        )

        return asdict(agent_response)

    except Exception as e:
        logging.exception(f"Agent workflow failed: {agent_type}")
        return asdict(AgentResponse(
            status="error",
            responses=[],
            reason=str(e),
            agent_type=agent_type
        ))


def _load_system_prompt(agent_type: str) -> str:
    """Load system prompt from instructions directory."""
    from pathlib import Path

    instructions_dir = Path(__file__).parent.parent / "instructions"
    prompt_file = instructions_dir / f"{agent_type}.system.md"

    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")

    logging.warning(f"No system prompt found for agent: {agent_type}")
    return f"You are a {agent_type} agent. Process the input and return a JSON response."


def _determine_next_action(agent_type: str, response: AgentResponse) -> NextAction | None:
    """Extract routing decision from agent response."""
    first_response = response.responses[0] if response.responses else {}

    if isinstance(first_response, dict) and 'raw' in first_response:
        first_response = first_response['raw']

    if isinstance(first_response, str):
        try:
            first_response = json.loads(first_response)
        except json.JSONDecodeError:
            logging.warning(f"Agent {agent_type} returned non-JSON response")
            return None

    agent_next_action = first_response.get("next_action") if isinstance(first_response, dict) else None

    if not agent_next_action or not isinstance(agent_next_action, dict):
        return None

    target_queue = agent_next_action.get("target_queue")
    if not target_queue or target_queue == "none":
        return None

    payload = agent_next_action.get("payload", {})
    logging.info(f"Agent {agent_type} routing to: {target_queue}")
    return NextAction(target_queue=target_queue, payload=payload)


def _track_usage(response: AgentResponse, agent_type: str, started_at: datetime) -> None:
    """Track token usage (fail-safe)."""
    try:
        if response.usage:
            from shared.util_token_tracking import track_token_usage
            track_token_usage(
                model_name=response.model_name or "unknown",
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                agent_type=agent_type,
                started_at=started_at,
                inference_rounds=response.inference_rounds,
            )
    except Exception as e:
        logging.warning(f"Failed to track token usage: {e}")
