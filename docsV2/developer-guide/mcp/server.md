# MCP Server

Soliplex exposes room tools via the Model Context Protocol (MCP), allowing external clients (Claude Desktop, other AI agents) to use your tools.

## Overview

```
External MCP Client (Claude Desktop)
    ↓
MCP HTTP Transport
    ↓
FastMCP Server (per room)
    ↓
Room Tools (search_documents, etc.)
```

## Enabling MCP for a Room

Set `allow_mcp: true` at the room level:

```yaml
# rooms/research/room_config.yaml
id: "research"
description: "Research room with MCP access"
allow_mcp: true  # Enable MCP server for this room

tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    allow_mcp: true  # Expose this specific tool via MCP
```

Both the room and individual tools must have `allow_mcp: true` to be exposed.

## Tool Eligibility

Not all tools can be exposed via MCP:

| Requirement | MCP Compatible | Reason |
|-------------|----------------|--------|
| `BARE` | Yes | No dependencies |
| `TOOL_CONFIG` | Yes | Config is curried in |
| `FASTAPI_CONTEXT` | No | Requires RunContext |

Tools requiring `FASTAPI_CONTEXT` (like `ask_with_rich_citations`) cannot be exposed because they depend on the FastAPI request context.

## MCP Server Setup

The server is automatically configured during application startup:

```python
# src/soliplex/mcp_server.py
def setup_mcp_for_rooms(the_installation: Installation):
    mcp_apps = {}

    for key, room_config in available_rooms.items():
        if room_config.allow_mcp:
            mcp = fmcp_server.FastMCP(
                key,
                tools=room_mcp_tools(room_config),
                auth=FastMCPTokenProvider(
                    room_id=key,
                    the_installation=the_installation,
                    max_age=max_age,
                ),
            )
            mcp_apps[key] = mcp.http_app(path="/")

    return mcp_apps
```

Each room with MCP enabled gets its own FastMCP server instance.

## Authentication

MCP endpoints are secured with URL-safe tokens.

### Getting a Token

Request a token via the API:

```bash
curl -H "Authorization: Bearer $OIDC_TOKEN" \
    http://localhost:8000/api/v1/rooms/{room_id}/mcp_token
```

Response:
```json
{
  "room_id": "research",
  "mcp_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Token Validation

Tokens are validated using `itsdangerous.URLSafeTimedSerializer`:

```python
class FastMCPTokenProvider(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        if self.auth_disabled:
            return token  # No-auth mode for development

        validated = validate_url_safe_token(
            self.secret_key,
            self.room_id,  # Salt = room ID
            token,
            max_age=self.max_age,
        )

        if validated is not None:
            return AccessToken(token=token, client_id=self.room_id)
```

### Token Configuration

Configure the token secret and expiration:

```yaml
# installation.yaml
secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "URL_SAFE_TOKEN_SECRET"

environment:
  - "MCP_TOKEN_MAX_AGE"  # Optional: token expiration in seconds
```

## MCP Endpoint URLs

MCP servers are mounted at:

```
http://localhost:8000/rooms/{room_id}/mcp/
```

For example:
- `http://localhost:8000/rooms/research/mcp/`
- `http://localhost:8000/rooms/legal/mcp/`

## Connecting Claude Desktop

Configure Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "soliplex-research": {
      "command": "npx",
      "args": [
        "-y",
        "@anthropic-ai/mcp-client-cli",
        "http://localhost:8000/rooms/research/mcp/",
        "--header",
        "Authorization: Bearer YOUR_MCP_TOKEN"
      ]
    }
  }
}
```

## Tool Wrappers

Some tools require wrapping for MCP compatibility:

```python
# Config wrapper for query-based tools
class WithQueryMCPWrapper:
    def __init__(self, func, tool_config):
        self._func = func
        self._tool_config = tool_config

    def __call__(self, query: str):
        return self._func(query=query, tool_config=self._tool_config)
```

The wrapper curries in the tool configuration so MCP clients only need to provide the query parameter.

## Exposed Tools

When a room has MCP enabled, its eligible tools are exposed:

```python
def room_mcp_tools(room_config: RoomConfig) -> list[Tool]:
    if room_config.allow_mcp:
        return [
            mcp_tool(tc) for tc in room_config.tool_configs.values()
            if tc.allow_mcp and tc.tool_requires != FASTAPI_CONTEXT
        ]
    return []
```

## Development Mode

In no-auth mode (`--no-auth-mode`), MCP tokens are not validated:

```bash
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

This allows testing MCP without token configuration. Do not use in production.

## Best Practices

1. **Use unique secrets** - Generate a strong `URL_SAFE_TOKEN_SECRET`
2. **Set token expiration** - Use `MCP_TOKEN_MAX_AGE` to limit token lifetime
3. **Limit tool exposure** - Only enable `allow_mcp` for tools that need it
4. **Secure transport** - Use HTTPS in production
5. **Monitor access** - Log MCP requests for auditing

## Source Code

- MCP server setup: `src/soliplex/mcp_server.py`
- Token authentication: `src/soliplex/mcp_auth.py`
- Tool wrappers: `src/soliplex/config.py:746-767`
