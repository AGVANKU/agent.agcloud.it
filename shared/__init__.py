"""
Shared utilities used across webhooks, agents, and tools layers.
"""

from shared.util_responses import json_response
from shared.util_config import get_config

__all__ = [
    "json_response",
    "get_config",
]
