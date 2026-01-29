"""
Pluggable AI backend for agent execution.

Supports multiple backends via the AIBackend protocol:
- AzureOpenAIBackend: Azure OpenAI Service (default)
- Add more backends as needed (e.g., Azure AI Agents, local models)

Selected via AI_BACKEND environment variable.
"""

import json
import logging
import os
from typing import Protocol, runtime_checkable

from agents.utility.util_classes import AgentResponse, TokenUsage


@runtime_checkable
class AIBackend(Protocol):
    """Protocol for pluggable AI backends."""

    def execute(self, system_prompt: str, messages: list, tools: list) -> AgentResponse:
        """Execute an agent with the given prompt, messages, and tools."""
        ...


class AzureOpenAIBackend:
    """Azure OpenAI Service backend."""

    def __init__(self):
        from openai import AzureOpenAI

        self.client = AzureOpenAI(
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    def execute(self, system_prompt: str, messages: list, tools: list) -> AgentResponse:
        """Execute agent via Azure OpenAI chat completion."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        kwargs = {
            "model": self.deployment,
            "messages": full_messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            content = choice.message.content or ""

            usage = None
            if response.usage:
                usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )

            return AgentResponse(
                status="success",
                responses=[content],
                usage=usage,
                model_name=self.deployment,
                tool_calls=len(choice.message.tool_calls) if choice.message.tool_calls else 0,
                inference_rounds=1,
            )

        except Exception as e:
            logging.exception(f"Azure OpenAI execution failed: {e}")
            return AgentResponse(
                status="error",
                responses=[],
                reason=str(e),
                model_name=self.deployment,
            )


class AzureAIAgentsBackend:
    """Azure AI Agents Service backend (placeholder)."""

    def execute(self, system_prompt: str, messages: list, tools: list) -> AgentResponse:
        """Execute agent via Azure AI Agents Service."""
        raise NotImplementedError("Azure AI Agents backend not yet implemented")


# =============================================================================
# FACTORY
# =============================================================================

_backend_instance = None


def get_backend() -> AIBackend:
    """Get the configured AI backend (cached singleton)."""
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    backend_type = os.environ.get("AI_BACKEND", "azure_openai")

    if backend_type == "azure_openai":
        _backend_instance = AzureOpenAIBackend()
    elif backend_type == "azure_ai_agents":
        _backend_instance = AzureAIAgentsBackend()
    else:
        logging.warning(f"Unknown AI_BACKEND '{backend_type}', defaulting to azure_openai")
        _backend_instance = AzureOpenAIBackend()

    logging.info(f"AI backend initialized: {backend_type}")
    return _backend_instance
