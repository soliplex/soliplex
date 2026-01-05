# Configuration Schema Reference

Complete YAML schema reference for Soliplex configuration.

## Installation Configuration

```yaml
# installation.yaml
id: string                          # Required: Unique installation ID

# Secrets configuration
secrets:
  - secret_name: string             # Secret identifier
    sources:                        # Resolution sources (in order)
      - kind: "env_var"             # Environment variable
        env_var_name: string
      - kind: "file_path"           # File contents
        file_path: string
      - kind: "subprocess"          # Command output
        command: string
        args: [string]
      - kind: "random_chars"        # Generated random string
        n_chars: integer            # Default: 32
  - string                          # Shorthand: env var with same name

# Environment configuration
environment:
  - name: string                    # Variable name
    value: string                   # Optional: explicit value
  - string                          # Shorthand: read from os.environ

# Agent configurations (global templates)
agent_configs:
  - id: string                      # Required: unique agent ID
    model_name: string              # Required: LLM model name
    provider_type: string           # "ollama" (default) | "openai"
    provider_base_url: string       # Override provider URL
    provider_key: string            # "secret:SECRET_NAME"
    system_prompt: string           # Inline text or "./file.txt"
    retries: integer                # Retry count (default: 3)
    model_settings:
      temperature: float            # 0-1
      top_p: float                  # Nucleus sampling
      max_tokens: integer           # Max response length

# Thread persistence database
thread_persistence_dburi:
  sync: string                      # Sync DBURI (psycopg2, sqlite)
  async: string                     # Async DBURI (asyncpg, aiosqlite)

# haiku-rag configuration file
haiku_rag_config_file: string       # Path to haiku.rag.yaml

# Path configuration
room_paths: [string]                # Room config directories
completion_paths: [string]          # Completion config directories
oidc_paths: [string]                # OIDC config directories

# Meta-configuration (advanced)
meta:
  agui_features:                    # AG-UI feature registrations
    - name: string                  # Feature name in AG-UI state
      model_klass: string           # Dotted import path to Pydantic model
      source: string                # "client", "server", or "either" (default)
  tool_configs:                     # Custom tool config classes
    - string                        # Dotted import path
    - config_klass: string          # Or explicit mapping
      wrapper_klass: string
  mcp_toolset_configs:              # Custom MCP toolset classes
    - string
  mcp_server_tool_wrappers:         # MCP tool wrappers
    - config_klass: string
      wrapper_klass: string
  agent_configs:                    # Custom agent config classes
    - config_klass: string
  secret_sources:                   # Custom secret source classes
    - config_klass: string
      registered_func: string
```

## Room Configuration

```yaml
# rooms/{room_id}/room_config.yaml
id: string                          # Required: matches directory name
name: string                        # Required: display name
description: string                 # Required: room description

# Agent configuration
agent:
  kind: string                      # "default" (default) | "factory"
  model_name: string                # LLM model name
  provider_type: string             # "ollama" | "openai"
  provider_base_url: string
  provider_key: string              # "secret:SECRET_NAME"
  system_prompt: string             # Inline or "./prompt.txt"
  retries: integer
  model_settings:
    temperature: float
    top_p: float
    max_tokens: integer
  template_id: string               # Reference global agent config
  # Factory agent options (kind: "factory")
  factory_name: string              # Python import path
  with_agent_config: boolean        # Pass config to factory (default: false)
  extra_config: object              # Custom parameters

# Tool configurations
tools:
  - tool_name: string               # Required: Python import path
    allow_mcp: boolean              # Expose via MCP (default: false)
    # RAG tool options
    rag_lancedb_stem: string        # Database in RAG_LANCE_DB_PATH
    rag_lancedb_override_path: string  # Explicit database path
    search_documents_limit: integer # Max results (default: 5)
    haiku_rag_config: object        # haiku-rag overrides

# MCP client toolsets
mcp_client_toolsets:
  {name}:
    kind: "stdio"
    command: string
    args: [string]
    env: {string: string}
    allowed_tools: [string]
  {name}:
    kind: "http"
    url: string
    headers: {string: string}       # Can use "secret:NAME"
    query_params: {string: string}
    allowed_tools: [string]

# MCP server
allow_mcp: boolean                  # Enable MCP server for room (default: false)

# UI options
_order: string                      # Sort key (defaults to id)
welcome_message: string             # Displayed on room entry
suggestions: [string]               # Starter questions
enable_attachments: boolean         # Allow file attachments (default: false)
logo_image: string                  # Room logo path

# Quizzes
quizzes:
  - id: string                      # Quiz ID
    title: string                   # Display title (default: "Quiz")
    question_file: string           # Path to JSON (stem or path)
    randomize: boolean              # Randomize questions (default: false)
    max_questions: integer          # Limit questions
    judge_agent:                    # Optional: custom judge agent
      model_name: string
      system_prompt: string
```

## OIDC Configuration

```yaml
# oidc/config.yaml
oidc_client_pem_path: string        # Default CA cert for all auth_systems

auth_systems:
  - id: string                      # Required: provider ID
    title: string                   # Required: display name
    server_url: string              # Required: OIDC server URL
    client_id: string               # Required: OAuth client ID
    client_secret: string           # "secret:SECRET_NAME" or literal
    scope: string                   # OAuth scopes
    token_validation_pem: string    # Required: public key PEM content
    oidc_client_pem_path: string    # CA cert (overrides file-level default)
```

## Completion Configuration

```yaml
# completions/{id}/completion_config.yaml
id: string                          # Required: completion ID
name: string                        # Display name (defaults to id)
agent:
  model_name: string
  provider_type: string
  system_prompt: string
  # ... same as room agent options

# Tool configurations (same as room)
tools:
  - tool_name: string
    # ... same as room tools

# MCP client toolsets (same as room)
mcp_client_toolsets:
  {name}:
    kind: "stdio" | "http"
    # ... same as room mcp_client_toolsets
```

## haiku-rag Configuration

```yaml
# haiku.rag.yaml
# See https://ggozad.github.io/haiku.rag/configuration/
environment: string                 # "development" | "production"

storage:
  data_dir: string
  vacuum_retention_seconds: integer

embeddings:
  model:
    name: string                    # Embedding model name
    provider: string                # "ollama" | "openai"
    vector_dim: integer             # Vector dimensions

qa:
  model:
    name: string
    provider: string

research:
  model:
    name: string
    provider: string
  max_iterations: integer
  confidence_threshold: float
  max_concurrency: integer

processing:
  chunk_size: integer               # Max chunk tokens
  converter: string                 # "docling-serve" for remote
  chunker: string                   # "docling-serve" for remote

search:
  context_radius: integer           # Surrounding chunks to include

providers:
  ollama:
    base_url: string                # Auto-set from OLLAMA_BASE_URL
  docling_serve:
    base_url: string
```

## Type Reference

### Secret Source Kinds

| Kind | Required Fields | Optional |
|------|-----------------|----------|
| `env_var` | `env_var_name` | |
| `file_path` | `file_path` | |
| `subprocess` | `command`, `args` | |
| `random_chars` | | `n_chars` (default: 32) |

### Provider Types

| Type | Description |
|------|-------------|
| `ollama` | Local Ollama server (default) |
| `openai` | OpenAI-compatible API |

### Agent Kinds

| Kind | Description |
|------|-------------|
| `default` | Standard LLM agent (default) |
| `factory` | Custom agent factory |

### Tool Requirements

| Requirement | MCP Compatible |
|-------------|----------------|
| `BARE` | Yes |
| `TOOL_CONFIG` | Yes |
| `FASTAPI_CONTEXT` | No |

### MCP Transport Kinds

| Kind | Description |
|------|-------------|
| `stdio` | Subprocess with stdin/stdout |
| `http` | HTTP streaming transport |
