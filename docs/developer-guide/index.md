# Developer Guide

This guide covers the architecture, internals, and extension points of Soliplex for developers who want to understand how it works or contribute to the project.

## Overview

Soliplex is built on a modern Python stack:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | FastAPI + Pydantic AI | Async API server with LLM agent framework |
| **Database** | LanceDB + SQLite | Vector store for RAG, SQLite for thread persistence |
| **LLM** | Ollama / OpenAI | Local or cloud-based inference |
| **Protocol** | AG-UI | Streaming protocol for agent events |
| **TUI** | Textual | Terminal-based chat client |

!!! note "Frontend"
    The Flutter frontend is maintained in a [separate repository](https://github.com/soliplex/flutter).

## Sections

- **[Architecture](architecture.md)** - System design, component interactions, and data flow
- **[Agents](agents/index.md)** - Pydantic AI agents, configuration, factory agents, and tools
- **[RAG](rag/index.md)** - Document retrieval, vector storage, and citation system
- **[MCP](mcp/index.md)** - Model Context Protocol server and client integration
- **[API](api/index.md)** - REST endpoints, AG-UI protocol, and request/response models

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
| `src/soliplex/tui/main.py` | Terminal UI client |

## Development Workflow

```bash
# Backend development
source venv/bin/activate
pip install -e ".[dev]"
pytest                           # Run tests
ruff check src/                  # Lint
ruff format src/                 # Format

# TUI development
pip install -e ".[tui]"
soliplex-tui --url http://localhost:8000
```

## Contributing

See the [Contributing Guide](../contributing/index.md) for development setup, code style, and PR guidelines.