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
  - name: "DEFAULT_AGENT_MODEL"
    value: "llama3.2"
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

## Resolution Priority

Environment variables are resolved as follows:

1. **`.env` file** - Always takes precedence if the variable is defined
2. **YAML value** - Used if `.env` doesn't have the variable
3. **OS environment** - Fallback when YAML value is omitted (bare string or `name:` without `value:`)

**Note:** `os.environ` is only checked when no YAML value is specified. If you set `value:` in YAML, `os.environ` is ignored (unless `.env` overrides it).

### .env File Support

Place a `.env` file in the same directory as your installation config:

```bash
# .env
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_AGENT_MODEL=llama3.2
```

Values from `.env` take precedence over both OS environment and YAML-configured values.

## Common Variables

### LLM Provider

| Variable | Description | Example |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |

### Agent Defaults

| Variable | Description | Example |
|----------|-------------|---------|
| `DEFAULT_AGENT_MODEL` | Default model when agent `model_name` is not specified | `llama3.2` |

### MCP

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TOKEN_MAX_AGE` | MCP token expiration (seconds) | None (no expiry) |

### Paths

| Variable | Description | Example |
|----------|-------------|---------|
| `SOLIPLEX_INSTALLATION_PATH` | Installation config path (CLI fallback) | `/path/to/installation.yaml` |
| `RAG_LANCE_DB_PATH` | RAG database directory | `file:./db/rag` |

## File References

Values starting with `file:` are treated as file path references and resolved relative to the configuration file's directory:

```yaml
environment:
  - name: "RAG_LANCE_DB_PATH"
    value: "file:./db/rag"  # Relative to config file
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
- DEFAULT_AGENT_MODEL      : llama3.2
- RAG_LANCE_DB_PATH        : /absolute/path/to/db/rag

```

Variables marked "MISSING" are configured but not set in `.env` or OS environment.

## Conditional Configuration

Use separate config files for different environments:

```yaml
# development.yaml
environment:
  - name: "OLLAMA_BASE_URL"
    value: "http://localhost:11434"
  - name: "DEFAULT_AGENT_MODEL"
    value: "llama3.2"

# production.yaml
environment:
  - name: "OLLAMA_BASE_URL"
    value: "http://gpu-server:11434"
  - name: "DEFAULT_AGENT_MODEL"
    value: "llama3.1:70b"
```

## Docker Compose Integration

```yaml
# docker-compose.yml
services:
  soliplex:
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DEFAULT_AGENT_MODEL=llama3.2
```

```yaml
# installation.yaml
environment:
  - "OLLAMA_BASE_URL"
  - "DEFAULT_AGENT_MODEL"
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
  # LLM Provider (read from .env or OS environment)
  - "OLLAMA_BASE_URL"

  # Agent Defaults
  - name: "DEFAULT_AGENT_MODEL"
    value: "llama3.2"

  # Paths
  - name: "RAG_LANCE_DB_PATH"
    value: "file:./db/rag"

  # MCP
  - name: "MCP_TOKEN_MAX_AGE"
    value: "3600"  # 1 hour

  # Custom application variables
  - name: "MY_CUSTOM_VAR"
    value: "custom_value"
```

## Source Code

- Environment configuration: `src/soliplex/config.py`
- Environment resolution: `src/soliplex/installation.py`
