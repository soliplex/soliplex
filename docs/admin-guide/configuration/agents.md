# Agent Configuration

Agents are configured to interact with LLM providers. This document covers agent configuration options.

## Quick Start

```yaml
agent_configs:
  - id: "default"
    model_name: "gpt-oss:latest"
```

## Agent Types

### Default Agent (Standard)

Uses an LLM provider directly (kind: `"default"`, which is the default):

```yaml
agent:
  model_name: "gpt-oss:latest"
  system_prompt: "You are a helpful assistant."
```

### Factory Agent

Custom agent creation via Python code:

```yaml
agent:
  kind: "factory"
  factory_name: "mypackage.agents.custom_factory"
  with_agent_config: true
```

See [Factory Agents](../../developer-guide/agents/factory-agents.md) for details.

## Configuration Reference

### id

Unique identifier (required for global agents):

```yaml
agent_configs:
  - id: "research_agent"
```

### model_name

LLM model to use. Falls back to `DEFAULT_AGENT_MODEL` environment variable if not set.

```yaml
model_name: "gpt-oss:latest"     # Ollama
model_name: "gpt-4"              # OpenAI
model_name: "gpt-4o"             # OpenAI (via compatible API)
```

Note: Only `ollama` and `openai` provider types are supported. For other LLMs (Claude, etc.), use an OpenAI-compatible proxy.

### provider_type

LLM provider type. Default: `ollama`

```yaml
provider_type: "ollama"   # Local Ollama server
provider_type: "openai"   # OpenAI API
```

### provider_base_url

Override provider URL:

```yaml
# Custom Ollama server
provider_base_url: "http://gpu-server:11434"

# Azure OpenAI
provider_base_url: "https://mycompany.openai.azure.com/openai"
```

If not set, uses `OLLAMA_BASE_URL` from environment.

### provider_key

API key reference (for authenticated providers):

```yaml
provider_key: "secret:OPENAI_API_KEY"
```

### system_prompt

Agent instructions. Inline or file reference:

**Inline:**
```yaml
system_prompt: |
  You are an expert research assistant.
  Always cite your sources.
  Be concise and accurate.
```

**File reference:**
```yaml
system_prompt: "./prompts/research.md"
```

File paths must start with `./` to be recognized as file references. Paths are resolved relative to the configuration file's directory.

### retries

Number of retries on failure. Default: `3`

```yaml
retries: 5
```

### model_settings

LLM parameters:

```yaml
model_settings:
  temperature: 0.7       # Randomness (0-1)
  top_p: 0.9            # Nucleus sampling
  max_tokens: 4096      # Max response length
```

### template_id

Inherit from another agent configuration:

```yaml
agent_configs:
  # Base template
  - id: "base_research"
    model_name: "gpt-oss:latest"
    system_prompt: "You are a research assistant."
    model_settings:
      temperature: 0.3

  # Inherits from base, overrides model
  - id: "advanced_research"
    template_id: "base_research"
    model_name: "gpt-oss:70b"
```

Child values override parent values.

## Room-Level Configuration

Agents can be configured inline in rooms:

```yaml
# rooms/chat/room_config.yaml
agent:
  model_name: "gpt-oss:latest"
  system_prompt: "./prompt.txt"
```

Or reference a global agent:

```yaml
# rooms/chat/room_config.yaml
agent:
  template_id: "research_agent"
```

## Provider Examples

### Ollama (Default)

```yaml
agent:
  model_name: "gpt-oss:latest"
  # Uses OLLAMA_BASE_URL from environment
```

### OpenAI

```yaml
# installation.yaml
secrets:
  - "OPENAI_API_KEY"

agent_configs:
  - id: "openai_gpt4"
    model_name: "gpt-4"
    provider_type: "openai"
    provider_key: "secret:OPENAI_API_KEY"
```

### Custom Ollama Server

```yaml
agent:
  model_name: "llama3:70b"
  provider_base_url: "http://gpu-cluster.local:11434"
```

## Factory Agent Configuration

For complex agents requiring custom Python code:

```yaml
agent:
  kind: "factory"
  factory_name: "soliplex.examples.joker_agent_factory"
  with_agent_config: true
  extra_config:
    joke_style: "puns"
    max_jokes: 5
```

Factory agents have access to:
- Full installation configuration
- Dynamic tool registration
- Multi-agent orchestration

### extra_config

The `extra_config` field is a dictionary of custom parameters passed to the factory function. Use it to configure factory-specific behavior:

```yaml
agent:
  kind: "factory"
  factory_name: "mypackage.agent_factory"
  extra_config:
    api_endpoint: "https://api.example.com"
    timeout_seconds: 30
    feature_flags:
      enable_cache: true
```

Access in factory:

```python
def my_agent_factory(agent_config: FactoryAgentConfig) -> Agent:
    endpoint = agent_config.extra_config.get("api_endpoint")
    timeout = agent_config.extra_config.get("timeout_seconds", 10)
    # ...
```

**Note:** `extra_config` accepts any JSON-compatible structure (strings, numbers, booleans, lists, nested objects).

## Agent Caching

Agents are cached by their **ID**. Each room or completion gets a unique agent ID:

- Room agents: `room-{room_id}`
- Completion agents: `completion-{completion_id}`

```yaml
# These two rooms have DIFFERENT agent instances
# (IDs: "room-room1" and "room-room2")
rooms/room1/room_config.yaml:
  agent:
    template_id: "default"

rooms/room2/room_config.yaml:
  agent:
    template_id: "default"
```

Global agents defined in `agent_configs` with the same ID will share instances.

## Complete Example

```yaml
# installation.yaml
secrets:
  - "OPENAI_API_KEY"

agent_configs:
  # Local Ollama agent
  - id: "local_chat"
    model_name: "gpt-oss:latest"
    system_prompt: |
      You are a helpful assistant.
      Be concise and accurate.
    model_settings:
      temperature: 0.7
    retries: 3

  # OpenAI agent for complex tasks
  - id: "advanced"
    model_name: "gpt-4"
    provider_type: "openai"
    provider_key: "secret:OPENAI_API_KEY"
    system_prompt: |
      You are an expert AI assistant.
      Provide detailed, accurate responses.
    model_settings:
      temperature: 0.5
      max_tokens: 8192

  # Specialized agent inheriting from local_chat
  - id: "code_assistant"
    template_id: "local_chat"
    system_prompt: |
      You are an expert programmer.
      Write clean, well-documented code.
      Explain your reasoning.
```

## Source Code

- Agent configuration: `src/soliplex/config.py`
- Agent creation: `src/soliplex/agents.py`
