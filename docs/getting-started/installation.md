# Installation Guide

Complete installation instructions for all Soliplex components.

## System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 4 cores | 8+ cores |
| **RAM** | 8 GB | 16+ GB (32+ for large models) |
| **Storage** | 10 GB | 50+ GB (models take space) |
| **GPU** | None | Apple Silicon or NVIDIA GPU |

### Software

| Requirement | Version | Installation |
|-------------|---------|--------------|
| **Python** | 3.13+ | [python.org](https://python.org) |
| **Ollama** | Latest | [ollama.com](https://ollama.com) |
| **Git** | Any | System package manager |

!!! note "Frontend"
    The Flutter frontend is maintained in a separate repository at [github.com/soliplex/flutter](https://github.com/soliplex/flutter).

## Backend Installation

### 1. Clone Repository

```bash
git clone https://github.com/soliplex/soliplex.git
cd soliplex
```

### 2. Create Virtual Environment

```bash
python3.13 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Basic installation
pip install -e .

# With development tools
pip install -e ".[dev]"
```

### 4. Verify Installation

```bash
soliplex-cli --help
```

## LLM Setup (Ollama)

### 1. Install Ollama

**macOS (Apple Silicon)**:
```bash
# Use ARM64 Homebrew for best performance
/opt/homebrew/bin/brew install ollama
```

**macOS (Intel)**:
```bash
brew install ollama
```

**Linux**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Start Ollama Server

```bash
ollama serve
```

### 3. Pull a Model

```bash
# Default model for minimal config
ollama pull gpt-oss

# Or use other models
ollama pull llama3
ollama pull mistral
```

### 4. Verify GPU Acceleration

```bash
ollama ps
```

Look for GPU usage in the output. If showing 100% CPU on Apple Silicon, you may have an x86_64 binary - reinstall using ARM64 Homebrew.

## Frontend Installation (Optional)

The Flutter frontend is maintained in a separate repository. To use the web UI:

```bash
# Clone the Flutter repo as a sibling directory
git clone https://github.com/soliplex/flutter ../flutter
cd ../flutter
flutter pub get
```

See the [Flutter repository](https://github.com/soliplex/flutter) for full installation instructions.

!!! tip "Alternative: TUI Client"
    Soliplex includes a built-in terminal UI client. Install with `pip install -e ".[tui]"` and run with `soliplex-tui --url http://localhost:8000`.

## Configuration

### Minimal Configuration

The `example/minimal.yaml` file provides a working local setup. Key sections:

```yaml
id: "soliplex-conf-minimal"

secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "SOLIPLEX_URL_SAFE_TOKEN_SECRET"
      - kind: "random_chars"  # Fallback if env var not set

environment:
  - "OLLAMA_BASE_URL"
  - name: "INSTALLATION_PATH"
    value: "file:."
  - name: "RAG_LANCE_DB_PATH"
    value: "file:../db/rag"

haiku_rag_config_file: "./haiku.rag.yaml"

agent_configs:
  - id: "default_chat"
    model_name: "gpt-oss:latest"
    system_prompt: |
      You are an expert AI assistant specializing in information retrieval.

      Your answers should be clear, concise, and ready for production use.

      Always provide code or examples in Markdown blocks.

thread_persistence_dburi:
  sync: "sqlite://"          # In-memory (threads lost on restart)
  async: "sqlite+aiosqlite://"

room_paths:
  - "./rooms/ask_soliplex"
  - "./rooms/haiku"
  - "./rooms/joker"
  - "./rooms/faux"
  - "./rooms/quiztest"
  - "./rooms/research"
```

### Full Configuration

See `example/installation.yaml` for a complete configuration with:

- Multiple rooms
- OIDC authentication
- MCP integrations
- RAG databases

## Starting Services

### All-in-One (Development)

Start all services manually:

```bash
# Terminal 1: Ollama
ollama serve

# Terminal 2: Backend
source venv/bin/activate
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  soliplex-cli serve example/minimal.yaml --no-auth-mode

# Terminal 3 (Optional): Flutter - if you have the frontend cloned
cd ../flutter
flutter run -d chrome --web-port 59001 --dart-define=DEFAULT_SERVER_URL=http://localhost:8000

# Or use the TUI client:
soliplex-tui --url http://localhost:8000
```

### Validate Configuration

Before starting, validate your config:

```bash
soliplex-cli check-config example/minimal.yaml
```

## Directory Structure

After installation:

```
soliplex/
├── src/
│   └── soliplex/          # Backend Python code
├── example/               # Example configurations
│   ├── minimal.yaml       # Minimal config
│   ├── installation.yaml  # Full config
│   └── rooms/             # Room configurations
├── db/                    # Databases (created at runtime)
│   └── rag/               # RAG vector store
└── venv/                  # Virtual environment
```

!!! note "Frontend Repository"
    The Flutter frontend is maintained at [github.com/soliplex/flutter](https://github.com/soliplex/flutter). Clone it as `../flutter` for local development.

## Next Steps

- [First Chat](first-chat.md) - Use the chat interface
- [Room Configuration](../admin-guide/configuration/rooms.md) - Customize rooms
- [Agent Configuration](../admin-guide/configuration/agents.md) - Configure LLMs
