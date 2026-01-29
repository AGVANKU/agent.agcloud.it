"""
Dataclasses for agent orchestration.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class NextAction:
    """What the orchestrator should queue next."""
    target_queue: str    # "agent-tasks" | "agent-results" | "none"
    payload: dict        # Message body for the queue


@dataclass
class AgentWorkflowInput:
    """Standardized input for the workflow activity."""
    agent_type: str      # "triage", etc.
    payload: dict        # All agent input data


@dataclass
class AgentResponse:
    """Agent execution result + workflow routing."""
    status: str
    responses: list[dict]
    thread_id: str | None = None
    reason: str | None = None
    usage: TokenUsage | None = None
    tool_calls: int = 0
    inference_rounds: int = 0
    agent_type: str | None = None
    model_name: str | None = None
    next_action: NextAction | None = None

    @classmethod
    def from_dict(cls, data: dict) -> 'AgentResponse':
        """Convert dict back to AgentResponse object."""
        return cls(
            status=data.get("status", "error"),
            responses=data.get("responses", []),
            thread_id=data.get("thread_id"),
            reason=data.get("reason"),
            usage=TokenUsage(**data["usage"]) if data.get("usage") else None,
            tool_calls=data.get("tool_calls", 0),
            inference_rounds=data.get("inference_rounds", 0),
            agent_type=data.get("agent_type"),
            model_name=data.get("model_name"),
            next_action=NextAction(**data["next_action"]) if data.get("next_action") else None
        )


@dataclass
class LoadedTools:
    """Tool definitions and executors for an agent."""
    definitions: list[dict] = field(default_factory=list)
    executors: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def __add__(self, other: 'LoadedTools') -> 'LoadedTools':
        if not isinstance(other, LoadedTools):
            return NotImplemented
        combined_definitions = (other.definitions or []) + (self.definitions or [])
        combined_executors = {**(self.executors or {}), **(other.executors or {})}
        return LoadedTools(
            definitions=combined_definitions,
            executors=combined_executors
        )
