# Completions Configuration

Completions are standalone chat endpoints that provide OpenAI-compatible API access without the full room features.

## Directory Structure

Each completion is configured via a directory whose name becomes the completion ID:

```
completions/
  chat-bot/
    completion_config.yaml
    prompt.txt              # Optional external system prompt
  code-assistant/
    completion_config.yaml
```

**Note:** Directories starting with `.` are ignored.

## Configuration File Schema

The `completion_config.yaml` file defines the completion endpoint:

### Required Fields

```yaml
id: "chat-bot"           # Must match directory name
agent:                   # Agent configuration (see Agents docs)
  model_name: "gpt-4o"
  system_prompt: |
    You are a helpful assistant.
```

### Complete Example

```yaml
id: "code-assistant"
name: "Code Assistant"   # Display name

agent:
  model_name: "gpt-4o"
  provider_type: "openai"
  provider_base_url: "https://api.openai.com/v1"
  provider_key: "secret:OPENAI_API_KEY"
  system_prompt: "./prompt.txt"  # Load from file
  retries: 3
  model_settings:
    temperature: 0.7
    max_tokens: 4096

tools:
  - tool_name: "soliplex.tools.get_current_datetime"
```

## External System Prompts

System prompts can be loaded from a `prompt.txt` file:

```yaml
agent:
  system_prompt: "./prompt.txt"  # Relative to completion directory
```

The file path must start with `./` to indicate it's relative to the config file location.

## Agent Configuration

The `agent` section follows the same schema as room agents. See [Agents Configuration](agents.md) for full details on:

- Provider types (`ollama`, `openai`)
- Model settings
- Secret references
- Template inheritance

## Tools Configuration

Completions can include tools:

```yaml
tools:
  - tool_name: "soliplex.tools.get_current_datetime"
    allow_mcp: true
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
```

## MCP Client Toolsets

Completions can connect to external MCP servers. Supports both stdio and HTTP transports.

### Stdio Transport

Run MCP server as a subprocess:

```yaml
mcp_client_toolsets:
  filesystem:
    kind: "stdio"
    command: "npx"
    args: ["-y", "@anthropic-ai/mcp-server-filesystem", "./workspace"]
    env:
      API_KEY: "secret:MCP_API_KEY"
    allowed_tools:
      - "read_file"
      - "list_directory"
```

### HTTP Transport

Connect to remote MCP server over HTTP:

```yaml
mcp_client_toolsets:
  remote:
    kind: "http"
    url: "https://mcp.example.com/v1"
    headers:
      Authorization: "Bearer secret:MCP_TOKEN"
    allowed_tools:
      - "search"
```

See [MCP Client](../../developer-guide/mcp/client.md) for full details on transport options and configuration.

## API Access

Completions are accessed via the OpenAI-compatible API:

```bash
# List available completions
curl http://localhost:8000/api/v1/chat/completions

# Get specific completion
curl http://localhost:8000/api/v1/chat/completions/chat-bot

# Execute chat completion
curl -X POST http://localhost:8000/api/v1/chat/completions/chat-bot \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

## Completions vs Rooms

| Feature | Completion | Room |
|---------|------------|------|
| OpenAI-compatible API | Yes | No |
| AG-UI streaming | No | Yes |
| Thread persistence | No | Yes |
| Document filtering | No | Yes |
| MCP server exposure | Yes | Yes |
| Flutter UI support | No | Yes |

Use completions for:
- Simple chat integrations
- OpenAI API compatibility
- Lightweight endpoints

Use rooms for:
- Full-featured chat applications
- Conversation history
- Rich client features

## Installation Reference

Register completion directories in `installation.yaml`:

```yaml
completion_paths:
  - "./completions"
```

## Source Code

- Completion views: `src/soliplex/views/completions.py`
- Completion model: `src/soliplex/models.py`
- Configuration: `src/soliplex/config.py`
