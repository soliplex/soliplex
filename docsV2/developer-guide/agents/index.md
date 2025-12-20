# Agent System

Soliplex uses [Pydantic AI](https://ai.pydantic.dev/) as its agent framework. This section covers how agents are configured, created, and extended.

## Overview

Agents in Soliplex:

- Handle conversations with users
- Execute tools (document search, API calls, etc.)
- Stream responses via AG-UI protocol
- Support multiple LLM providers (Ollama, OpenAI)

## Agent Types

| Type | Use Case |
|------|----------|
| **Default Agent** | Standard configuration via YAML |
| **Factory Agent** | Custom Python code for advanced behavior |

## Sections

- **[Configuration](configuration.md)** - AgentConfig properties, templates, and model settings
- **[Factory Agents](factory-agents.md)** - Custom agent creation with FactoryAgentConfig
- **[Tools](tools.md)** - Built-in tools and creating custom tools
- **[Streaming](streaming.md)** - run_stream() and AG-UI event handling

## Quick Example

```yaml
# Basic agent configuration
agent_configs:
  - id: "default_chat"
    model_name: "gpt-oss:latest"
    provider_type: "ollama"
    system_prompt: |
      You are a helpful AI assistant.
```

## Key Concepts

### AgentDependencies

Every agent receives dependencies at runtime:

```python
@dataclasses.dataclass
class AgentDependencies:
    the_installation: typing.Any      # installation.Installation
    user: models.UserProfile = None   # Current user info
    tool_configs: ToolConfigMap = None  # Tool configurations
    agui_emitter: typing.Any = None   # AG-UI event emitter
    state: agui.AGUI_State = field(default_factory=dict)  # Client state
```

### Agent Caching

Agents are cached by ID to avoid recreation:

```python
# First call creates agent, subsequent calls return cached
agent = get_agent_from_configs(agent_config, tool_configs, mcp_client_toolset_configs)
```

### RunContext in Tools

Tools access dependencies via `RunContext`:

```python
async def my_tool(ctx: pydantic_ai.RunContext[AgentDependencies]) -> str:
    user = ctx.deps.user
    return f"Hello, {user.given_name}!"
```

## Source Files

| File | Purpose |
|------|---------|
| `src/soliplex/agents.py` | Agent creation and caching |
| `src/soliplex/tools.py` | Built-in tool implementations |
| `src/soliplex/config.py` | AgentConfig and FactoryAgentConfig |
| `src/soliplex/examples.py` | Factory agent examples |
