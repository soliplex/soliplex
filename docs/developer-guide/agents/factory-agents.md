# Factory Agents

Factory agents provide complete control over agent creation using custom Python code. Use them when standard configuration isn't sufficient.

## When to Use Factory Agents

| Use Case | Standard Config | Factory Agent |
|----------|-----------------|---------------|
| Simple prompt + model | Yes | No |
| Custom tools at runtime | No | Yes |
| Multi-agent orchestration | No | Yes |
| Dynamic system prompts | No | Yes |
| Custom dependencies | No | Yes |

## Configuration

```yaml
# rooms/custom/room_config.yaml
agent:
  kind: "factory"
  factory_name: "mypackage.agents.custom_factory"
  with_agent_config: true
  extra_config:
    custom_param: "value"
```

### Properties

| Property | Required | Description |
|----------|----------|-------------|
| `kind` | Yes | Must be `"factory"` |
| `factory_name` | Yes | Python import path |
| `with_agent_config` | No | Pass config to factory |
| `extra_config` | No | Custom parameters |

## Factory Function Signature

```python
def my_factory(
    agent_config: config.FactoryAgentConfig,  # Provided when with_agent_config=true
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
) -> pydantic_ai.Agent:
    """Create and return a Pydantic AI agent."""
    pass
```

When `with_agent_config: true`, the config system uses `functools.partial` to bind the `agent_config` parameter automatically.

## Example: Joke Generator

The `joker_agent_factory` demonstrates multi-agent orchestration:

```python
# src/soliplex/examples.py

JOKER_AGENT_PROMPT = """\
Use the `joke_factory` to generate some jokes, then choose the best.

You must return just a single joke.
"""

def joker_agent_factory(
    agent_config,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
):
    installation_config = agent_config._installation_config

    # Create Ollama provider
    provider_base_url = installation_config.get_environment("OLLAMA_BASE_URL")
    provider_kw = {"base_url": f"{provider_base_url}/v1"}
    provider = ollama_providers.OllamaProvider(**provider_kw)

    # Primary agent - handles user interaction
    joke_selection_agent = pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name="gpt-oss:latest",
            provider=provider,
        ),
        system_prompt=JOKER_AGENT_PROMPT,
    )

    # Helper agent - generates jokes
    joke_generation_agent = pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name="gpt-oss:latest",
            provider=provider,
        ),
        output_type=list[str],  # Returns list of jokes
    )

    # Register tool on primary agent that uses helper
    @joke_selection_agent.tool
    async def joke_factory(
        ctx: pydantic_ai.RunContext[None],
        count: int,
        topic: str = None,
    ) -> list[str]:
        """Generate jokes using the helper agent."""
        if topic is None:
            prompt = f"Please generate {count} jokes."
        else:
            prompt = f"Please generate {count} jokes about {topic}."

        r = await joke_generation_agent.run(
            prompt,
            usage=ctx.usage,  # Share usage tracking
        )
        return r.output

    return joke_selection_agent
```

### Room Configuration

```yaml
# example/rooms/joker/room_config.yaml
id: "joker"
name: "Joke generator"
description: "Testing agent delegation"
agent:
  kind: "factory"
  factory_name: "soliplex.examples.joker_agent_factory"
  with_agent_config: true
allow_mcp: false
```

## Accessing Installation Config

Factory agents can access the full installation configuration:

```python
def my_factory(agent_config, tool_configs, mcp_configs):
    # Access installation config
    installation = agent_config._installation_config

    # Get secrets
    api_key = installation.get_secret("OPENAI_API_KEY")

    # Get environment
    ollama_url = installation.get_environment("OLLAMA_BASE_URL")

    # Access other agent configs
    other_agent = installation.agent_configs_map["other_agent"]

    # ...
```

## Dynamic Tools

Add tools dynamically using decorators:

```python
def my_factory(agent_config, tool_configs, mcp_configs):
    agent = pydantic_ai.Agent(
        model=get_model(agent_config),
        system_prompt="You are a helpful assistant.",
    )

    # Add tool based on configuration
    if agent_config.extra_config.get("enable_search"):
        @agent.tool
        async def search(ctx, query: str) -> list[str]:
            return await perform_search(query)

    return agent
```

## Dynamic System Prompts

Use `@agent.system_prompt` for runtime prompt generation:

```python
def my_factory(agent_config, tool_configs, mcp_configs):
    agent = pydantic_ai.Agent(model=get_model(agent_config))

    @agent.system_prompt
    async def get_prompt(ctx: pydantic_ai.RunContext) -> str:
        user = ctx.deps.user
        return f"""
        You are assisting {user.given_name}.
        Today's date is {datetime.now().isoformat()}.
        Be helpful and accurate.
        """

    return agent
```

## Multi-Agent Patterns

### Delegation Pattern

Primary agent delegates to specialized agents:

```python
def orchestrator_factory(agent_config, tool_configs, mcp_configs):
    # Specialized agents
    code_agent = create_code_agent()
    research_agent = create_research_agent()

    # Orchestrator
    orchestrator = pydantic_ai.Agent(
        model=get_model(agent_config),
        system_prompt="Route requests to appropriate specialists.",
    )

    @orchestrator.tool
    async def ask_code_expert(ctx, question: str) -> str:
        result = await code_agent.run(question, usage=ctx.usage)
        return result.output

    @orchestrator.tool
    async def ask_researcher(ctx, question: str) -> str:
        result = await research_agent.run(question, usage=ctx.usage)
        return result.output

    return orchestrator
```

## Example: Faux Agent (Testing)

The `faux_agent_factory` creates a simulated agent for testing purposes. It doesn't use a real LLM but simulates agent behavior with delays and mock responses.

```python
# src/soliplex/examples.py

@dataclasses.dataclass
class FauxAgent:
    agent_config: config.FactoryAgentConfig
    tool_configs: config.ToolConfigMap = None
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None

    async def run_stream_events(self, message_history, deps, **kwargs):
        # 1. Emit thinking events with delays
        yield ai_messages.PartStartEvent(index=0, part=ThinkingPart("I'm thinking"))
        await asyncio.sleep(random.uniform(0.5, 2.0))
        yield ai_messages.PartEndEvent(index=0, part=think_part)

        # 2. Call each configured tool
        for tool_name, tool_config in self.tool_configs.items():
            yield ai_messages.PartStartEvent(index=i, part=ToolCallPart(tool_name))
            await tool_config.tool(ctx)
            yield ai_messages.PartEndEvent(index=i, part=tc_part)

        # 3. Return static response
        yield ai_messages.PartStartEvent(index=n, part=TextPart("I don't know!"))
        yield ai_messages.PartEndEvent(index=n, part=text_part)


def faux_agent_factory(agent_config, tool_configs, mcp_client_toolset_configs):
    return FauxAgent(agent_config, tool_configs, mcp_client_toolset_configs)
```

### Room Configuration

```yaml
# example/rooms/faux/room_config.yaml
id: "faux"
name: "Test Room"
description: "Room for testing agent streaming behavior"
agent:
  kind: "factory"
  factory_name: "soliplex.examples.faux_agent_factory"
  with_agent_config: true
allow_mcp: false
```

### Use Cases

- Testing AG-UI event streaming without LLM costs
- Verifying tool call behavior in isolation
- UI development with predictable agent responses
- Integration testing with controlled delays

## Best Practices

1. **Share usage tracking** - Pass `ctx.usage` between agents
2. **Handle errors** - Wrap agent calls in try/except
3. **Cache agents** - Create helper agents once, not per-request
4. **Test thoroughly** - Factory agents need extra testing
5. **Document behavior** - Custom agents need clear documentation

## Source Code

- Factory agent implementation: `src/soliplex/config.py` (lines 943-1003)
- Example factories: `src/soliplex/examples.py`
