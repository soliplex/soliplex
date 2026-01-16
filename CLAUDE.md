# CLAUDE.md

This file provides guidance for AI assistants working with the Soliplex codebase.

## Project Overview

Soliplex is an AI-powered Retrieval-Augmented Generation (RAG) system with a FastAPI backend, Flutter web frontend, and terminal UI. It provides semantic document retrieval, multi-room chat environments, and support for multiple LLM providers.

## Repository Structure

```
soliplex/
├── src/soliplex/           # Python backend source code
│   ├── views/              # FastAPI endpoint routers
│   ├── agui/               # AG-UI protocol implementation
│   ├── tui/                # Terminal user interface
│   ├── main.py             # FastAPI application setup
│   ├── cli.py              # Command-line interface
│   ├── config.py           # YAML configuration parsing
│   ├── installation.py     # Installation management
│   ├── agents.py           # Pydantic AI agent creation
│   ├── tools.py            # AI agent tool definitions
│   ├── mcp_server.py       # FastMCP server implementation
│   └── mcp_client.py       # MCP client toolsets
├── docs/                   # Documentation (MkDocs)
├── example/                # Example configurations
│   ├── rooms/              # Room configuration directories
│   ├── completions/        # Completion endpoint configs
│   ├── oidc/               # OIDC provider configs
│   └── quizzes/            # Quiz question files
├── tests/
│   ├── unit/               # Unit tests (100% coverage required)
│   └── functional/         # Integration tests requiring LLM
├── db/                     # Local database storage
└── schemas/                # AG-UI feature JSON schemas
```

## Build and Test Commands

```bash
# Install in development mode
pip install -e . --group dev

# Run unit tests with coverage (100% required)
pytest

# Run with specific coverage threshold
pytest --cov-fail-under=100

# Run linting
ruff check

# Check formatting
ruff format --check

# Start development server
soliplex-cli serve example/minimal.yaml --no-auth-mode

# Check configuration validity
soliplex-cli check-config example/minimal.yaml

# List configured rooms
soliplex-cli list-rooms example/minimal.yaml
```

## Key Technical Details

### Python Version

- Requires Python 3.12 or later
- pyproject.toml specifies `requires-python = ">=3.12"`
- ruff targets Python 3.13 (`target-version = "py313"`)

### Dependencies

- FastAPI for the REST API
- Pydantic AI (1.0.11+) for agent management
- haiku.rag-slim (0.25.0) for RAG functionality
- FastMCP (2.13.0+) for Model Context Protocol
- SQLModel for database models
- Uvicorn for ASGI server

### Configuration System

- YAML-based hierarchical configuration
- Installation config references rooms, completions, OIDC providers
- Environment variables resolved via `Installation.get_environment()`
- Secrets resolved via configurable source chain (env vars, files, subprocess, random)

### Entry Points

- `soliplex-cli` - Main backend CLI
- `soliplex-tui` - Terminal UI client
- `soliplex-tui-serve` - TUI server

## Code Style and Conventions

### Formatting

- Line length: 79 characters
- Single-line imports enforced by isort
- Ruff handles linting and formatting

### Testing

- Unit tests in `tests/unit/` with 100% coverage requirement
- Functional tests in `tests/functional/` (require LLM, skip by default)
- pytest-asyncio for async test support

### Configuration Classes

- Use dataclasses for configuration types
- `from_yaml` classmethod pattern for YAML parsing
- `_installation_config` and `_config_path` private fields for context

## Common Development Tasks

### Adding a New Tool

1. Define the tool function in `src/soliplex/tools.py`
2. If tool requires configuration, create a `ToolConfig` subclass in `config.py`
3. Register the config class in `TOOL_CONFIG_CLASSES_BY_TOOL_NAME`
4. Add to room configuration under `agent.tools`

### Adding a New Room

1. Create directory under `example/rooms/<room_id>/`
2. Add `room_config.yaml` with required fields: `id`, `name`, `description`, `agent`
3. Optionally add `prompt.txt` for external system prompt

### Adding API Endpoints

1. Create or modify router in `src/soliplex/views/`
2. Register router in `main.py` with appropriate prefix
3. Add unit tests with 100% coverage

## Important Files

- [pyproject.toml](pyproject.toml) - Package metadata, dependencies, tool configuration
- [src/soliplex/config.py](src/soliplex/config.py) - Configuration parsing (2500+ lines)
- [src/soliplex/main.py](src/soliplex/main.py) - FastAPI application factory
- [example/installation.yaml](example/installation.yaml) - Full configuration example

## Environment Variables

Key environment variables (see `.env.example` for complete list):

- `OLLAMA_BASE_URL` - Ollama server URL (without `/v1` suffix)
- `OPENAI_API_KEY` - OpenAI API key
- `SOLIPLEX_URL_SAFE_TOKEN_SECRET` - Token generation secret
- `LOGFIRE_TOKEN` - Pydantic Logfire token (optional)
- `RAG_LANCE_DB_PATH` - Path to RAG database directory
