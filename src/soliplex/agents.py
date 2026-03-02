from __future__ import annotations

import dataclasses
import typing
from collections import abc

import pydantic_ai
from pydantic_ai import agent as ai_agent
from pydantic_ai import mcp as ai_mcp
from pydantic_ai import models as ai_models
from pydantic_ai import tools as ai_tools
from pydantic_ai.models import google as google_models
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import google as google_providers
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers

from soliplex import agui
from soliplex import config
from soliplex import mcp_client
from soliplex import models

ToolConfigMap = dict[str, typing.Any]


@dataclasses.dataclass
class AgentDependencies:
    """Agent dependencies implementing StateHandler protocol.

    The `state` field is required by pydantic-ai's StateHandler protocol.
    AG-UI will inject the client's state into this field for each run.
    """

    the_installation: typing.Any  # installation.Installation
    user: models.UserProfile = None  # TBD make required
    tool_configs: ToolConfigMap = None
    thread_id: str | None = None
    state: agui.AGUI_State = dataclasses.field(default_factory=dict)


SoliplexAgent = ai_agent.AbstractAgent[AgentDependencies, typing.Any]
AgentFactory = abc.Callable[
    [
        config.AgentConfig,
        ToolConfigMap,
        config.MCP_ClientToolsetConfigMap,
    ],
    SoliplexAgent,
]

# Cache for agents to avoid recreating them
_agent_cache: dict[str, pydantic_ai.Agent] = {}


def make_ai_tool(tool_config: config.ToolConfig) -> ai_tools.Tool:
    tool_func = tool_config.tool_with_config

    return ai_tools.Tool(
        tool_func,
        name=tool_config.tool_id,
    )


def make_mcp_client_toolset(
    toolset_config: config.MCP_ClientToolsetConfig,
) -> ai_mcp.MCPServer:
    toolset_klass = mcp_client.TOOLSET_CLASS_BY_KIND[toolset_config.kind]
    return toolset_klass(**toolset_config.tool_kwargs)


def get_model_from_config(
    *,
    agent_config: config.AgentConfig,
) -> ai_models.Model:
    provider_kw = agent_config.llm_provider_kw

    if agent_config.provider_type == config.LLMProviderType.GOOGLE:
        provider = google_providers.GoogleProvider(**provider_kw)
        return google_models.GoogleModel(
            model_name=agent_config.model_name,
            provider=provider,
        )

    elif agent_config.provider_type == config.LLMProviderType.OLLAMA:
        provider_kw["api_key"] = "dummy"
        provider = ollama_providers.OllamaProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=agent_config.model_name,
            provider=provider,
        )
    else:
        provider = openai_providers.OpenAIProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=agent_config.model_name,
            provider=provider,
        )


def get_default_agent_from_configs(
    *,
    agent_config: config.AgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap,
) -> SoliplexAgent:
    """Build a Pydantic AI agent from a config"""
    model = get_model_from_config(agent_config=agent_config)

    tools = [
        make_ai_tool(tool_config) for tool_config in tool_configs.values()
    ]
    toolsets = [
        make_mcp_client_toolset(mctc)
        for mctc in mcp_client_toolset_configs.values()
    ]

    return pydantic_ai.Agent(
        model=model,
        model_settings=agent_config.model_settings,
        tools=tools,
        toolsets=toolsets,
        instructions=agent_config.get_system_prompt(),
        deps_type=AgentDependencies,
    )


def get_agent_from_configs(
    *,
    agent_config: config.AgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap,
) -> SoliplexAgent:
    """Get or create an agent from the specified agent and tool configs."""

    if agent_config.id not in _agent_cache:
        if agent_config.kind == "default":
            agent = get_default_agent_from_configs(
                agent_config=agent_config,
                tool_configs=tool_configs,
                mcp_client_toolset_configs=mcp_client_toolset_configs,
            )

        else:
            agent = agent_config.factory(
                tool_configs=tool_configs,
                mcp_client_toolset_configs=mcp_client_toolset_configs,
            )

        _agent_cache[agent_config.id] = agent

    return _agent_cache[agent_config.id]
