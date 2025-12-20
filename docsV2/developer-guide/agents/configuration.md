# Agent Configuration

This document covers the `AgentConfig` class and all its configuration options.

## AgentConfig Properties

```yaml
agent_configs:
  - id: "my_agent"                    # Required: Unique identifier
    model_name: "gpt-oss:latest"      # Required: LLM model name
    provider_type: "ollama"           # Optional: ollama or openai
    provider_base_url: null           # Optional: Override provider URL
    provider_key: null                # Optional: API key reference
    system_prompt: "You are..."       # Optional: System instructions
    retries: 3                        # Optional: Retry count
    model_settings:                   # Optional: Model parameters
      temperature: 0.7
      top_p: 0.9
```

## Property Reference

### id (required)

Unique identifier for the agent. Used for caching and references.

```yaml
id: "research_agent"
```

### model_name (required)

The LLM model name. Format depends on provider:

```yaml
# Ollama models
model_name: "gpt-oss:latest"
model_name: "llama3:8b"
model_name: "mistral:7b"

# OpenAI models
model_name: "gpt-4"
model_name: "gpt-3.5-turbo"
```

### provider_type

LLM provider type. Defaults to `ollama`.

```yaml
provider_type: "ollama"   # Local Ollama
provider_type: "openai"   # OpenAI API
```

### provider_base_url

Override the provider URL. If not set, uses `OLLAMA_BASE_URL` from environment.

```yaml
provider_base_url: "http://custom-ollama:11434"
```

### provider_key

Reference to a secret for API authentication.

```yaml
provider_key: "secret:OPENAI_API_KEY"
```

### system_prompt

Instructions for the agent. Can be inline or file reference.

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

The file path is relative to the configuration file location.

### retries

Number of retries on failure. Default is 3.

```yaml
retries: 5
```

### model_settings

Pydantic AI model settings for fine-tuning behavior.

```yaml
model_settings:
  temperature: 0.7        # Randomness (0-1)
  top_p: 0.9             # Nucleus sampling
  max_tokens: 4096       # Max response length
```

## Template Inheritance

Agents can inherit from templates using `template_id`:

```yaml
agent_configs:
  # Base template
  - id: "base_research"
    model_name: "gpt-oss:latest"
    system_prompt: "You are a research assistant."

  # Inherits from base, overrides model
  - id: "advanced_research"
    template_id: "base_research"
    model_name: "gpt-oss:20b"

  # Inherits from base, overrides prompt
  - id: "legal_research"
    template_id: "base_research"
    system_prompt: "You are a legal research specialist."
```

Template inheritance:
1. Loads the template configuration
2. Merges current config over template
3. Current values override template values

## Provider Configuration

### Ollama Provider

```yaml
# Minimal (uses OLLAMA_BASE_URL from env)
agent_configs:
  - id: "local_agent"
    model_name: "gpt-oss:latest"

# Explicit URL
agent_configs:
  - id: "remote_ollama"
    model_name: "llama3:8b"
    provider_base_url: "http://gpu-server:11434"
```

### OpenAI Provider

```yaml
agent_configs:
  - id: "openai_agent"
    model_name: "gpt-4"
    provider_type: "openai"
    provider_key: "secret:OPENAI_API_KEY"
```

Ensure the secret is defined:

```yaml
secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "env_var"
        env_var_name: "OPENAI_API_KEY"
```

## Room-Level Agent Configuration

Rooms can define agents inline or reference global configs:

**Inline agent:**
```yaml
# rooms/research/room_config.yaml
agent:
  model_name: "gpt-oss:latest"
  system_prompt: "You are a research assistant."
```

**Reference global:**
```yaml
# installation.yaml
agent_configs:
  - id: "research_agent"
    model_name: "gpt-oss:latest"

# rooms/research/room_config.yaml
agent:
  template_id: "research_agent"
```

## Complete Example

```yaml
# installation.yaml
id: "my-installation"

secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "env_var"
        env_var_name: "OPENAI_API_KEY"

environment:
  - "OLLAMA_BASE_URL"

agent_configs:
  # Local Ollama agent
  - id: "local_chat"
    model_name: "gpt-oss:latest"
    system_prompt: |
      You are a helpful assistant.
      Be concise and accurate.
    model_settings:
      temperature: 0.7

  # OpenAI agent for advanced tasks
  - id: "advanced_chat"
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
```

## Source Code

Configuration parsing: `src/soliplex/config.py` (lines 781-937)
