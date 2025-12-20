# Deployment

This section covers deploying Soliplex to various environments.

## Deployment Options

- **[Docker](docker.md)** - Containerized deployment
- **[Production](production.md)** - Production deployment checklist
- **[Monitoring](monitoring.md)** - Logging and observability

## Quick Reference

### Development

```bash
# Start with no auth (development only)
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

### Production Checklist

- [ ] Configure OIDC authentication
- [ ] Set up proper secrets management
- [ ] Enable HTTPS via reverse proxy
- [ ] Configure appropriate logging
- [ ] Set resource limits
- [ ] Back up RAG databases

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OLLAMA_BASE_URL` | If using Ollama | Ollama server URL |
| `URL_SAFE_TOKEN_SECRET` | Recommended | MCP token signing secret |

### Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key (configured via `provider_key: "secret:OPENAI_API_KEY"`) |

### CLI Options

| Option | Description |
|--------|-------------|
| `--log-level` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `--no-auth-mode` | Disable authentication (development only) |

### Network Requirements

| Port | Service | Access |
|------|---------|--------|
| 8000 | Backend API | Required |
| 11434 | Ollama | Backend only |
| 443 | HTTPS (reverse proxy) | Public |

## Architecture Considerations

### Single Server

```
┌─────────────────────────────────────┐
│            Reverse Proxy            │
│           (nginx/traefik)           │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│         Soliplex Backend            │
│         (FastAPI + Uvicorn)         │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│            Ollama                   │
│         (Local LLM Inference)       │
└─────────────────────────────────────┘
```

### Scalability Notes

- Backend is stateless (thread persistence in SQLite/DB)
- RAG database can be shared (LanceDB on shared storage)
- Consider connection pooling for high concurrency
- MCP stdio clients spawn subprocesses per connection
