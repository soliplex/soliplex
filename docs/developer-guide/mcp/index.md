# MCP Integration

Soliplex implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) in dual mode - both as a server exposing tools and as a client consuming external tools.

## Overview

| Mode | Purpose |
|------|---------|
| **MCP Server** | Expose Soliplex room tools to external MCP clients |
| **MCP Client** | Connect to external MCP servers and use their tools |

## Architecture

```
                    ┌─────────────────┐
                    │ External MCP    │
                    │ Clients         │
                    └────────┬────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │              Soliplex                    │
        │  ┌─────────────────────────────────┐    │
        │  │         MCP Server              │    │
        │  │  (Exposes room tools via /mcp/) │    │
        │  └─────────────────────────────────┘    │
        │                                          │
        │  ┌─────────────────────────────────┐    │
        │  │         MCP Client              │    │
        │  │  (Connects to external servers) │    │
        │  └──────────────┬──────────────────┘    │
        └─────────────────│────────────────────────┘
                          │
        ┌─────────────────▼─────────────────┐
        │ External MCP Servers              │
        │ (Google Maps, Weather, etc.)      │
        └───────────────────────────────────┘
```

## Sections

- **[MCP Server](server.md)** - Exposing room tools to external clients
- **[MCP Client](client.md)** - Consuming tools from external MCP servers

## Quick Examples

### Expose Tools via MCP Server

```yaml
# rooms/research/room_config.yaml
id: "research"
allow_mcp: true  # Enable MCP server for this room

tools:
  - tool_name: "soliplex.tools.search_documents"
    allow_mcp: true  # Expose this tool
  - tool_name: "soliplex.tools.get_current_datetime"
    allow_mcp: true
```

### Connect to External MCP Server

```yaml
# rooms/maps/room_config.yaml
mcp_client_toolsets:
  google_maps:
    kind: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-google-maps"]
    env:
      GOOGLE_MAPS_API_KEY: "secret:GOOGLE_MAPS_API_KEY"
```

## Authentication

MCP server endpoints use URL-safe signed tokens:

```
GET /api/v1/rooms/{room_id}/mcp_token
→ { "mcp_token": "eyJ0eXAi..." }
```

Tokens are:
- Signed with `URL_SAFE_TOKEN_SECRET`
- Scoped to specific room_id
- Optionally time-limited via `MCP_TOKEN_MAX_AGE`

## Transport Types

| Type | Use Case |
|------|----------|
| **stdio** | Local subprocess (npx, python, etc.) |
| **http** | Remote HTTP endpoint |

## Source Files

| File | Purpose |
|------|---------|
| `src/soliplex/mcp_server.py` | MCP server implementation |
| `src/soliplex/mcp_client.py` | MCP client connections |
| `src/soliplex/mcp_auth.py` | Token authentication |
| `src/soliplex/config.py` | MCP configuration classes |
