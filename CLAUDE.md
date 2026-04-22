# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project Overview

Soliplex is an AI-powered RAG system with a FastAPI backend, Flutter web
frontend, and terminal UI. It provides semantic document retrieval, multi-room
chat, and multi-provider LLM support.

**This repository contains the Python backend and TUI only.** The Flutter
frontend lives in a sibling repo at
<https://github.com/soliplex/flutter> with its own tooling.

See `AGENTS.md` for deeper guidance on adding tools, rooms, and API
endpoints.

## Quick Reference

```bash
# Run unit tests (100% coverage required)
uv run pytest

# Run a single test file / test
uv run pytest tests/unit/test_agents.py
uv run pytest tests/unit/test_agents.py::test_name

# Run functional tests (require a running LLM, skipped by default)
uv run pytest tests/functional/ -m needs_llm

# Lint and format
uv run ruff check
uv run ruff format --check

# Start dev server
uv run soliplex-cli serve example/minimal.yaml --no-auth-mode

# Validate config
uv run soliplex-cli check-config example/minimal.yaml
```

## Repository Structure

Non-obvious modules and directories (the rest are self-explanatory from
their filenames -- `ls src/soliplex/` for the full layout):

- `agui/` -- AG-UI protocol (threads, runs, persistence)
- `authz/` -- Authorization policy engine
- `config/` -- YAML config parsing (16 modules, see `installation.py`
  for the top-level entry)
- `tools/` -- Agent tools (RAG, feedback, file uploads)
- `agents.py` -- Pydantic AI agent creation
- `completions.py` -- OpenAI-compatible streaming endpoint (not just
  LLM-level completions)
- `installation.py` -- Installation lifespan, admin bootstrap, and
  global state management
- `main.py` -- FastAPI app factory (`create_app`)
- `tests/unit/` -- 100% coverage required; mirrors `src/soliplex/`
- `tests/functional/` -- tests requiring an LLM (marked `needs_llm`)
  are skipped by default; other functional tests run
- `example/` -- sample configs (rooms, completions, oidc, quizzes, skills)
- `schemas/` -- AG-UI feature JSON schemas

## Technical Details

- Python 3.12+, ruff targets 3.13, line length 79
- Single-line imports enforced via isort
- 100% branch coverage enforced on unit tests; `cli.py`, `examples.py`,
  and `tui.py` are omitted from coverage (see `[tool.coverage.run]` in
  `pyproject.toml`) -- new code in those modules silently bypasses the
  threshold
- Config classes use dataclasses with `from_yaml` classmethod pattern
- Config dataclasses carry `_installation_config` and `_config_path` as
  private fields so nested configs can resolve env vars, secrets, and
  paths relative to the config file without threading them through every
  `from_yaml` call

## Key Dependencies

See `pyproject.toml` for authoritative version constraints.

- FastAPI / Uvicorn -- REST API and ASGI server
- pydantic-ai-slim[google] -- Agent framework
- haiku.rag-slim -- RAG functionality
- FastMCP -- Model Context Protocol
- ag-ui-protocol -- AG-UI event protocol
- SQLModel / aiosqlite -- Database ORM
- haiku-skills -- Haiku skills framework

## Entry Points

- `soliplex-cli` -- Backend CLI; run `soliplex-cli --help` for the full
  command list
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
