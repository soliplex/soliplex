# Reference

Technical reference documentation for Soliplex.

## Sections

- **[CLI Reference](cli.md)** - Command-line interface documentation
- **[Config Schema](config-schema.md)** - Complete YAML configuration schema
- **[Server API](server-api.md)** - Auto-generated Python API documentation

## Quick Reference

### CLI Commands

| Command | Description |
|---------|-------------|
| `soliplex-cli serve <config>` | Start the server |
| `soliplex-cli check-config <config>` | Validate configuration |
| `soliplex-cli list-rooms <config>` | List configured rooms |

### API Base URL

```
http://localhost:8000/api/v1/
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rooms` | GET | List available rooms |
| `/rooms/{id}/agui` | POST | Create new thread |
| `/rooms/{id}/agui/{thread}/{run}` | POST | Execute run (SSE) |
| `/login` | GET | Get OIDC providers |
| `/user_info` | GET | Get current user |

### Configuration Files

| File | Purpose |
|------|---------|
| `installation.yaml` | Main configuration |
| `rooms/*/room_config.yaml` | Room configuration |
| `completions/*/completion_config.yaml` | Completion configuration |
| `oidc/*.yaml` | OIDC provider configuration |
| `haiku.rag.yaml` | Global RAG configuration |

## LLM Entry Points

For AI agents consuming this documentation, key entry points:

- **Backend**: `src/soliplex/` - FastAPI server
- **Frontend**: `src/flutter/lib/` - Flutter application
- **Config**: `example/` - Example configurations
- **Docs**: `docs/` (existing) or `docsV2/` (new structure)
