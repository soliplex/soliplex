"""GenUI Agent with AG-UI State Support.

This module provides an agent factory for the GenUI room that supports
the AG-UI StateHandler protocol, allowing the client to send canvas state
with each request.

The key insight: pydantic-ai's AG-UI adapter passes `instructions` to
run_stream_events(). We don't need a custom wrapper agent - we just need:
1. A deps type that implements StateHandler (dataclass with `state` field)
2. Build dynamic instructions in views/agui.py based on deps.state
3. Pass instructions to adapter.run_stream()

See BACKEND-REQUEST.md for investigation notes.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import pydantic_ai
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import openai as openai_providers

from soliplex import config


@dataclasses.dataclass
class GenUIDependencies:
    """Dependencies for GenUI agent that implements StateHandler protocol.

    The `state` field is required by pydantic-ai's StateHandler protocol.
    AG-UI will inject the client's state into this field for each run.
    """
    the_installation: Any
    user: Any = None
    tool_configs: config.ToolConfigMap = None
    agui_emitter: Any = None
    state: dict[str, Any] = dataclasses.field(default_factory=dict)


def format_canvas_state(state: dict[str, Any]) -> str:
    """Format canvas state for inclusion in system prompt.

    This is called from views/agui.py when building dynamic instructions.
    """
    canvas_items = state.get("canvas", [])

    if not canvas_items:
        return "[Canvas is empty]"

    lines = ["[Current canvas contents for context - do not output this, use for reference only]"]

    for item in canvas_items:
        widget = item.get("widget", "Unknown")
        data = item.get("data", {})
        item_id = item.get("id", "?")

        # Format based on widget type
        if widget == "SkillsCard":
            name = data.get("name", "Unknown")
            lines.append(f"- {name} (id={item_id})")
        elif widget == "ProjectCard":
            title = data.get("title", "Unknown Project")
            lines.append(f"- {title} (id={item_id})")
        elif widget == "InfoCard":
            title = data.get("title", "Info")
            lines.append(f"- {title} (id={item_id})")
        else:
            lines.append(f"- {widget} (id={item_id})")

    return "\n".join(lines)


def genui_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
) -> pydantic_ai.Agent:
    """Factory function to create a GenUI agent with state support.

    Returns a standard pydantic_ai.Agent with GenUIDependencies.
    Dynamic instructions (including canvas state) are built in views/agui.py.
    """
    installation_config = agent_config._installation_config

    # Get provider configuration
    extra = agent_config.extra_config or {}

    provider_base_url = extra.get(
        "provider_base_url",
        installation_config.get_environment("OLLAMA_BASE_URL"),
    )

    provider_kw = {"base_url": f"{provider_base_url}/v1"}

    provider_key = extra.get("provider_key")
    if provider_key:
        provider_kw["api_key"] = installation_config.get_secret(provider_key)

    provider = openai_providers.OpenAIProvider(**provider_kw)

    # Get model name
    model_name = extra.get(
        "model_name",
        installation_config.get_environment("DEFAULT_AGENT_MODEL", "gpt-oss:20b"),
    )

    # Get base system prompt from file - this becomes the static instructions
    # Dynamic canvas state is added in views/agui.py
    base_prompt = ""
    config_path = agent_config._config_path
    if config_path:
        prompt_file = config_path.parent / extra.get("system_prompt", "./prompt.txt")
        if prompt_file.is_file():
            base_prompt = prompt_file.read_text()

    # Store base_prompt on the agent for views/agui.py to access
    agent: pydantic_ai.Agent[GenUIDependencies, Any] = pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name=model_name,
            provider=provider,
        ),
        deps_type=GenUIDependencies,
        instructions=base_prompt,  # Static base prompt
    )

    # Attach base_prompt for dynamic instruction building in views/agui.py
    agent._genui_base_prompt = base_prompt

    return agent
