# Soliplex

*Production RAG without the framework tax.*

A complete, hackable RAG system you can actually read and modify.

## Why Soliplex?

Most RAG tutorials are toy examples. Most RAG frameworks are black boxes. Soliplex sits in between: a **full-stack, production-style RAG system** built for understanding and customization.

**Philosophy:**
- **Composition over framework** — Thin configuration layer over best-in-class libraries (pydantic-ai, haiku-rag, FastMCP), not abstractions that hide them
- **Full-stack reference** — Backend, frontend, CLI, and evaluation pipeline in one repo
- **Hackable by design** — Fork it, read it, make it yours

**What you get:**
- FastAPI backend with AG-UI streaming protocol
- Cross-platform Flutter client (web, desktop, mobile) — *prototype until 1.0*
- Efficient document ingestion via Haiku RAG
- Evaluation pipeline using pydantic-evals *(coming soon)*

**Who is this for?**
- Developers building custom RAG applications
- Teams wanting a reference implementation to fork
- Learners studying production RAG architecture

**When NOT to use Soliplex:**
- You want a turnkey, hosted solution
- You need a stable, supported framework (we're pre-1.0)
- You're not comfortable reading and modifying source code
- You want to swap out core libraries (pydantic-ai, SQLAlchemy, haiku-rag)

## Features

- **RAG-Powered Search**: Semantic document retrieval using LanceDB vector database
- **Multi-Room Architecture**: Independent chat environments with separate configurations and knowledge bases
- **Multiple LLM Providers**: OpenAI, Ollama, and compatible APIs
- **AI Agent System**: Function calling and tool integration for AI agents
- **OIDC Authentication**: Enterprise SSO with Keycloak integration
- **Model Context Protocol (MCP)**: Extended AI capabilities through MCP client or exposing Room as MCP server
- **Real-time Communication**: SSE-based conversation streams
- **Quiz System**: Custom quizzes with LLM-based evaluation
- **Observability**: Logfire integration for monitoring

## Architecture

### Backend (`/src/soliplex/`)
**Python 3.13+ / FastAPI**

- **Core**: FastAPI application with async support
- **RAG Engine**: Haiku RAG with LanceDB vector storage
- **Protocol**: AG-UI for streaming agent responses
- **Authentication**: Python-Keycloak with OIDC/JWT support
- **MCP**: FastMCP server and client implementations
- **Database**: SQLAlchemy async for thread persistence
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
- **State Management**: Riverpod
- **Navigation**: Go Router
- **Authentication**: Flutter AppAuth for OIDC
- **Real-time**: Server-Sent Events (SSE) streaming
- **Secure Storage**: Flutter Secure Storage for credentials

Key modules:
- `core/auth/` - OIDC authentication (oidc_client.dart, auth_providers.dart)
- `core/network/` - Backend communication (room_session.dart, connection_manager.dart)
- `core/providers/` - Riverpod state management (app_providers.dart, panel_providers.dart)
- `features/` - UI features (chat, settings, configure)

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
on port 8000 on your local machine, and uses the "haiku" room, just
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
