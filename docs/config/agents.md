# Agent Configurations

The agent configuration mapping is used to configure the Pydantic AI
agent used to make the calls to the LLM.


```yaml
agent:
    model_name: "gpt-oss:20b"
    system_prompt: |
      You are an expert AI assistant specializing in information retrieval.

      Your answers should be clear, concise, and ready for production use.

      Always provide code or examples in Markdown blocks.
```

## Required Agent Elements

- `model_name`: a string, should be the identifier of an LLM model for the
  agent.

  **NOTE**: this value was previously optional, defaulting to the value
            of the since-deprecated `DEFAULT_AGENT_MODEL` key in the
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
        1. When a user asks a question, use the search_documents tool to find relevant information
        ...
```

A minimal configuration, but with the prompt stored in external file:

```yaml
agent:
    model_name: "gpt-oss:latest"
    system_prompt: "./prompt.txt"
```

## Optional Agent Elements

- `provider_type`: a string, must be one of `"ollama"` (the default) or
  `"openai"`.

- `provider_base_url`: a string, defaulting to the value configured in
  the installation environment as `OLLAMA_BASE_URL` is the base API URL
  for the agent's LLM provider. Must be specified *without* the `/v1`
    suffix. E.g.:

  ```yaml
  provider_base_url: "https://provider.example.com/api"
  ```

- `provider_key` (a string, default's to None) should be the
  *name* of the secret holding the LLM provider's API key
  (*not* the value of the API key), prefixed with `secret:`

  ```yaml
  provider_key: "secret:FOO_PROVIDER_API_KEY"
  ```

  `provider_model_settings`: a mapping, whose keys are determined by
  the `provider_type` above (see below).


## Example Ollama Configuration

**NOTE**: the values below show types, but should not be used without
          testing.

```yaml
model_name: "gpt-oss:latest"
provider_type: "ollama"
provider_model_settings:
  temperature: 0.90
  top_k: 100
  top_p: 0.75
  min_p: 0.25
  stop: "STOP"
  num_ctx: 2048
  num_predict: 2000
```

## Example OpenAI Configuration

**NOTE**: the values below show types, but should not be used without
          testing.

```yaml
model_name: "mistral:7b"
provider_type: "openai"
provider_model_settings:
  temperature: 0.90
  top_p: 0.70
  frequency_penalty: 0.25
  presence_penalty: 0.50
  parallel_tool_calls: false
  truncation: "disabled"
  max_tokens: 2048
  verbosity: "high"
```
