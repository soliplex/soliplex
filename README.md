# Soliplex

An AI-powered Retrieval-Augmented Generation (RAG) system with a modern web interface.

## Features

- **RAG-Powered Search**: Semantic document retrieval using LanceDB vector database
- **Multi-Room Architecture**: Independent chat environments (rooms) with separate configurations and knowledge bases
- **Multiple LLM Providers**: OpenAI, Ollama, Google Gemini, Anthropic, Groq, and compatible APIs
- **AI Agent System**: Function calling and tool integration for AI agents
- **OIDC Authentication**: Enterprise SSO with Keycloak integration
- **Model Context Protocol (MCP)**: Extended AI capabilities through MCP client or exposing Room as MCP server
- **Real-time Communication**: [AG-UI](https://docs.ag-ui.com/introduction) streams over [SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- **Quiz System**: Custom quizzes with LLM-based evaluation
- **Observability**: Logfire integration for monitoring

## Architecture

### Backend (`/src/soliplex/`)

**Python 3.12+ / FastAPI**

- **Core**: FastAPI application with async support
- **RAG Engine**: [haiku.rag-slim](https://pypi.org/project/haiku.rag-slim/)
  with LanceDB vector storage
- **AI Integration**: [Pydantic AI](https://pypi.org/project/pydantic-ai/)
  for agent management
- **Authentication**: Python-Keycloak with OIDC/JWT support
- **MCP**: [FastMCP](https://pypi.org/project/fastmcp/) server and client
  implementations
- **Configuration**: YAML-based configuration system

Key modules:
- `views/` - API endpoints (auth, completions, conversations, rooms, quizzes)
- `agents.py` - AI agent configuration and management
- `agui/` - AG-UI thread persistence and retrieval
- `tools/` - Tool definitions for AI agents
- `mcp_server.py` / `mcp_client.py` - Model Context Protocol integration
- `tui/` - Terminal user interface

### Frontend

The Flutter client lives in its own
[repository](https://github.com/soliplex/frontend).

**Flutter 3.35+ / Dart 3.10.0+**

- **Framework**: Flutter web with Material Design
- **State Management**: Riverpod (2.6.1)
- **Navigation**: Go Router (16.0.0)
- **Authentication**: Flutter AppAuth (9.0.1) for OIDC
- **Real-time**: WebSocket communication
- **Secure Storage**: Flutter Secure Storage for credentials

### TUI (`src/soliplex/tui`)

Quick-and-dirty client for room queries

- **Framework**: Python `textual`

## Quick Start

For detailed installation instructions, see the [Prerequisites Guide](docs/prerequisites.md).

### Install Soliplex and dependencies

```bash
# Install (requires uv: https://docs.astral.sh/uv/)
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your settings
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

### Backend Server CLI Commands

The `soliplex-cli` command provides several utilities for managing your Soliplex installation:

#### Check Configuration

Validate your configuration file and report any missing secrets or environment variables:

```bash
soliplex-cli check-config example/minimal.yaml
```

#### List Rooms

Show all configured chat rooms:

```bash
soliplex-cli list-rooms example/minimal.yaml
```

#### List Completions

Show all configured completion endpoints:

```bash
soliplex-cli list-completions example/minimal.yaml
```

#### List Secrets

Display all configured secrets and their status:

```bash
soliplex-cli list-secrets example/minimal.yaml
```

#### List Environment Variables

Show all environment variables and their values:

```bash
soliplex-cli list-environment example/minimal.yaml
```

#### List OIDC Providers

Display configured OIDC authentication providers:

```bash
soliplex-cli list-oidc-auth-providers example/minimal.yaml
```

#### Export Configuration

Export the installation configuration as YAML:

```bash
soliplex-cli config example/minimal.yaml
```

#### Export AG-UI Feature Schemas

Export AG-UI feature schemas as JSON:

```bash
soliplex-cli agui-feature-schemas example/minimal.yaml
```

#### Run Backend Server

Start the Soliplex backend server:

```bash
export OLLAMA_BASE_URL=<your Ollama server / port>
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

Server options:
- `--no-auth-mode` - Disable authentication (for development/testing)
- `--host HOST` - Bind to specific host (default: 127.0.0.1)
- `--port PORT` - Listen on specific port (default: 8000)
- `--reload {python,config,both}` - Enable hot reload for python code, config, or both
- `--reload-dirs DIRS` - Additional directories to watch for reload
- `--reload-includes PATTERNS` - File patterns to include in reload watch
- `--proxy-headers` - Enable proxy header parsing
- `--forwarded-allow-ips IPS` - Trusted IP addresses for proxy headers

### Frontend

```bash
cd src/flutter
flutter pub get
flutter run -d chrome --web-port 59001
```

### TUI

The TUI does not yet support authentication, so run the back-end with
`--no-auth-mode` when using the TUI.

Within the virtual environment where you installed `soliplex`:

```bash
soliplex-tui --help

 Usage: soliplex-tui [OPTIONS]

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version             -v                                                     │
│ --url                      TEXT  Base URL for Soliplex back-end              │
│                                  [default: http://127.0.0.1:8000]            │
│ --help                -h         Show this message and exit.                 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

```bash
soliplex-tui
```

By default, the TUI connects to a Soliplex back-end server running
on port 8000 on your local machine:

```bash
soliplex-tui --url http://127.0.0.1:8000
```

## Development

This project uses [PEP 735 Dependency Groups](https://peps.python.org/pep-0735/)
for managing development dependencies. This is the modern standard supported by
`uv` and recent versions of `pip`.

### Installing dev dependencies

```bash
# Using pip (requires pip 24.0+)
pip install -e . --group dev

# Using uv (recommended)
uv sync --group dev
```

**Note:** The older syntax `pip install -e ".[dev]"` is for `[project.optional-dependencies]`
and will NOT work with `[dependency-groups]`. Always use `--group dev` instead.

### Available dependency groups

| Group | Purpose |
|-------|---------|
| `dev` | Testing tools (pytest, ruff, coverage) |
| `docs` | Documentation (mkdocs, mkdocs-material) |
| `postgres` | PostgreSQL support (asyncpg) |
| `tui` | Terminal UI (textual, typer) |

### Running tests

```bash
# Run unit tests with coverage
pytest

# Run with specific coverage threshold (CI enforces 100%)
pytest --cov-fail-under=100

# Run linting
ruff check

# Check formatting
ruff format --check
```

## Configuration

YAML-based configuration with:
- **Installation** (`installation.yaml`) - Main config referencing agents, rooms, and OIDC providers
- **Rooms** (`rooms/*.yaml`) - Individual chat room configurations with RAG settings
- **Agents** (`completions/*.yaml`) - LLM provider and model configurations
- **OIDC** (`oidc/*.yaml`) - Authentication provider settings

See `example/` directory for sample configurations.

### Environment Variables

See the [environment](docs/server/environment.md) docs for an explanation
of when to configure Soliplex using OS environment variables.

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Prerequisites Guide](docs/prerequisites.md)** - Step-by-step installation checklist
- **[Server Setup](docs/server/index.md)** - Backend server configuration and CLI reference
- **[Client Setup](docs/client.md)** - Frontend Flutter application setup
- **[Docker Deployment](docs/docker.md)** - Complete Docker and docker-compose guide
- **[RAG Setup](docs/rag.md)** - RAG database initialization and management
- **[Configuration](docs/config/)** - Detailed configuration options

### Running with Docker

See the [Docker Deployment Guide](docs/docker.md) for complete instructions:

```bash
# Setup
cp .env.example .env
# Edit .env with your settings

# Run
docker-compose up
```

Access:
- Backend API: <http://localhost:8000>
- API Documentation: <http://localhost:8000/docs>
- Frontend Web UI: <http://localhost:9000>

## Related Repositories

- **[soliplex/flutter](https://github.com/soliplex/flutter)** - Flutter frontend (cross-platform mobile/desktop)
- **[Documentation](https://soliplex.github.io/)** - Documentation site (MkDocs)
- **[soliplex/ingester](https://github.com/soliplex/ingester)** - Content ingestion pipeline
- **[soliplex/ingester-agents](https://github.com/soliplex/ingester-agents)** - Document ingestion agents
- **[soliplex/whitelabel](https://github.com/soliplex/whitelabel)** - Customer white-label appshell template

## License

MIT License - Copyright (c) 2025 Enfold Systems, Inc.
