# Agent Configurations

The `agent` mapping in a room or completion configuration controls how
Soliplex communicates with an LLM.  The `kind` key selects which agent
type is used:

| `kind`        | Description |
|---------------|-------------|
| `"default"`   | Pydantic AI agent with direct LLM access (default) |
| `"factory"`   | Agent created by a custom Python callable |
| `"haiku_chat"`| Conversational RAG agent powered by `haiku.rag` |

When `kind` is omitted, it defaults to `"default"`.

## `default` kind

The default agent wraps a Pydantic AI agent that calls the configured
LLM provider directly.

```yaml
agent:
    model_name: "gpt-oss:20b"
    system_prompt: |
      You are an expert AI assistant specializing in information retrieval.

      Your answers should be clear, concise, and ready for production use.

      Always provide code or examples in Markdown blocks.
```

### Required Elements

- `model_name`: a string, should be the identifier of an LLM model for the
  agent.

  **NOTE**: this value was previously optional, defaulting to the value
            of the now-removed `DEFAULT_AGENT_MODEL` key in the
            installation environment.

- `system_prompt` is the "instructions" for the LLM serving the room.
  If it starts with a `./`, it will be treated as a filename in the
  same directory, whose contents will be read in its place.

A minimal configuration, without an external prompt file:

```yaml
agent:
    model_name: "gpt-oss:latest"
    system_prompt: |
        You are a knowledgeable assistant that helps users find information from a document knowledge base.

        Your process:
        1. When a user asks a question, find relevant information
        ...
```

A minimal configuration, but with the prompt stored in external file:

```yaml
agent:
    model_name: "gpt-oss:latest"
    system_prompt: "./prompt.txt"
```

### Optional Elements

- `provider_type`: a string, must be one of `"ollama"` (the default),
  `"openai"`, or `"google"`.

- `provider_base_url`: a string, is the base API URL for the agent's LLM
  provider.

  If not provided, and `provider_type` is set to `"ollama"`, defaults to
  the value configured in the installation environment as `OLLAMA_BASE_URL`

  If not provided, and `provider_type` is set to `"openai"`, defaults to
  the default OpenAI service URL.

  **Must not be set** if `provider_type` is set to `"google"`.

  Must be specified *without* the `/v1` suffix. E.g.:

  ```yaml
  provider_base_url: "https://provider.example.com/api"
  ```

- `provider_key` (a string, default None) should be the *name* of the secret
  holding the LLM provider's API key (*not* the value of the API key),
  prefixed with `secret:`

  ```yaml
  provider_key: "secret:FOO_PROVIDER_API_KEY"
  ```

- `model_settings`: a mapping, whose keys are determined by
  the `provider_type` above (see below).

### Example Ollama Configuration

**NOTE**: the values below show types, but should not be used without
          testing.

```yaml
model_name: "gpt-oss:latest"
provider_type: "ollama"
model_settings:
  temperature: 0.90
  top_k: 100
  top_p: 0.75
  min_p: 0.25
  stop: "STOP"
  num_ctx: 2048
  num_predict: 2000
```

### Example OpenAI Configuration

**NOTE**: the values below show types, but should not be used without
          testing.

```yaml
model_name: "mistral:7b"
provider_type: "openai"
model_settings:
  temperature: 0.90
  top_p: 0.70
  frequency_penalty: 0.25
  presence_penalty: 0.50
  parallel_tool_calls: false
  truncation: "disabled"
  max_tokens: 2048
  verbosity: "high"
```

### Example Google Configuration

**NOTE**: the values below show types, but should not be used without
          testing.

```yaml
model_name: "gemini-2.5-flash"
provider_type: "google"
model_settings:
  temperature: 0.90
  top_p: 0.70
  frequency_penalty: 0.25
  presence_penalty: 0.50
  parallel_tool_calls: false
  truncation: "disabled"
  max_tokens: 2048
  verbosity: "high"
```

## `factory` kind

The `factory` agent delegates agent creation to a custom Python callable.
Rather than configuring an LLM provider declaratively, you provide a
dotted import path to a function that builds and returns the agent.

```yaml
agent:
  kind: "factory"
  factory_name: "mypackage.agents.build_agent"
```

### Required Elements

- `kind`: must be set to `"factory"`.

- `factory_name`: a dotted Python import path to a callable that returns
  an agent instance.

### Optional Elements

- `with_agent_config` (a boolean, default `false`):  if `true`, the
  factory callable receives the `FactoryAgentConfig` instance itself as
  the `agent_config` keyword argument.

- `extra_config` (a mapping, default `{}`):  arbitrary key-value pairs
  passed through to the factory.  The structure is determined by the
  factory implementation.

### Example

```yaml
agent:
  kind: "factory"
  factory_name: "mypackage.agents.build_agent"
  with_agent_config: true
  extra_config:
    temperature: 0.8
    max_retries: 5
```

### haiku.rag Configuration

The LLM model, search settings, and other RAG behavior are controlled
via haiku.rag's own configuration, not via the agent config.  See the
[haiku.rag configuration page](rag.md) for details.

A room directory may contain a `haiku.rag.yaml` file whose settings
override the installation-level haiku.rag configuration for that room.

### Example

A full-featured room using `haiku_chat`:

```yaml
agent:
  kind: "haiku_chat"
  rag_lancedb_stem: "rag"
  rag_features: ["search", "documents", "qa"]
  preamble: |
    You are a knowledgeable assistant that answers questions
    using a document knowledge base.
  background_context: |
    This knowledge base contains internal documentation
    about the Soliplex platform.
```

A minimal search-only room:

```yaml
agent:
  kind: "haiku_chat"
  rag_lancedb_stem: "rag"
  rag_features: ["search"]
```
