# CLI Reference

Command-line interface reference for `soliplex-cli`.

## Installation

```bash
pip install soliplex
# or
pip install -e .  # from source
```

## Global Options

```bash
soliplex-cli [options] <command>
```

- `-v, --version` - Show version and exit
- `-h, --help` - Show help

## Commands

### serve

Start the Soliplex server.

```bash
soliplex-cli serve <config_path> [options]
```

**Arguments:**
- `config_path` - Path to installation.yaml (can also be set via `SOLIPLEX_INSTALLATION_PATH` env var)

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-h, --host` | 127.0.0.1 | Host to bind |
| `-p, --port` | 8000 | Port to bind |
| `--workers` | None | Number of worker processes (env: `WEB_CONCURRENCY`) |
| `--no-auth-mode` | False | Disable OIDC authentication |
| `-r, --reload` | None | Reload mode: `config`, `python`, or `both` |
| `--reload-dirs` | [] | Additional directories to monitor for reload |
| `--reload-includes` | [] | Additional glob patterns for reload monitoring |
| `--log-level` | None | Log level: critical, error, warning, info, debug, trace |
| `--log-config` | None | Logging configuration file (.ini, .json, .yaml) |
| `--access-log` | None | Enable/disable access log |
| `--uds` | None | Bind to Unix domain socket |
| `--fd` | None | Bind to socket from file descriptor |
| `--proxy-headers` | None | Enable X-Forwarded-Proto/For headers |
| `--forwarded-allow-ips` | None | IPs to trust for proxy headers (env: `FORWARDED_ALLOW_IPS`) |

**Examples:**
```bash
# Basic start
soliplex-cli serve installation.yaml

# Production with workers
soliplex-cli serve installation.yaml --host 0.0.0.0 --port 8000 --workers 4

# Development mode with config reload
soliplex-cli serve installation.yaml --no-auth-mode --reload config

# Development with Python and config reload
soliplex-cli serve installation.yaml --no-auth-mode --reload both

# With debug logging
soliplex-cli serve installation.yaml --log-level debug
```

### check-config

Validate a configuration file and check that all secrets/environment variables can be resolved.

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
───────────────────────────── Checking secrets ─────────────────────────────

OK

───────────────────────────── Checking environment ─────────────────────────

OK

───────────────────────────── Validating installation model ────────────────

OK

───────────────────────────── Validating room models ───────────────────────

Room: research
OK

Room: chat
OK

───────────────────────────── Validating completion models ─────────────────

Completion: default
OK
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
───────────────────────────── Configured secrets ───────────────────────────

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
───────────────────────────── Configured environment variables ─────────────

- OLLAMA_BASE_URL          : http://localhost:11434
- INSTALLATION_PATH        : file:.
- RAG_LANCE_DB_PATH        : file:../db/rag
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
───────────────────────────── Configured Rooms ─────────────────────────────

- [ research ] Research Room:
  Research Assistant with RAG enabled

- [ chat ] General Chat:
  General purpose chat room
```

### list-completions

List configured completion endpoints.

```bash
soliplex-cli list-completions <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli list-completions installation.yaml
```

**Output:**
```
───────────────────────────── Configured Completions ───────────────────────

- [ default ] Default Completion:
```

### list-oidc-auth-providers

List configured OIDC authentication providers.

```bash
soliplex-cli list-oidc-auth-providers <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli list-oidc-auth-providers installation.yaml
```

**Output:**
```
───────────────────────────── Configured OIDC Auth Providers ───────────────

- [ google ] Google:
  https://accounts.google.com

- [ okta ] Okta Corporate:
  https://company.okta.com
```

### config

Export the merged installation configuration as YAML.

```bash
soliplex-cli config <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli config installation.yaml
```

**Output:**
```
#------------------------------------------------------------------------------
# Source: installation.yaml
#------------------------------------------------------------------------------
id: soliplex-conf-default
secrets:
  - secret_name: URL_SAFE_TOKEN_SECRET
    ...
```

### agui-feature-schemas

Export AG-UI feature schemas as JSON.

```bash
soliplex-cli agui-feature-schemas <config_path>
```

**Arguments:**
- `config_path` - Path to installation.yaml

**Examples:**
```bash
soliplex-cli agui-feature-schemas installation.yaml
```

**Output:**
```json
{
  "filter_documents": {
    "source": "client",
    "json_schema": {...}
  },
  "ask_history": {
    "source": "server",
    "json_schema": {...}
  }
}
```

This command exports the JSON schemas for all registered AG-UI features, useful for client applications that need to discover available features and their data contracts.

## Environment Variables

The CLI respects these environment variables:

| Variable | Used By | Description |
|----------|---------|-------------|
| `SOLIPLEX_INSTALLATION_PATH` | `<config_path>` argument | Default installation path |
| `WEB_CONCURRENCY` | `--workers` | Number of worker processes |
| `FORWARDED_ALLOW_IPS` | `--forwarded-allow-ips` | Trusted proxy IPs |

**Note:** Environment variables like `OLLAMA_BASE_URL` and `LOGFIRE_TOKEN` are configuration-level settings defined in `installation.yaml`, not CLI options.

## Common Workflows

### Development

```bash
# Start Ollama
ollama serve &

# Start backend with config reload
export OLLAMA_BASE_URL=http://localhost:11434
soliplex-cli serve example/minimal.yaml --no-auth-mode --reload config
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
soliplex-cli serve installation.yaml --no-auth-mode --log-level debug
```

---

## TUI Client

The TUI (Terminal User Interface) provides a terminal-based chat client for Soliplex.

### soliplex-tui

Start the terminal user interface client.

```bash
soliplex-tui [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | http://127.0.0.1:8000 | Backend server URL |
| `-v, --version` | - | Show version and exit |
| `-h, --help` | - | Show help |

**Examples:**
```bash
# Connect to local server
soliplex-tui --url http://127.0.0.1:8000

# Connect to remote server
soliplex-tui --url https://soliplex.example.com
```

**Keyboard Shortcuts:**

| Shortcut | Action |
|----------|--------|
| `Ctrl+Q` | Quit application |
| `Ctrl+N` | New thread |
| `Ctrl+T` | List threads |
| `Ctrl+R` | List runs |
| `Ctrl+Z` | Edit metadata |
| `Escape` | Exit/dismiss screen |
| `Enter` | Submit input |

**Note:** Some shortcuts require an active thread selection:
- `Ctrl+R`, `Ctrl+N`, `Ctrl+Z` are only available after selecting a thread

**Features:**

- OIDC authentication (login with configured identity providers)
- Room selection and navigation
- Thread management (create, select, view history)
- Run viewing with messages and events
- Metadata editing for threads and runs
- Real-time streaming responses
- Installation and room configuration viewing

**Screen Navigation:**

The TUI has a hierarchical screen structure:

1. **Room Selection** - Main screen showing available rooms
2. **Room Chat** (`Ctrl+Click` or `Enter` on room) - Chat interface for a room
3. **Thread List** (`Ctrl+T` from chat) - View all threads in the room
4. **Run List** (`Ctrl+R` from chat) - View runs in the current thread
5. **Run Details** (`Enter` on run) - Detailed view of a run with events

Use `Escape` to go back one level.

**Metadata Editing:**

Press `Ctrl+Z` to edit metadata in context:

- **From Room Chat view:** Edit thread metadata (name and description)
- **From Run Details view:** Edit run metadata (label)

A dialog appears with input fields. Press `Enter` to save or `Escape` to cancel.

**Authentication:**

The TUI supports two authentication modes:

**1. OIDC Authentication (Production)**

When connecting to a server with OIDC enabled, the TUI presents a login screen:

1. Select an OIDC provider from the list
2. Enter your username and password
3. The TUI authenticates via the provider's token endpoint
4. On success, you're taken to the room selection screen

```bash
# Start backend with OIDC configured
soliplex-cli serve production.yaml

# Connect TUI - login screen appears
soliplex-tui --url https://soliplex.example.com
```

**2. No-Auth Mode (Development)**

For local development without authentication:

```bash
# Terminal 1: Start backend without auth
soliplex-cli serve example/minimal.yaml --no-auth-mode

# Terminal 2: Connect TUI - no login required
soliplex-tui --url http://127.0.0.1:8000
```

### soliplex-tui-serve

Serve the TUI via web browser using textual-serve.

```bash
soliplex-tui-serve
```

Starts a web server on port 8002 that serves the TUI application, allowing browser-based access to the terminal interface.

**Use Case:** Access the TUI from a web browser when terminal access is not available or when sharing the interface remotely.
