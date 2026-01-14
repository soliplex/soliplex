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
| `soliplex-cli list-secrets <config>` | List configured secrets |
| `soliplex-cli list-environment <config>` | List environment variables |
| `soliplex-cli list-rooms <config>` | List configured rooms |
| `soliplex-cli list-completions <config>` | List completions |
| `soliplex-cli list-oidc-auth-providers <config>` | List OIDC providers |
| `soliplex-cli config <config>` | Export merged config as YAML |

### API Base URL

```
http://localhost:8000/api/
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/rooms` | GET | List available rooms |
| `/api/v1/rooms/{room_id}/agui` | POST | Create new thread |
| `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | POST | Execute run (SSE) |
| `/api/login` | GET | Get OIDC providers |
| `/api/user_info` | GET | Get current user |

### Configuration Files

| File | Purpose |
|------|---------|
| `installation.yaml` | Main configuration |
| `rooms/*/room_config.yaml` | Room configuration |
| `completions/*/completion_config.yaml` | Completion configuration |
| `oidc/config.yaml` | OIDC provider configuration |
| `haiku.rag.yaml` | Global RAG configuration |

## LLM Entry Points

For AI agents consuming this documentation, key entry points:

- **Backend**: `src/soliplex/` - FastAPI server
- **Config**: `example/` - Example configurations
- **Docs**: `docs/`
- **Frontend**: [github.com/soliplex/flutter](https://github.com/soliplex/flutter) - Flutter application (separate repo)
