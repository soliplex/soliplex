# Installation Configuration

The installation configuration file (`installation.yaml`) is the root of Soliplex configuration.

## Quick Start

```yaml
# installation.yaml
id: "my-installation"

environment:
  - "OLLAMA_BASE_URL"

room_paths:
  - "./rooms"

agent_configs:
  - id: "default"
    model_name: "gpt-oss:latest"
```

## Configuration Reference

### id (required)

Unique identifier for this installation.

```yaml
id: "production-soliplex"
```

### environment

Non-secret environment variables. See [Environment](environment.md).

```yaml
environment:
  - "OLLAMA_BASE_URL"
  - name: "LOG_LEVEL"
    value: "INFO"
```

### secrets

Secret values (API keys, passwords). See [Secrets](secrets.md).

```yaml
secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "env_var"
        env_var_name: "OPENAI_API_KEY"
```

### agent_configs

Global agent definitions. See [Agents](agents.md).

```yaml
agent_configs:
  - id: "research_agent"
    model_name: "gpt-oss:latest"
    system_prompt: "You are a research assistant."
```

### room_paths

Paths to search for room configurations. See [Rooms](rooms.md).

```yaml
room_paths:
  - "./rooms"           # Relative to installation file
  - "/opt/rooms"        # Absolute path
```

Default: `["./rooms"]`

### completion_paths

Paths to search for completion configurations.

```yaml
completion_paths:
  - "./completions"
```

Default: `["./completions"]`

### oidc_paths

Paths to search for OIDC provider configurations. See [OIDC](oidc.md).

```yaml
oidc_paths:
  - "./oidc"
```

Default: `["./oidc"]`

To disable authentication:
```yaml
oidc_paths:
  -    # Empty entry
```

Or use CLI flag: `soliplex-cli serve --no-auth-mode`

### quizzes_paths

Paths to search for quiz data files. See [Quizzes](quizzes.md).

```yaml
quizzes_paths:
  - "./quizzes"
```

Default: `["./quizzes"]`

### thread_persistence_dburi

Database URIs for thread storage.

```yaml
thread_persistence_dburi:
  sync: "sqlite:///data/threads.db"
  async: "sqlite+aiosqlite:///data/threads.db"
```

Default (in-memory):
```yaml
thread_persistence_dburi:
  sync: "sqlite://"
  async: "sqlite+aiosqlite://"
```

**PostgreSQL example:**
```yaml
thread_persistence_dburi:
  sync: "postgresql+psycopg2://user:secret:DB_PASSWORD@dbhost/soliplex"
  async: "postgresql+asyncpg://user:secret:DB_PASSWORD@dbhost/soliplex"
```

**Note:** Use `secret:SECRET_NAME` to reference a configured secret.

### room_authz_dburi

Database URIs for room authorization policies. See [Authorization](authorization.md).

```yaml
room_authz_dburi:
  sync: "sqlite:///data/authz.db"
  async: "sqlite+aiosqlite:///data/authz.db"
```

Default (in-memory):
```yaml
room_authz_dburi:
  sync: "sqlite://"
  async: "sqlite+aiosqlite://"
```

**Note:** Without persistent storage, authorization policies are lost on server restart.

### haiku_rag_config_file

Path to haiku-rag configuration file.

```yaml
haiku_rag_config_file: "./haiku.rag.yaml"
```

Default: `haiku.rag.yaml` in the same directory as the installation file.

### meta

Meta-configuration for registering custom types. See [Meta Configuration](#meta-configuration).

```yaml
meta:
  tool_configs:
    - kind: "my_custom_tool"
      class: "mypackage.config.MyToolConfig"
```

## Directory Structure

Typical installation layout:

```
installation/
├── installation.yaml       # Main config
├── haiku.rag.yaml          # RAG config
├── oidc/
│   └── config.yaml         # OIDC providers
├── rooms/
│   ├── research/
│   │   ├── room_config.yaml
│   │   └── prompt.txt
│   └── chat/
│       └── room_config.yaml
├── completions/
│   └── default/
│       └── completion_config.yaml
├── quizzes/
│   └── intro.json
└── db/
    └── rag/
        └── knowledge.lancedb/
```

## Path Resolution

Relative paths are resolved from the installation file's directory:

```yaml
# If installation.yaml is at /opt/soliplex/installation.yaml
room_paths:
  - "./rooms"    # → /opt/soliplex/rooms
  - "../shared"  # → /opt/shared
```

## Meta Configuration

Register custom configuration types:

```yaml
meta:
  tool_configs:
    - kind: "weather"
      class: "mypackage.config.WeatherToolConfig"

  mcp_toolset_configs:
    - kind: "custom_mcp"
      class: "mypackage.config.CustomMCPConfig"
```

After registration, use in room configs:

```yaml
# rooms/weather/room_config.yaml
tools:
  - tool_name: "mypackage.tools.get_weather"
    kind: "weather"
    api_key_secret: "secret:WEATHER_API_KEY"
```

## Complete Example

```yaml
id: "production"

secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "URL_SAFE_TOKEN_SECRET"
      - kind: "random_chars"
        n_chars: 32

  - "OPENAI_API_KEY"  # Shorthand: reads from env var

environment:
  - "OLLAMA_BASE_URL"
  - name: "LOG_LEVEL"
    value: "INFO"

agent_configs:
  - id: "ollama_default"
    model_name: "gpt-oss:latest"
    system_prompt: |
      You are a helpful AI assistant.
      Be concise and accurate.

  - id: "openai_advanced"
    model_name: "gpt-4"
    provider_type: "openai"
    provider_key: "secret:OPENAI_API_KEY"

thread_persistence_dburi:
  sync: "sqlite:///data/threads.db"
  async: "sqlite+aiosqlite:///data/threads.db"

room_paths:
  - "./rooms"

completion_paths:
  - "./completions"

oidc_paths:
  - "./oidc"
```

## CLI Commands

```bash
# Validate configuration
soliplex-cli check-config installation.yaml

# List configured secrets
soliplex-cli list-secrets installation.yaml

# List environment variables
soliplex-cli list-environment installation.yaml

# List rooms
soliplex-cli list-rooms installation.yaml

# Start server
soliplex-cli serve installation.yaml
```

## Source Code

- Configuration parsing: `src/soliplex/config.py`
- Installation dataclass: `src/soliplex/installation.py`
