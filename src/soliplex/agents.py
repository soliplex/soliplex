from __future__ import annotations

import abc
import dataclasses
import datetime
import typing
import uuid

import pydantic_ai
from haiku.skills import agent as hs_agent
from haiku.skills import prompts as hs_prompts
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
from soliplex import mcp_client
from soliplex import models
from soliplex.config import agents as config_agents
from soliplex.config import tools as config_tools

ToolConfigMap = dict[str, typing.Any]

DEFAULT_PRINCIPAL_MAX_DURATION = 300


@dataclasses.dataclass(frozen=True)
class AgentPrincipal:
    """Unique identity for an agent run execution."""

    principal_id: str
    parent_principal_id: str | None
    user_email: str
    user_username: str
    room_id: str
    created_at: datetime.datetime
    expires_at: datetime.datetime

    @classmethod
    def mint(
        cls,
        user: models.UserProfile,
        room_id: str,
        max_duration_seconds: int = DEFAULT_PRINCIPAL_MAX_DURATION,
        parent_principal_id: str | None = None,
    ) -> AgentPrincipal:
        now = datetime.datetime.now(datetime.UTC)
        return cls(
            principal_id=str(uuid.uuid4()),
            parent_principal_id=parent_principal_id,
            user_email=user.email,
            user_username=user.preferred_username,
            room_id=room_id,
            created_at=now,
            expires_at=now
            + datetime.timedelta(
                seconds=max_duration_seconds,
            ),
        )


class SkillToolsetConfig(typing.Protocol):
    # contract for config.RoomSkillsConfig etc.
    @abc.abstractproperty
    def skill_toolset(self) -> hs_agent.SkillToolset: ...


@dataclasses.dataclass
class AgentDependencies:
    """Agent dependencies implementing StateHandler protocol.

    The `state` field is required by pydantic-ai's StateHandler protocol.
    AG-UI will inject the client's state into this field for each run.
    """

    the_installation: typing.Any  # installation.Installation
    user: models.UserProfile
    principal: AgentPrincipal | None = None
    tool_configs: ToolConfigMap = None
    thread_id: str | None = None
    state: agui.AGUI_State = dataclasses.field(default_factory=dict)


SoliplexAgent = ai_agent.AbstractAgent[AgentDependencies, typing.Any]


class AgentFactory(typing.Protocol):
    def __call__(
        self,
        *,
        tool_configs: ToolConfigMap,
        mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap,
        skill_toolset_config: SkillToolsetConfig | None = None,
    ) -> SoliplexAgent: ...


# Cache for agents to avoid recreating them
_agent_cache: dict[str, pydantic_ai.Agent] = {}


def make_ai_tool(tool_config: config_tools.ToolConfig) -> ai_tools.Tool:
    tool_func = tool_config.tool_with_config

    return ai_tools.Tool(
        tool_func,
        name=tool_config.tool_id,
    )


def make_mcp_client_toolset(
    toolset_config: config_tools.MCP_ClientToolsetConfig,
) -> ai_mcp.MCPServer:
    toolset_klass = mcp_client.TOOLSET_CLASS_BY_KIND[toolset_config.kind]
    return toolset_klass(**toolset_config.tool_kwargs)


def get_model_from_config(
    *,
    agent_config: config_agents.AgentConfig,
) -> ai_models.Model:
    provider_kw = agent_config.llm_provider_kw

    if agent_config.provider_type == config_agents.LLMProviderType.GOOGLE:
        provider = google_providers.GoogleProvider(**provider_kw)
        return google_models.GoogleModel(
            model_name=agent_config.model_name,
            provider=provider,
        )

    elif agent_config.provider_type == config_agents.LLMProviderType.OLLAMA:
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
    agent_config: config_agents.AgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap,
    skill_toolset_config: SkillToolsetConfig | None = None,
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

    if skill_toolset_config is not None:
        toolset = skill_toolset_config.skill_toolset
        toolsets.append(toolset)
        instructions = hs_prompts.build_system_prompt(
            preamble=agent_config.get_system_prompt(),
            skill_catalog=toolset.skill_catalog,
        )
    else:
        instructions = agent_config.get_system_prompt()

    return pydantic_ai.Agent(
        model=model,
        model_settings=agent_config.model_settings,
        tools=tools,
        toolsets=toolsets,
        instructions=instructions,
        deps_type=AgentDependencies,
    )


def get_agent_from_configs(
    *,
    agent_config: config_agents.AgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap,
    skill_toolset_config: SkillToolsetConfig | None = None,
) -> SoliplexAgent:
    """Get or create an agent from the specified agent and tool configs."""

    if agent_config.id not in _agent_cache:
        if agent_config.kind == "default":
            agent = get_default_agent_from_configs(
                agent_config=agent_config,
                tool_configs=tool_configs,
                mcp_client_toolset_configs=mcp_client_toolset_configs,
                skill_toolset_config=skill_toolset_config,
            )

        else:
            # Treat 'agent_config' as an 'AgentFactory'
            agent = agent_config.factory(
                tool_configs=tool_configs,
                mcp_client_toolset_configs=mcp_client_toolset_configs,
                skill_toolset_config=skill_toolset_config,
            )

        _agent_cache[agent_config.id] = agent

    return _agent_cache[agent_config.id]
