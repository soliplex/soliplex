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
| **Flutter** | 3.x | [flutter.dev](https://flutter.dev) |
| **Ollama** | Latest | [ollama.com](https://ollama.com) |
| **Git** | Any | System package manager |

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

## Frontend Installation

### 1. Navigate to Flutter Directory

```bash
cd src/flutter
```

### 2. Install Dependencies

```bash
flutter pub get
```

### 3. Verify Installation

```bash
flutter doctor
```

## Configuration

### Minimal Configuration

The `example/minimal.yaml` file provides a working local setup:

```yaml
id: "soliplex-conf-minimal"

secrets:
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "random_chars"

environment:
  - "OLLAMA_BASE_URL"

agent_configs:
  - id: "default_chat"
    model_name: "gpt-oss:latest"
    system_prompt: |
      You are an expert AI assistant.

room_paths:
  - "./rooms/haiku"
  - "./rooms/joker"
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

# Terminal 3: Flutter
cd src/flutter
flutter run -d chrome --web-port 59001
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
│   ├── soliplex/          # Backend Python code
│   └── flutter/           # Frontend Flutter code
├── example/               # Example configurations
│   ├── minimal.yaml       # Minimal config
│   ├── installation.yaml  # Full config
│   └── rooms/             # Room configurations
├── db/                    # Databases (created at runtime)
│   └── rag/               # RAG vector store
└── venv/                  # Virtual environment
```

## Next Steps

- [First Chat](first-chat.md) - Use the chat interface
- [Room Configuration](../admin-guide/configuration/rooms.md) - Customize rooms
- [Agent Configuration](../admin-guide/configuration/agents.md) - Configure LLMs
