# Configuration

Soliplex uses YAML-based configuration with a hierarchical structure supporting installations, rooms, agents, and secrets.

## Configuration Hierarchy

```
installation.yaml                    # Main entry point
├── secrets:                         # Secret definitions
├── environment:                     # Environment variables
├── agent_configs:                   # Global agent configs
├── room_paths:                      # → rooms/*/room_config.yaml
├── completion_paths:                # → completions/*/completion_config.yaml
└── oidc_paths:                      # → oidc/*.yaml
```

## Sections

- **[Installation](installation.md)** - Main installation.yaml configuration
- **[Agents](agents.md)** - Agent configuration and templates
- **[Rooms](rooms.md)** - Room configuration with tools and RAG
- **[RAG](rag.md)** - RAG and haiku-rag configuration
- **[Secrets](secrets.md)** - Secret management and sources
- **[Environment](environment.md)** - Environment variable configuration
- **[OIDC](oidc.md)** - OpenID Connect provider configuration
- **[Quizzes](quizzes.md)** - Quiz configuration

## Quick Start

### Minimal Configuration

```yaml
# minimal.yaml
id: "soliplex-minimal"

secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "random_chars"

environment:
  - "OLLAMA_BASE_URL"

agent_configs:
  - id: "default_chat"
    model_name: "gpt-oss:latest"
    system_prompt: "You are a helpful assistant."

room_paths:
  - "./rooms/default"
```

### Validate Configuration

```bash
soliplex-cli check-config path/to/installation.yaml
```

## Configuration Patterns

### Secret Interpolation

Secrets can be referenced in configs:

```yaml
provider_key: "secret:OPENAI_API_KEY"
```

### File References

Paths can reference files:

```yaml
system_prompt: "./prompts/research.md"  # Loads from file
```

### Environment Variables

Configure environment variables with optional `.env` file override:

```yaml
environment:
  - "OLLAMA_BASE_URL"                    # Read from .env or os.environ
  - name: "RAG_LANCE_DB_PATH"
    value: "file:./db/rag"               # .env can override this value
```

## Example Configurations

See the `example/` directory for complete examples:

- `example/minimal.yaml` - Minimal local setup
- `example/installation.yaml` - Full configuration
- `example/rooms/` - Room configurations
