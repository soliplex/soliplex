# Agent Configurations

The `agent` mapping in a room or completion configuration controls how
Soliplex communicates with an LLM.  The `kind` key selects which agent
type is used:

| `kind`        | Description |
|---------------|-------------|
| `"default"`   | Pydantic AI agent with direct LLM access (default) |
| `"factory"`   | Agent created by a custom Python callable |

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

**Template exception:** When an agent config uses `template_id` to
inherit from an entry in the installation-level `agent_configs`, both
`model_name` and `system_prompt` may be omitted locally -- they will be
supplied by the template.  Any fields set locally override the template.

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

  If provided, the value can
  [interpolate](installation.md#installation-secret-environment-interpolation)
  installation configuration environment variables, e.g.,
  `"env:MY_PROVIDER_BASE_URL"`.

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

- `retries` (an integer, default `3`):  number of retries for LLM calls
  on recoverable errors.

- `agui_feature_names` (a list of strings, default empty):  AG-UI feature
  names this agent contributes to the room's aggregate feature set.  Each
  name must be registered in the AG-UI feature registry; see
  [AG-UI Features](agui.md) for the registration paths and the
  [`meta.agui_features`](meta.md#registering-ag-ui-feature-classes) stanza
  for the YAML form.  The room's effective feature set is the union of
  features declared on the agent, the room, its tools, and its skills.

- `capabilities` (a list, default empty):  Pydantic AI capabilities for
  the agent, each named as a string, or as a mapping with `name` and
  `kwargs`.  Names come from the Pydantic AI capability registry, from
  the two evidence capabilities below, and from any registered via the
  [`meta.agent_capability_types`](meta.md) stanza.

### Evidence capabilities

Two capabilities are available to a room that retrieves.  Both are
hook-only: they add no tools, and neither affects whether the room's
other capabilities load eagerly or on demand.

- `haiku-rag-evidence-compaction`:  on each request, replaces earlier
  questions' evidence with a capsule of the evidence that was cited,
  re-attaching cited page images; every other earlier evidence return
  becomes a short receipt.  Requests only -- stored history is untouched.

- `haiku-rag-citation-policy`:  requires every answer to register the
  evidence that grounds it, or to declare that nothing does.  An answer
  that ends a question without declaring is redirected once to cite,
  which costs an extra model request; an ending that cannot be redirected
  is recorded as a violation in the run state.

They are independent, but their effects are not symmetric:

- **Compaction without the citation policy loses evidence.**  The capsule
  is built only from what was cited, so for any earlier question the
  model did not cite for, that question's evidence is replaced by
  receipts and nothing takes its place -- worse than not compacting.
  Register the citation policy alongside compaction, or register neither.

- The citation policy without compaction is safe:  citations are required
  and recorded, and no history is rewritten.

A room that registers neither resends every earlier turn's full search
results on every request.

  ```yaml
  agent:
    template_id: "default_chat"
    capabilities:
      - "haiku-rag-evidence-compaction"
      - "haiku-rag-citation-policy"
  ```

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

- `agui_feature_names` (a list of strings, default empty):  AG-UI feature
  names this agent contributes to the room's aggregate feature set.  Each
  name must be registered in the AG-UI feature registry; see
  [AG-UI Features](agui.md) for the registration paths and the
  [`meta.agui_features`](meta.md#registering-ag-ui-feature-classes) stanza
  for the YAML form.  The room's effective feature set is the union of
  features declared on the agent, the room, its tools, and its skills.

### Example

```yaml
agent:
  kind: "factory"
  factory_name: "mypackage.agents.build_agent"
  with_agent_config: true
  extra_config:
    # Additional arguments passed to the factory function
    temperature: 0.8
    max_retries: 5
  agui_feature_names:
    - "myfeature"
```
