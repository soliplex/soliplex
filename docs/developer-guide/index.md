# Developer Guide

This guide covers the architecture, internals, and extension points of Soliplex for developers who want to understand how it works or contribute to the project.

## Overview

Soliplex is built on a modern Python + Flutter stack:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Flutter + Riverpod | Cross-platform UI with reactive state management |
| **Backend** | FastAPI + Pydantic AI | Async API server with LLM agent framework |
| **Database** | LanceDB + SQLite | Vector store for RAG, SQLite for thread persistence |
| **LLM** | Ollama / OpenAI | Local or cloud-based inference |
| **Protocol** | AG-UI | Streaming protocol for agent events |

## Sections

- **[Architecture](architecture.md)** - System design, component interactions, and data flow
- **[Agents](agents/index.md)** - Pydantic AI agents, configuration, factory agents, and tools
- **[RAG](rag/index.md)** - Document retrieval, vector storage, and citation system
- **[MCP](mcp/index.md)** - Model Context Protocol server and client integration
- **[API](api/index.md)** - REST endpoints, AG-UI protocol, and request/response models
- **[Flutter](flutter/index.md)** - Frontend architecture, state management, and widgets

## Key Source Files

| File | Purpose |
|------|---------|
| `src/soliplex/agents.py` | Agent creation, caching, and dependencies |
| `src/soliplex/tools.py` | Built-in tool implementations |
| `src/soliplex/config.py` | YAML configuration parsing |
| `src/soliplex/installation.py` | Installation management |
| `src/soliplex/views/agui.py` | AG-UI streaming endpoint |
| `src/soliplex/mcp_server.py` | MCP server implementation |
| `src/soliplex/mcp_client.py` | MCP client connections |
| `src/flutter/lib/` | Flutter application source |

## Development Workflow

```bash
# Backend development
source venv/bin/activate
pip install -e ".[dev]"
pytest                           # Run tests
ruff check src/                  # Lint
ruff format src/                 # Format

# Frontend development
cd src/flutter
flutter pub get
flutter test                     # Run tests
flutter analyze                  # Lint (zero warnings required)
dart format lib test             # Format
```

## Contributing

See the [Contributing Guide](../contributing/index.md) for development setup, code style, and PR guidelines.