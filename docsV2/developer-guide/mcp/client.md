# MCP Client

Soliplex can consume tools from external MCP servers, extending agent capabilities with third-party integrations.

## Overview

```
Soliplex Agent
    ↓
MCP Client (Stdio or HTTP)
    ↓
External MCP Server (filesystem, database, API, etc.)
```

## Transport Types

Soliplex supports two MCP transport types:

| Transport | Use Case | Connection |
|-----------|----------|------------|
| `stdio` | Local tools | Subprocess with stdin/stdout |
| `http` | Remote tools | HTTP/SSE streaming |

## Stdio Transport

Connects to MCP servers running as local subprocesses.

### Configuration

```yaml
# rooms/dev/room_config.yaml
mcp_client_toolsets:
  filesystem:
    kind: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@anthropic-ai/mcp-server-filesystem"
      - "/path/to/allowed/directory"
    env:
      NODE_ENV: "production"
    allowed_tools:
      - "read_file"
      - "list_directory"
```

### Properties

| Property | Required | Description |
|----------|----------|-------------|
| `kind` | Yes | Must be `"stdio"` |
| `command` | Yes | Executable to run |
| `args` | No | Command arguments |
| `env` | No | Environment variables |
| `allowed_tools` | No | Whitelist of tools to expose |

### Implementation

```python
class Stdio_MCP_ClientToolsetConfig:
    kind: str = "stdio"
    command: str
    args: list[str] = []
    env: dict[str, str] = {}
    allowed_tools: list[str] = None
```

The stdio client wraps Pydantic AI's `MCPServerStdio`:

```python
class Stdio_MCP_Client_Toolset(ai_mcp.MCPServerStdio):
    async def list_tools(self) -> list[Tool]:
        offered_tools = await super().list_tools()
        return _filter_tools(offered_tools, self.allowed_tools)
```

## HTTP Transport

Connects to remote MCP servers over HTTP.

### Configuration

```yaml
# rooms/api/room_config.yaml
mcp_client_toolsets:
  remote_api:
    kind: "http"
    url: "https://api.example.com/mcp/"
    headers:
      Authorization: "secret:API_TOKEN"
      X-Custom-Header: "value"
    query_params:
      version: "v1"
    allowed_tools:
      - "search"
      - "fetch"
```

### Properties

| Property | Required | Description |
|----------|----------|-------------|
| `kind` | Yes | Must be `"http"` |
| `url` | Yes | MCP server URL |
| `headers` | No | HTTP headers (supports secrets) |
| `query_params` | No | URL query parameters |
| `allowed_tools` | No | Whitelist of tools to expose |

### Secret Headers

Headers can reference secrets:

```yaml
headers:
  Authorization: "secret:MY_API_KEY"  # Resolved from secrets config
```

The secret reference is resolved during configuration loading.

### Implementation

```python
class HTTP_MCP_ClientToolsetConfig:
    kind: str = "http"
    url: str
    headers: dict[str, Any] = {}
    query_params: dict[str, str] = {}
    allowed_tools: list[str] = None
```

## Tool Filtering

Use `allowed_tools` to limit which tools from an MCP server are available:

```yaml
mcp_client_toolsets:
  database:
    kind: "stdio"
    command: "mcp-postgres"
    args: ["postgres://localhost/mydb"]
    allowed_tools:
      - "query"        # Allow read queries
      # - "execute"    # Block write operations
```

If `allowed_tools` is not specified, all tools are available.

## Factory Agent Integration

MCP client toolsets are passed to factory agents:

```python
def my_factory(
    agent_config: FactoryAgentConfig,
    tool_configs: ToolConfigMap,
    mcp_client_toolset_configs: MCP_ClientToolsetConfigMap,
) -> Agent:
    agent = Agent(model=get_model(agent_config))

    # Add MCP tools from external servers
    for name, mcp_config in mcp_client_toolset_configs.items():
        toolset = mcp_config.to_toolset()
        agent.add_mcp_server(toolset)

    return agent
```

## Room-Level Configuration

MCP clients are configured at the room level:

```yaml
# rooms/dev/room_config.yaml
id: "dev"
description: "Development room with external tools"

agent:
  model_name: "gpt-oss:latest"

mcp_client_toolsets:
  # Filesystem access
  filesystem:
    kind: "stdio"
    command: "npx"
    args: ["-y", "@anthropic-ai/mcp-server-filesystem", "./workspace"]

  # GitHub integration
  github:
    kind: "http"
    url: "https://mcp.github.com/"
    headers:
      Authorization: "secret:GITHUB_TOKEN"

tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "dev"
```

## Common MCP Servers

### Filesystem

```yaml
mcp_client_toolsets:
  filesystem:
    kind: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@anthropic-ai/mcp-server-filesystem"
      - "/allowed/path"
```

### SQLite

```yaml
mcp_client_toolsets:
  sqlite:
    kind: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@anthropic-ai/mcp-server-sqlite"
      - "path/to/database.db"
```

### Custom Server

```yaml
mcp_client_toolsets:
  custom:
    kind: "stdio"
    command: "python"
    args: ["-m", "my_mcp_server"]
    env:
      CONFIG_PATH: "/path/to/config.yaml"
```

## Error Handling

MCP client connections may fail. Common issues:

1. **Command not found** - Verify the command is installed and in PATH
2. **Connection refused** - Check the server URL and network access
3. **Authentication failed** - Verify headers and secrets are correct
4. **Tool not found** - Ensure the tool name matches exactly

## Best Practices

1. **Use allowed_tools** - Limit exposure to only needed tools
2. **Secure secrets** - Use secret references for authentication headers
3. **Test locally first** - Use stdio transport for local testing
4. **Monitor connections** - Log MCP client activity
5. **Handle failures gracefully** - External servers may be unavailable

## Source Code

- MCP client classes: `src/soliplex/mcp_client.py`
- Client configuration: `src/soliplex/config.py:586-744`
