from __future__ import annotations

import inspect

from agent_framework import Agent, AgentResponse
from agent_framework.foundry import FoundryChatClient


def test_pinned_agent_framework_supports_structured_run_options() -> None:
    run_parameters = inspect.signature(Agent.run).parameters
    assert "options" in run_parameters
    assert hasattr(AgentResponse, "value")
    client_parameters = inspect.signature(FoundryChatClient).parameters
    assert {"project_endpoint", "model", "credential"} <= set(client_parameters)
