from __future__ import annotations

import dataclasses
import typing

import pydantic_ai
from haiku.rag.capabilities import analysis as hr_caps_analysis
from haiku.rag.capabilities import rag as hr_caps_rag
from pydantic_ai import agent as ai_agent
from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import tools as ai_tools
from pydantic_ai import toolsets as ai_toolsets

from soliplex import agui
from soliplex import mcp_client
from soliplex import models
from soliplex.capabilities import rag_audit as cap_rag_audit
from soliplex.config import agents as config_agents
from soliplex.config import tools as config_tools

ToolConfigMap = dict[str, typing.Any]

# Capabilities which take 'vision' from agent config's 'multimodal'
HR_VisionCapabilities = (
    hr_caps_rag.RAGCapability | hr_caps_analysis.AnalysisCapability
)


class CapabilityConfig(typing.Protocol):
    """Room-specific native capabilities and their audit targets."""

    @property
    def capabilities(self) -> list[ai_capabilities.AbstractCapability]: ...

    @property
    def rag_db_paths(self) -> dict[str, str]: ...


@dataclasses.dataclass
class AgentDependencies:
    """Agent dependencies implementing StateHandler protocol.

    The `state` field is required by pydantic-ai's StateHandler protocol.
    AG-UI will inject the client's state into this field for each run.
    """

    the_installation: typing.Any  # installation.Installation
    the_threads: agui.ThreadStorage = None
    state: agui.AGUI_State = dataclasses.field(default_factory=dict)
    room_id: str | None = None
    thread_id: str | None = None
    run_id: str | None = None
    user: models.UserProfile = None  # TBD make required
    tool_configs: ToolConfigMap = None


SoliplexAgent = ai_agent.AbstractAgent[AgentDependencies, typing.Any]


class AgentFactory(typing.Protocol):
    def __call__(
        self,
        *,
        tool_configs: ToolConfigMap,
        mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap,
        capability_config: CapabilityConfig | None = None,
    ) -> SoliplexAgent: ...


def make_ai_tool(tool_config: config_tools.ToolConfig) -> ai_tools.Tool:
    tool_func = tool_config.tool_with_config

    ai_tool_params = tool_config.ai_tool_params

    if "name" not in ai_tool_params:
        ai_tool_params["name"] = tool_config.tool_id

    return ai_tools.Tool(tool_func, **ai_tool_params)


def make_mcp_client_toolset(
    toolset_config: config_tools.MCP_ClientToolsetConfig,
) -> ai_toolsets.AbstractToolset:
    factory = mcp_client.TOOLSET_FACTORY_BY_KIND[toolset_config.kind]
    return factory(**toolset_config.tool_kwargs)


def _is_routing_capability(
    capability: ai_capabilities.AbstractCapability,
) -> bool:
    """Whether the model has anything to load from this capability.

    Tools or instructions are what there is to route between; a hook-only
    capability offers neither.
    """
    if capability.get_instructions() or capability.get_native_tools():
        return True

    toolset = capability.get_toolset()

    if toolset is None:
        return False

    # A capability registering no tools of its own still gets an empty
    # 'FunctionToolset', so ask whether it is empty, not whether it exists.
    return bool(getattr(toolset, "tools", True))


def get_default_agent_from_configs(
    *,
    agent_config: config_agents.AgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap,
    capability_config: CapabilityConfig | None = None,
) -> SoliplexAgent:
    """Build a Pydantic AI agent from a config"""
    model = config_agents.get_model_from_config(agent_config=agent_config)

    tools = [
        make_ai_tool(tool_config) for tool_config in tool_configs.values()
    ]
    toolsets = [
        make_mcp_client_toolset(mctc)
        for mctc in mcp_client_toolset_configs.values()
    ]

    capabilities = list(agent_config.capabilities)
    if capability_config is not None:
        capabilities.extend(capability_config.capabilities)
        if capability_config.rag_db_paths:
            capabilities.append(
                cap_rag_audit.RAGAccessAuditCapability(
                    id="soliplex-rag-access-audit",
                    db_paths=capability_config.rag_db_paths,
                )
            )

    # RAG/analysis capabilities attach picture chunks to search results as
    # images only when the receiving model accepts them. That model is this
    # agent's model, not haiku.rag's configured model, so gate on the room
    # agent's declared multimodality.
    for capability in capabilities:
        if isinstance(capability, HR_VisionCapabilities):
            capability.vision = agent_config.multimodal

    # A single model-facing capability loads eagerly so its tools are visible;
    #
    # Multiple stay deferred so the model routes between them via
    # 'load_capability'.
    routing_capabilities = [
        capability
        for capability in capabilities
        if _is_routing_capability(capability)
    ]
    defer_loading = len(routing_capabilities) > 1
    for capability in routing_capabilities:
        capability.defer_loading = defer_loading

    return pydantic_ai.Agent(
        model=model,
        model_settings=agent_config.model_settings,
        tools=tools,
        toolsets=toolsets,
        instructions=agent_config.get_system_prompt(),
        capabilities=capabilities,
        deps_type=AgentDependencies,
        retries=agent_config.retries,
    )


def get_agent_from_configs(
    *,
    agent_config: config_agents.AgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap,
    capability_config: CapabilityConfig | None = None,
) -> SoliplexAgent:
    """Get or create an agent from the specified agent and tool configs."""

    if agent_config.kind == "default":
        return get_default_agent_from_configs(
            agent_config=agent_config,
            tool_configs=tool_configs,
            mcp_client_toolset_configs=mcp_client_toolset_configs,
            capability_config=capability_config,
        )

    else:
        # Treat 'agent_config' as an 'AgentFactory'
        return agent_config.factory(
            tool_configs=tool_configs,
            mcp_client_toolset_configs=mcp_client_toolset_configs,
            capability_config=capability_config,
        )
