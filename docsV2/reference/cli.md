# CLI Reference

Command-line interface reference for `soliplex-cli`.

## Installation

```bash
pip install soliplex
# or
pip install -e .  # from source
```

## Commands

### serve

Start the Soliplex server.

```bash
soliplex-cli serve <config_path> [options]
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Options:**
- `--host` - Host to bind (default: 127.0.0.1)
- `--port` - Port to bind (default: 8000)
- `--workers` - Number of workers (default: 1)
- `--no-auth-mode` - Disable authentication
- `--reload` - Enable auto-reload (development)

**Examples:**
```bash
# Basic start
soliplex-cli serve installation.yaml

# Production with workers
soliplex-cli serve installation.yaml --host 0.0.0.0 --port 8000 --workers 4

# Development mode
soliplex-cli serve installation.yaml --no-auth-mode --reload
```

### check-config

Validate a configuration file.

```bash
soliplex-cli check-config <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli check-config installation.yaml
```

**Output:**
```
✓ Configuration valid
  - 3 rooms configured
  - 2 agents configured
  - 1 OIDC provider
```

### list-secrets

List configured secrets and their resolution status.

```bash
soliplex-cli list-secrets <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli list-secrets installation.yaml
```

**Output:**
```
───────────────────────── Configured secrets ──────────────────────────────

- LOGFIRE_TOKEN             MISSING
- OPENAI_API_KEY            MISSING
- URL_SAFE_TOKEN_SECRET     OK
```

### list-environment

List configured environment variables.

```bash
soliplex-cli list-environment <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli list-environment installation.yaml
```

**Output:**
```
─────────────────────── Configured environment variables ───────────────────────

- OLLAMA_BASE_URL          : http://localhost:11434
- LOG_LEVEL                : INFO
- LOGFIRE_ENVIRONMENT      : development
```

### list-rooms

List configured rooms.

```bash
soliplex-cli list-rooms <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli list-rooms installation.yaml
```

**Output:**
```
───────────────────────────── Configured rooms ─────────────────────────────

- research    : Research Assistant (RAG enabled)
- chat        : General Chat
- code        : Code Assistant
```

## Environment Variables

The CLI respects these environment variables:

| Variable | Description |
|----------|-------------|
| `OLLAMA_BASE_URL` | Ollama server URL |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOGFIRE_TOKEN` | Logfire observability token |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Missing dependencies |

## Common Workflows

### Development

```bash
# Start Ollama
ollama serve &

# Start backend with auto-reload
export OLLAMA_BASE_URL=http://localhost:11434
soliplex-cli serve example/minimal.yaml --no-auth-mode --reload
```

### Production

```bash
# Validate config
soliplex-cli check-config production.yaml
soliplex-cli list-secrets production.yaml

# Start server
soliplex-cli serve production.yaml --host 0.0.0.0 --workers 4
```

### Debugging

```bash
# Check configuration
soliplex-cli check-config installation.yaml

# Check secrets are resolved
soliplex-cli list-secrets installation.yaml

# Check environment
soliplex-cli list-environment installation.yaml

# Start with debug logging
LOG_LEVEL=DEBUG soliplex-cli serve installation.yaml --no-auth-mode
```
