# Filesystem Layout

An installation is a set of filesystem-based configuration files organized as a directory tree.

## Installation Root

At the root of an installation directory is `installation.yaml`, which configures environment variables, secrets, and references to other configuration directories.

```
my-installation/
  installation.yaml           # Main configuration
  completions/               # Completion endpoints
    chat-bot/
      completion_config.yaml
      prompt.txt
  oidc/                      # OIDC provider configs
    cacert.pem
    config.yaml
  quizzes/                   # Quiz definitions
    quiz_name.json
  rooms/                     # Chat room configs
    research/
      prompt.txt
      room_config.yaml
      logo.png
```

## Directory Types

### Rooms Directory

Each room is a subdirectory containing:

| File | Required | Description |
|------|----------|-------------|
| `room_config.yaml` | Yes | Room metadata and configuration |
| `prompt.txt` | No | External system prompt file |
| `logo.png/jpg/svg` | No | Room logo image |

Example:
```
rooms/
  research/
    room_config.yaml
    prompt.txt
    logo.png
  legal/
    room_config.yaml
```

See [Rooms Configuration](rooms.md) for the `room_config.yaml` schema.

### Completions Directory

Each completion endpoint is a subdirectory containing:

| File | Required | Description |
|------|----------|-------------|
| `completion_config.yaml` | Yes | Completion configuration |
| `prompt.txt` | No | External system prompt file |

Example:
```
completions/
  chat-bot/
    completion_config.yaml
  code-assistant/
    completion_config.yaml
    prompt.txt
```

See [Completions Configuration](completions.md) for the `completion_config.yaml` schema.

### Quizzes Directory

Quiz files are JSON documents defining question sets:

```
quizzes/
  general_knowledge.json
  product_training.json
```

See [Quizzes Configuration](quizzes.md) for the quiz JSON schema.

### OIDC Directory

OIDC provider configurations:

| File | Description |
|------|-------------|
| `config.yaml` | Provider definitions |
| `*.pem` | Certificate files for token validation |

Example:
```
oidc/
  config.yaml
  keycloak.pem
  google.pem
```

See [OIDC Configuration](oidc.md) for the provider schema.

## Installation Configuration Reference

The `installation.yaml` file ties everything together:

```yaml
id: "my-installation"

# Configuration paths
room_paths:
  - "./rooms"

completion_paths:
  - "./completions"

oidc_paths:
  - "./oidc"

quizzes_paths:
  - "./quizzes"

# Environment and secrets
environment:
  - "OLLAMA_BASE_URL"
  - "DEFAULT_AGENT_MODEL"

secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "env_var"
        env_var_name: "OPENAI_API_KEY"

# Optional: haiku-rag configuration
haiku_rag_config_file: "./haiku_rag.yaml"

# Optional: Thread persistence
thread_persistence_dburi_sync: "sqlite:///threads.db"
thread_persistence_dburi_async: "sqlite+aiosqlite:///threads.db"

# Optional: Default agents (templates)
agents:
  - id: "ollama-default"
    model_name: "llama3.2"
    provider_type: "ollama"
```

## Path Resolution

### Relative Paths

All paths in configuration files are resolved relative to their location:

- `./rooms` in `installation.yaml` → `<installation_dir>/rooms`
- `./prompt.txt` in `room_config.yaml` → `<room_dir>/prompt.txt`

### Multiple Paths

Configuration paths can specify multiple directories:

```yaml
room_paths:
  - "./rooms"
  - "./additional-rooms"
  - "/shared/company-rooms"
```

Rooms from all paths are merged. Duplicate IDs result in an error.

## Ignored Files

The following are ignored during configuration loading:

- Directories starting with `.` (e.g., `.hidden/`)
- Files not matching expected patterns
- Backup files (e.g., `*.bak`, `*~`)

## Example: Minimal Installation

```
minimal/
  installation.yaml
  rooms/
    chat/
      room_config.yaml
```

`installation.yaml`:
```yaml
id: "minimal"
room_paths:
  - "./rooms"
```

`rooms/chat/room_config.yaml`:
```yaml
id: "chat"
agent:
  system_prompt: "You are a helpful assistant."
```

## Example: Production Installation

```
production/
  installation.yaml
  installation-docker.yaml     # Alternative config for containers
  rooms/
    research/
      room_config.yaml
      prompt.txt
      logo.png
    legal/
      room_config.yaml
      prompt.txt
  completions/
    api-chat/
      completion_config.yaml
  oidc/
    config.yaml
    keycloak.pem
  quizzes/
    onboarding.json
  haiku_rag.yaml
```

## Source Code

- Configuration loading: `src/soliplex/config.py`
- Installation dataclass: `src/soliplex/installation.py`
