# Secrets Configuration

Secrets are sensitive values like API keys and passwords. Soliplex supports multiple secret sources with fallback ordering.

## Quick Start

```yaml
secrets:
  - "OPENAI_API_KEY"  # Reads from environment variable
```

## Secret Sources

### Environment Variable

Read from an environment variable:

```yaml
secrets:
  - secret_name: "MY_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "MY_SECRET_ENV_VAR"
```

### File Path

Read from a file (e.g., Docker secrets):

```yaml
secrets:
  - secret_name: "MY_SECRET"
    sources:
      - kind: "file_path"
        file_path: "/run/secrets/my_secret"
```

### Subprocess Command

Execute a command to get the secret:

```yaml
secrets:
  - secret_name: "MY_SECRET"
    sources:
      - kind: "subprocess"
        command: "/usr/bin/fetch_secret"
        args:
          - "--secret-name=MY_SECRET"
```

### Random String

Generate a random string at startup:

```yaml
secrets:
  - secret_name: "SESSION_KEY"
    sources:
      - kind: "random_chars"
        n_chars: 32
```

## Source Layering

Sources are tried in order. First success wins:

```yaml
secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      # Try environment variable first
      - kind: "env_var"
        env_var_name: "URL_SAFE_TOKEN_SECRET"
      # Fall back to random generation
      - kind: "random_chars"
        n_chars: 32
```

## Shorthand Syntax

### Bare String

A bare string is equivalent to an environment variable source:

```yaml
secrets:
  - "OPENAI_API_KEY"
```

Is equivalent to:

```yaml
secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "env_var"
        env_var_name: "OPENAI_API_KEY"
```

### No Sources

A secret without sources defaults to environment variable:

```yaml
secrets:
  - secret_name: "MY_SECRET"
```

Is equivalent to:

```yaml
secrets:
  - secret_name: "MY_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "MY_SECRET"
```

## Using Secrets

### In Agent Configuration

```yaml
agent_configs:
  - id: "openai"
    model_name: "gpt-4"
    provider_type: "openai"
    provider_key: "secret:OPENAI_API_KEY"
```

### In Database URIs

```yaml
secrets:
  - secret_name: "DB_PASSWORD"
    sources:
      - kind: "env_var"
        env_var_name: "DB_PASSWORD"

thread_persistence_dburi:
  sync: "postgresql+psycopg2://user:secret:DB_PASSWORD@dbhost/db"
  async: "postgresql+asyncpg://user:secret:DB_PASSWORD@dbhost/db"
```

### In Tool Configuration

```yaml
tools:
  - tool_name: "mypackage.tools.external_api"
    api_key: "secret:EXTERNAL_API_KEY"
```

### In OIDC Configuration

```yaml
auth_systems:
  - id: "keycloak"
    client_secret: "secret:KEYCLOAK_CLIENT_SECRET"
```

### In MCP Headers

```yaml
mcp_client_toolsets:
  external:
    kind: "http"
    url: "https://api.example.com/mcp/"
    headers:
      Authorization: "secret:API_TOKEN"
```

## Common Secrets

| Secret | Purpose |
|--------|---------|
| `OPENAI_API_KEY` | OpenAI API access |
| `URL_SAFE_TOKEN_SECRET` | MCP token signing |
| `LOGFIRE_TOKEN` | Logfire observability |
| Database passwords | Thread persistence |
| OIDC client secrets | Authentication |

## Checking Secrets

Use the CLI to verify secret configuration:

```bash
$ soliplex-cli list-secrets installation.yaml

───────────────────────── Configured secrets ──────────────────────────────

- LOGFIRE_TOKEN             MISSING
- OPENAI_API_KEY            MISSING
- URL_SAFE_TOKEN_SECRET     OK

```

Secrets marked "MISSING" could not be resolved from any source.

## Best Practices

1. **Never commit secrets** - Use environment variables or external stores
2. **Use layering** - Provide fallbacks for development environments
3. **Generate random secrets** - For tokens that don't need to be shared
4. **Use Docker secrets** - For containerized deployments
5. **Validate before deploy** - Run `list-secrets` to check configuration

## Docker Secrets Example

```yaml
# docker-compose.yml
services:
  soliplex:
    secrets:
      - openai_api_key
      - db_password

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  db_password:
    file: ./secrets/db_password.txt
```

```yaml
# installation.yaml
secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "file_path"
        file_path: "/run/secrets/openai_api_key"

  - secret_name: "DB_PASSWORD"
    sources:
      - kind: "file_path"
        file_path: "/run/secrets/db_password"
```

## Source Code

- Secret configuration: `src/soliplex/config.py`
- Secret resolution: `src/soliplex/installation.py`
