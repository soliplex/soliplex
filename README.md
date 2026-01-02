# Soliplex

An AI-powered Retrieval-Augmented Generation (RAG) system with a modern web interface.

## Features

- **RAG-Powered Search**: Semantic document retrieval using LanceDB vector database
- **Multi-Room Architecture**: Independent chat environments with separate configurations and knowledge bases
- **Multiple LLM Providers**: OpenAI, Ollama, and compatible APIs
- **AI Agent System**: Function calling and tool integration for AI agents
- **OIDC Authentication**: Enterprise SSO with Keycloak integration
- **Model Context Protocol (MCP)**: Extended AI capabilities through MCP client or exposing Room as MCP server
- **Real-time Communication**: WebSocket-based conversation streams
- **Quiz System**: Custom quizzes with LLM-based evaluation
- **Observability**: Logfire integration for monitoring

## Architecture

### Backend (`/src/soliplex/`)
**Python 3.13+ / FastAPI**

- **Core**: FastAPI application with async support
- **RAG Engine**: Haiku RAG (0.12.1+) with LanceDB vector storage
- **AI Integration**: Pydantic AI (1.0.11+) for agent management
- **Authentication**: Python-Keycloak with OIDC/JWT support
- **MCP**: FastMCP (2.12.3+) server and client implementations
- **Configuration**: YAML-based configuration system

Key modules:
- `views/` - API endpoints (auth, completions, conversations, rooms, quizzes)
- `agents.py` - AI agent configuration and management
- `agui/` - AG-UI thread persistence and retrieval
- `tools.py` - Tool definitions for AI agents
- `mcp_server.py` / `mcp_client.py` - Model Context Protocol integration
- `tui/` - Terminal user interface

### Frontend (`/src/flutter/`)
**Flutter 3.35+ / Dart 3.10.0+**

- **Framework**: Flutter web with Material Design
- **State Management**: Riverpod (2.6.1)
- **Navigation**: Go Router (16.0.0)
- **Authentication**: Flutter AppAuth (9.0.1) for OIDC
- **Real-time**: WebSocket communication
- **Secure Storage**: Flutter Secure Storage for credentials

Key files:
- `main.dart` - Application entry point
- `soliplex_client.dart` - Backend API client
- `oidc_client.dart` - OIDC authentication client
- `controllers.dart` - Riverpod state management
- `configure.dart` - Configuration UI

### TUI (`src/soliplex/tui`)

Quick-and-dirty client for room queries

- **Framework**: Python `textual`

## Quick Start

### Install Soliplex and dependencies

```bash
# Install
python3.13 -m venv venv
source venv/bin/activate
pip install -e .
```

### Index Soliplex docs into RAG database

```bash
source venv/bin/activate
export OLLAMA_BASE_URL=<your Ollama server / port>
# Run docling-serve if you have not installed the full haiku.rag
docker run -p 5001:5001 -d -e DOCLING_SERVE_ENABLE_UI=1 \
  quay.io/docling-project/docling-serve
haiku-rag --config example/haiku.rag.yaml \
  init --db  db/rag/rag.lancedb
haiku-rag --config example/haiku.rag.yaml \
  add-src --db db/rag/rag.lancedb docs/
...
17 documents added successfully.
```

See: `docs/rag.md` for more options.

### Check the backend server configuration

```bash
soliplex-cli check-config example/minimal.yaml
```

### List the rooms in the backend server configuration

```bash
soliplex-cli list-rooms example/minimal.yaml
```

### Run Soliplex backend server

```bash
export OLLAMA_BASE_URL=<your Ollama server / port>
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

### Frontend

```bash
cd src/flutter
flutter pub get
flutter run -d chrome --web-port 59001
```

### TUI

The TUI does not yet grok authentication, so run the back-end with
`--no-auth-mode` when using the TUI.

Within the virtual environment where you installed `soliplex`:

```bash
soliplex-tui --help
                                                                                
 Usage: soliplex-tui [OPTIONS]                                                  
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version             -v                                                     │
│ --url                                  TEXT  Base URL for Soliplex back-end  │
│                                              [default:                       │
│                                              http://127.0.0.1:8000]          │
│ --room                -r               TEXT  Room name for the agent         │
│                                              [default: haiku]                │
│ --agui                    --no-agui          Connect using Soliplex AG-UI    │
│                                              endpoint                        │
│                                              [default: agui]                 │
│ --install-completion                         Install completion for the      │
│                                              current shell.                  │
│ --show-completion                            Show completion for the current │
│                                              shell, to copy it or customize  │
│                                              the installation.               │
│ --help                -h                     Show this message and exit.     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

```bash
soliplex-tui
```

By default, the TUI connects to a Soliplex back-end server running
on port 8000 on your local machine, and uses the "haiku" romm, just
as though you typed:

```bash
soliplex-tui --url http://127.0.0.1:8000 --room haiku
```

## Configuration

YAML-based configuration with:
- **Installation** (`installation.yaml`) - Main config referencing agents, rooms, and OIDC providers
- **Rooms** (`rooms/*.yaml`) - Individual chat room configurations with RAG settings
- **Agents** (`completions/*.yaml`) - LLM provider and model configurations
- **OIDC** (`oidc/*.yaml`) - Authentication provider settings

See `example/` directory for sample configurations.

## License

MIT License - Copyright (c) 2025 Enfold Systems, Inc.
