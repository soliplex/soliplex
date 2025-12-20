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
        n_chars: integer
  - string                          # Shorthand: env var with same name

# Environment configuration
environment:
  - name: string                    # Variable name
    value: string                   # Optional: explicit value
  - string                          # Shorthand: read from os.environ

# Agent configurations (global)
agent_configs:
  - id: string                      # Required: unique agent ID
    model_name: string              # Required: LLM model name
    provider_type: string           # "ollama" | "openai"
    provider_base_url: string       # Override provider URL
    provider_key: string            # "secret:SECRET_NAME"
    system_prompt: string           # Inline or file path
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

# Meta-configuration
meta:
  tool_config_kinds:
    - kind: string                  # Custom tool kind name
      class: string                 # Python class path
  mcp_client_toolset_kinds:
    - kind: string
      class: string
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
  template_id: string               # Reference global agent
  # Factory agent options
  factory_name: string              # Python import path
  with_agent_config: boolean        # Pass config to factory
  extra_config: object              # Custom parameters

# Tool configurations
tools:
  - tool_name: string               # Required: Python import path
    allow_mcp: boolean              # Expose via MCP
    # RAG tool options
    rag_lancedb_stem: string        # Database in db/rag/
    rag_lancedb_override_path: string  # Explicit database path
    search_documents_limit: integer # Max results
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
allow_mcp: boolean                  # Enable MCP server for room

# UI options
welcome_message: string             # Displayed on room entry
suggestions: [string]               # Starter questions
enable_attachments: boolean         # Allow file attachments
logo_image: string                  # Room logo path
sort_key: integer                   # Sort order

# Quizzes
quizzes:
  - id: string                      # Quiz ID
    title: string                   # Display title
    question_file: string           # Path to JSON
    randomize: boolean              # Randomize questions
    max_questions: integer          # Limit questions
```

## OIDC Configuration

```yaml
# oidc/config.yaml
oidc_client_pem_path: string        # CA certificate file

auth_systems:
  - id: string                      # Required: provider ID
    title: string                   # Required: display name
    server_url: string              # Required: OIDC server URL
    client_id: string               # Required: OAuth client ID
    client_secret: string           # "secret:SECRET_NAME"
    scope: string                   # OAuth scopes
    token_validation_pem: string    # Required: public key PEM
```

## Completion Configuration

```yaml
# completions/{id}/completion_config.yaml
id: string                          # Required: completion ID
agent:
  model_name: string
  provider_type: string
  system_prompt: string
  # ... same as room agent options
```

## haiku-rag Configuration

```yaml
# haiku.rag.yaml
embedding:
  model: string                     # Embedding model name
  dimensions: integer               # Vector dimensions

search:
  context_radius: integer           # Surrounding chunks
  rerank: boolean                   # Enable reranking
  limit: integer                    # Default limit

chunking:
  strategy: string                  # "semantic" | "fixed"
  max_size: integer                 # Max chunk tokens
  overlap: integer                  # Chunk overlap
```

## Type Reference

### Secret Source Kinds

| Kind | Required Fields |
|------|-----------------|
| `env_var` | `env_var_name` |
| `file_path` | `file_path` |
| `subprocess` | `command`, `args` |
| `random_chars` | `n_chars` |

### Provider Types

| Type | Description |
|------|-------------|
| `ollama` | Local Ollama server |
| `openai` | OpenAI API |

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
