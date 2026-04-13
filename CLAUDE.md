# CLAUDE.md

Guidance for AI assistants working with the Soliplex codebase.

## Project Overview

Soliplex is an AI-powered RAG system with a FastAPI backend, Flutter web
frontend, and terminal UI. It provides semantic document retrieval, multi-room
chat, and multi-provider LLM support.

## Quick Reference

```bash
# Run unit tests (100% coverage required)
uv run pytest

# Lint and format
uv run ruff check
uv run ruff format --check

# Start dev server
uv run soliplex-cli serve example/minimal.yaml --no-auth-mode

# Validate config
uv run soliplex-cli check-config example/minimal.yaml
```

## Repository Structure

```text
src/soliplex/
├── views/              # FastAPI routers
├── config/             # YAML config parsing (16 modules)
├── agui/               # AG-UI protocol (threads, runs, persistence)
├── authz/              # Authorization policy engine
├── tools/              # Agent tools (RAG, feedback, file uploads)
├── tui/                # Terminal UI (Textual)
├── main.py             # FastAPI app factory
├── cli.py              # CLI entry point
├── installation.py     # Installation management
├── agents.py           # Pydantic AI agent creation
├── models.py           # Public API response models
├── authn.py            # OIDC/JWT authentication
├── mcp_server.py       # FastMCP server
├── mcp_client.py       # MCP client toolsets
├── mcp_auth.py         # MCP token auth
├── secrets.py          # Secret resolution
└── completions.py      # OpenAI-compatible streaming
tests/
├── unit/               # 100% coverage required
└── functional/         # Require LLM, skip by default
example/                # Configs: rooms, completions, oidc, quizzes, skills
docs/                   # MkDocs documentation
schemas/                # AG-UI feature JSON schemas
```

## Technical Details

- Python 3.12+, ruff targets 3.13, line length 79
- Single-line imports enforced via isort
- 100% branch coverage enforced on unit tests
- Config classes use dataclasses with `from_yaml` classmethod pattern
- Private fields `_installation_config` and `_config_path` carry context

## Key Dependencies

- FastAPI / Uvicorn -- REST API and ASGI server
- pydantic-ai-slim[google] -- Agent framework
- haiku.rag-slim (>=0.38.0) -- RAG functionality
- FastMCP (>=2.14.0) -- Model Context Protocol
- ag-ui-protocol (>=0.1.15) -- AG-UI event protocol
- SQLModel / aiosqlite -- Database ORM
- haiku-skills (>=0.13.2) -- Haiku skills framework

## Entry Points

- `soliplex-cli` -- Backend CLI (serve, check-config, list-rooms,
  validate-config, add-admin-user)
- `soliplex-tui` -- Terminal UI client
- `soliplex-tui-serve` -- TUI server

## Environment Variables

See `.env.example` for the full reference. Key variables:

- `OLLAMA_BASE_URL` -- Ollama server URL (without `/v1` suffix)
- `OPENAI_API_KEY` / `GEMINI_API_KEY` -- LLM provider keys
- `SOLIPLEX_URL_SAFE_TOKEN_SECRET` -- MCP token secret (auto-generated if
  unset)
- `LOGFIRE_TOKEN` -- Pydantic Logfire token (optional)

## Documentation

Detailed configuration and usage docs are in [docs/](docs/) (served via
MkDocs). Example configurations are in [example/](example/).
