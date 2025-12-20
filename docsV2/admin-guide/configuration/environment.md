# Environment Configuration

Environment variables provide non-secret configuration values to the Soliplex application.

## Quick Start

```yaml
environment:
  - "OLLAMA_BASE_URL"  # Read from OS environment
```

## Configuration Syntax

### Full Syntax

Specify name and value:

```yaml
environment:
  - name: "LOG_LEVEL"
    value: "INFO"
```

### OS Environment Fallback

Omit value to read from OS environment:

```yaml
environment:
  - name: "OLLAMA_BASE_URL"
    # No value - reads from os.environ["OLLAMA_BASE_URL"]
```

### Bare String (Shorthand)

A bare string is equivalent to reading from OS environment:

```yaml
environment:
  - "OLLAMA_BASE_URL"
```

Is equivalent to:

```yaml
environment:
  - name: "OLLAMA_BASE_URL"
```

## Common Variables

### LLM Provider

| Variable | Description | Example |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OPENAI_BASE_URL` | OpenAI API URL (optional) | `https://api.openai.com/v1` |

### Logging

| Variable | Description | Values |
|----------|-------------|--------|
| `LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOGFIRE_ENVIRONMENT` | Logfire environment tag | `development`, `production` |
| `LOGFIRE_SERVICE_NAME` | Logfire service name | `soliplex` |

### MCP

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TOKEN_MAX_AGE` | MCP token expiration (seconds) | None (no expiry) |

### Paths

| Variable | Description | Example |
|----------|-------------|---------|
| `INSTALLATION_PATH` | Base path for relative references | `file:.` |
| `RAG_LANCE_DB_PATH` | Default RAG database directory | `file:../db/rag` |

## File References

Values starting with `file:` are treated as file path references:

```yaml
environment:
  - name: "INSTALLATION_PATH"
    value: "file:."  # Current directory

  - name: "RAG_LANCE_DB_PATH"
    value: "file:../db/rag"  # Relative path
```

## Accessing in Code

Use `Installation.get_environment()` instead of `os.environ`:

```python
# Good - uses configured environment
ollama_url = installation.get_environment("OLLAMA_BASE_URL")

# Avoid - bypasses configuration
ollama_url = os.environ.get("OLLAMA_BASE_URL")
```

## Checking Environment

Use the CLI to verify environment configuration:

```bash
$ soliplex-cli list-environment installation.yaml

─────────────────────── Configured environment variables ───────────────────────

- OLLAMA_BASE_URL          : http://localhost:11434
- LOG_LEVEL                : INFO
- LOGFIRE_ENVIRONMENT      : development

```

Variables marked "MISSING" are configured but not set.

## Conditional Configuration

Set different values per environment:

```yaml
# development.yaml
environment:
  - name: "LOG_LEVEL"
    value: "DEBUG"
  - name: "OLLAMA_BASE_URL"
    value: "http://localhost:11434"

# production.yaml
environment:
  - name: "LOG_LEVEL"
    value: "WARNING"
  - name: "OLLAMA_BASE_URL"
    value: "http://gpu-server:11434"
```

## Docker Compose Integration

```yaml
# docker-compose.yml
services:
  soliplex:
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - LOG_LEVEL=INFO
```

```yaml
# installation.yaml
environment:
  - "OLLAMA_BASE_URL"
  - "LOG_LEVEL"
```

## Best Practices

1. **Document all variables** - List required variables in deployment docs
2. **Provide defaults** - Use explicit values for non-sensitive config
3. **Validate on startup** - Run `list-environment` before deployment
4. **Use per-environment files** - Separate development/staging/production configs
5. **Prefer configuration over hardcoding** - Make URLs and paths configurable

## Complete Example

```yaml
environment:
  # LLM Provider
  - "OLLAMA_BASE_URL"

  # Logging
  - name: "LOG_LEVEL"
    value: "INFO"
  - name: "LOGFIRE_ENVIRONMENT"
    value: "production"
  - name: "LOGFIRE_SERVICE_NAME"
    value: "soliplex"

  # Paths
  - name: "INSTALLATION_PATH"
    value: "file:."
  - name: "RAG_LANCE_DB_PATH"
    value: "file:./db/rag"

  # MCP
  - name: "MCP_TOKEN_MAX_AGE"
    value: "3600"  # 1 hour
```

## Source Code

- Environment configuration: `src/soliplex/config.py`
- Environment resolution: `src/soliplex/installation.py`
