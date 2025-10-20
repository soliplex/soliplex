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

- `system_prompt` is the "instructions" for the LLM serving the room.
  If it starts with a `./`, it will be treated as a filename in the
  same directory, whose contents will be read in its place.

A minimal configuration, without an external prompt file:

```yaml
agent:
    system_prompt: |
        You are a knowledgeable assistant that helps users find information from a document knowledge base.

        Your process:
        1. When a user asks a question, use the search_documents tool to find relevant information
        ...
```

A minimal configuration, but with the prompt stored in external file:

```yaml
agent:
    system_prompt: "./prompt.txt"
```

## Optional Agent Elements

- `model_name`: a string, defaulting to the value configured in
  the installation environment as `DEFAULT_AGENT_MODEL`, should be the
  identifier of an alternate model for the agent.  E.g.:

  ```yaml
  model_name: "mistral:7b"
  ```

- `provider_base_url`: a string, defaulting to the value configured in
  the installation environment as `OLLAMA_BASE_URL` ) is base API URL for the agent's
  LLM provider.  *without* the `/v1` suffix. E.g.:

  ```yaml
  provider_base_url: "https://provider.example.com/api"
  ```

- `provider_key` (a string, default's to None) should be the
  *name* of the scret holding the LLM provider's API key
  (*not* the value of the API key), prefixed with `secret:`

  ```yaml
  provider_key: "secret:FOO_PROVIDER_API_KEY"
