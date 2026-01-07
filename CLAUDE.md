# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

### Backend (Python)

```bash
# Install in virtual environment
python3.13 -m venv venv
source venv/bin/activate
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"

# Run backend server
soliplex-cli serve example/minimal.yaml --no-auth-mode

# Validate configuration
soliplex-cli check-config example/minimal.yaml

# List configured rooms
soliplex-cli list-rooms example/minimal.yaml
```

### Testing & Linting

```bash
# Run unit tests (default - requires 100% coverage)
pytest

# Run single test file
pytest tests/unit/test_agents.py

# Run single test
pytest tests/unit/test_agents.py::test_function_name

# Run functional tests (requires LLM)
pytest tests/functional/

# Lint with ruff
ruff check src/

# Format code
ruff format src/
```

### Frontend (Flutter)

```bash
cd src/flutter

# Install dependencies
flutter pub get

# Run web app
flutter run -d chrome --web-port 59001

# Run tests
flutter test

# Analyze code (must have zero warnings)
flutter analyze

# Format code
dart format lib test
```

### TUI

```bash
# Install TUI dependencies
pip install -e ".[tui]"

# Run TUI client (requires backend with --no-auth-mode)
soliplex-tui --url http://127.0.0.1:8000
```

## Architecture Overview

### Multi-Component System

- **Backend** (`src/soliplex/`): Python 3.13+ FastAPI server handling RAG, AI agents, and API endpoints
- **Frontend** (`src/flutter/`): Flutter web/mobile/desktop app with Riverpod state management
- **TUI** (`src/soliplex/tui/`): Textual-based terminal client

### Backend Structure

- `views/` - FastAPI route handlers (auth, completions, rooms, quizzes, agui, installation)
- `agents.py` - Pydantic AI agent configuration and management with agent caching
- `config.py` - YAML configuration parsing with secret/environment variable resolution
- `tools.py` - AI agent tool definitions
- `mcp_server.py` / `mcp_client.py` - Model Context Protocol integration
- `agui/` - AG-UI protocol implementation for streaming responses (thread/run management, SSE events)
- `installation.py` - Installation dataclass managing config, secrets, rooms, agents, and MCP servers

### Configuration System

YAML-based configuration with hierarchical structure:
- **Installation** (`installation.yaml`) - Main config referencing other configs
- **Rooms** (`rooms/*/room_config.yaml`) - Chat environments with RAG settings
- **Completions** (`completions/*/completion_config.yaml`) - LLM provider/model configs
- **OIDC** (`oidc/*.yaml`) - Authentication providers

Example configs in `example/` directory. Use `example/minimal.yaml` for local development.

### Agent Configuration

Agents can be configured via:
1. **CompletionAgentConfig** - Standard LLM provider setup (Ollama, OpenAI)
2. **FactoryAgentConfig** - Custom agent factories for specialized behavior (see `src/flutter/SOLIPLEX.md`)

Factory agents support custom dependencies, tools, and dynamic system prompts via `@agent.system_prompt` decorator.

### Key Dependencies

- **haiku.rag-slim**: Vector database and RAG engine (LanceDB storage)
- **pydantic-ai-slim**: Agent framework for LLM integration (via haiku.rag-slim)
- **FastMCP**: Model Context Protocol server/client (>= 2.13.0.2, < 2.14)
- **ag-ui-protocol**: AG-UI streaming protocol (>= 0.1.10)
- **Textual**: TUI framework (install with `pip install -e ".[tui]"`)
- **Riverpod**: Flutter state management

### API Endpoints

REST API at `/api/v1/`:
- `GET /rooms/{room_id}/agui` - List threads
- `POST /rooms/{room_id}/agui` - Create thread with initial run
- `GET /rooms/{room_id}/agui/{thread_id}` - Get thread details
- `POST /rooms/{room_id}/agui/{thread_id}` - Create new run
- `POST /rooms/{room_id}/agui/{thread_id}/meta` - Update thread metadata
- `DELETE /rooms/{room_id}/agui/{thread_id}` - Delete thread
- `GET /rooms/{room_id}/agui/{thread_id}/{run_id}` - Get run details
- `POST /rooms/{room_id}/agui/{thread_id}/{run_id}` - Execute run (SSE stream)
- `POST /rooms/{room_id}/agui/{thread_id}/{run_id}/meta` - Update run metadata
- `POST /rooms/{room_id}/agui/{thread_id}/{run_id}/feedback` - Add run feedback

See `src/flutter/SOLIPLEX.md` for full API documentation.

### Test Structure

- `tests/unit/` - Unit tests (run by default, 100% coverage required)
- `tests/functional/` - Integration tests requiring LLM (marked with `@pytest.mark.needs_llm`)

## Flutter-Specific Notes

See `src/flutter/CLAUDE.md` for Flutter-specific guidance including:
- Platform-specific code patterns (`*_io.dart` / `*_web.dart`)
- Server-scoped provider pattern for panel state
- Zero-tolerance policy for analyzer warnings
- Documentation lifecycle system for feature work
