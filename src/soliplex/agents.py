import pydantic_ai
from pydantic_ai import tools as ai_tools
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers

from soliplex import config
from soliplex import models

# Cache for agents to avoid recreating them
_agent_cache: dict[str, pydantic_ai.Agent] = {}



def make_ai_tool(tool_config) -> ai_tools.Tool:
    tool_func = tool_config.tool_with_config

    return ai_tools.Tool(
        tool_func,
        name=tool_config.tool_id,
    )


def get_agent_from_configs(
    agent_config: config.AgentConfig,
    tool_configs: config.ToolConfigMap,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap,
) -> pydantic_ai.Agent:
    """Get or create an agent from the specified agent and tool configs."""

    if agent_config.id not in _agent_cache:
        provider_kw = agent_config.llm_provider_kw

        if agent_config.provider_type == config.LLMProviderType.OLLAMA:
            provider_kw["api_key"] = "dummy"
            provider = ollama_providers.OllamaProvider(**provider_kw)
        else:
            provider = openai_providers.OpenAIProvider(**provider_kw)

        tools = [
            make_ai_tool(tool_config)
            for tool_config in tool_configs.values()
        ]
        toolsets = [] # TOOD build from mcp_client_toolsets

        _agent_cache[agent_config.id] = pydantic_ai.Agent(
            model=openai_models.OpenAIChatModel(
                model_name=agent_config.model_name,
                provider=provider,
            ),
            tools=tools,
            toolsets=toolsets,
            instructions=agent_config.get_system_prompt(),
            deps_type=models.AgentDependencies,
        )

    return _agent_cache[agent_config.id]
