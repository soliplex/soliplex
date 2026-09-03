# AGENTS.md

Guidance for AI coding agents working on the Soliplex project. Human
contributors should read [DEVELOPMENT.md](DEVELOPMENT.md), which covers the
same ground in prose. (`CLAUDE.md` is a thin stub that imports this file so
Claude Code loads it automatically.)

## Project Overview

Soliplex is an AI-powered RAG system with a FastAPI backend, Flutter web
frontend, and terminal UI. It provides semantic document retrieval,
multi-room chat, and multi-provider LLM support.

**This repository contains the Python backend and TUI only.** The Flutter
frontend lives in a sibling repo at <https://github.com/soliplex/frontend>
with its own tooling.

## Build and Test

```bash
# Install dependencies (use uv, not pip)
uv sync --group dev

# Run unit tests with 100% coverage requirement
uv run pytest

# Run a specific test file / test
uv run pytest tests/unit/test_agents.py
uv run pytest tests/unit/test_agents.py::test_name

# Run functional tests (require a running LLM)
uv run pytest tests/functional/ -m needs_llm

# Lint and format
uv run ruff check
uv run ruff format --check

# Auto-fix lint and format issues
uv run ruff check --fix
uv run ruff format

# Start a dev server (no auth)
uv run soliplex-cli serve example/minimal.yaml --no-auth-mode

# Validate a configuration
uv run soliplex-cli audit example/minimal.yaml
```

## Code Style

- Line length: 79 characters
- Single-line imports enforced (isort via ruff)
- Ruff rule sets: F, E, B, U, I, PD, TRY, PT
- Target version: Python 3.13
- Use `uv run` to execute all Python commands

## Pre-commit Hooks

Optional: `uv run pre-commit install` automates the CI checks before each
commit (`uv run pre-commit run --all-files` runs them once against the whole
tree). The configured hooks (see `.pre-commit-config.yaml`) enforce:

- `ruff-check` / `ruff-format` -- lint and format Python sources
- `pymarkdown` -- lint Markdown files
- `lint-textio` -- reject text file IO in `src/soliplex/` without an
  explicit `encoding=` (falls back to the host locale encoding, `cp1252` on
  Windows); `scripts/lint_textio.py`, stdlib-only, with a `--self-test` mode
- `actionlint` -- lint GitHub Actions workflow files
- `check-toml` / `check-yaml` -- validate TOML and YAML syntax
- `gitleaks` -- scan for committed secrets
- `pip-audit` -- scan dependencies for known vulnerabilities (runs when
  `pyproject.toml`, `uv.lock`, or `.pre-commit-config.yaml` changes)
- `debug-statements` -- reject leftover `pdb` / `breakpoint()` calls
- `trailing-whitespace` / `end-of-file-fixer` -- normalize whitespace
- `check-merge-conflict` -- reject unresolved merge-conflict markers
- `no-commit-to-branch` -- block direct commits to `main` / `master`

## Testing Requirements

- Unit tests live in `tests/unit/`, mirroring the `src/soliplex/` structure
- 100% branch coverage is enforced via pytest-cov (`--cov-fail-under=100`)
- Coverage measures four targets (see `addopts` in `pyproject.toml`):
  `src/soliplex`, `tests/unit`, `scripts`, and
  `skills/soliplex-docs/scripts` -- the test suite and the helper scripts
  are held to the same 100% bar as `src/`
- Those targets are *paths*, not importable names, and must stay that way.
  `soliplex` is a namespace package (there is no
  `src/soliplex/__init__.py`); coverage cannot enumerate one by walking the
  filesystem, so `--cov=soliplex` would measure only the modules some test
  happened to import, and a module nobody imports would pass unnoticed
- `[tool.coverage.run] omit` is therefore the single place that decides
  what is exempt: `scripts/lint_textio.py` (it runs its own `--self-test`
  during lint) and `src/soliplex/tui/*` (the TUI is deliberately
  untested). Everything else under `src/soliplex/` must reach 100%
- Use pytest-asyncio for async tests
- Functional tests (`tests/functional/`) require a running LLM and are
  skipped by default (marker: `needs_llm`)

## Repository Structure

Non-obvious modules and directories (the rest are self-explanatory from
their filenames -- `ls src/soliplex/` for the full layout):

- `agui/` -- AG-UI protocol (threads, runs, persistence)
- `authz/` -- authorization policy engine
- `config/` -- YAML config parsing (16 modules; see `installation.py` for
  the top-level entry)
- `tools/` -- agent tools (RAG, feedback, file uploads)
- `agents.py` -- Pydantic AI agent creation
- `completions.py` -- OpenAI-compatible streaming endpoint (not just
  LLM-level completions)
- `installation.py` -- installation lifespan, admin bootstrap, and global
  state management
- `main.py` -- FastAPI app factory (`create_app`)
- `tests/unit/` -- 100% coverage required; mirrors `src/soliplex/`
- `tests/functional/` -- tests requiring an LLM (marked `needs_llm`) are
  skipped by default; other functional tests run
- `example/` -- sample configs (rooms, completions, oidc, quizzes, skills)
- `schemas/` -- AG-UI feature JSON schemas

Key files:

- `pyproject.toml` -- dependencies, scripts, tool config
- `src/soliplex/config/installation.py` -- master config parsing
- `src/soliplex/main.py` -- FastAPI app factory
- `example/installation.yaml` -- full config example
- `example/minimal.yaml` -- minimal config for development
- `.env.example` -- environment variable reference

## Configuration System

- YAML-based hierarchical config in `src/soliplex/config/` (16 modules)
- Top-level entry: `InstallationConfig` in `config/installation.py`
- Config classes use dataclasses with a `from_yaml` classmethod
- Private fields `_installation_config` and `_config_path` carry context so
  nested configs can resolve env vars, secrets, and paths relative to the
  config file without threading them through every `from_yaml` call
- Environment variables resolved via `Installation.get_environment()`
- Secrets resolved via a configurable source chain (env vars, files,
  subprocess, random generation) in `config/secrets.py`

## Adding a New Tool

1. Create or modify a tool module in `src/soliplex/tools/`
2. Tool functions are async and accept `RunContext[AgentDependencies]`
3. If the tool needs configuration, add a `ToolConfig` subclass in
   `config/tools.py`
4. Register it in `TOOL_CONFIG_CLASSES_BY_TOOL_NAME` (found in
   `config/tools.py` and `config/meta.py`)
5. Reference the tool in room configuration under `agent.tools`

## Adding a New Room

1. Create `example/rooms/<room_id>/room_config.yaml`
2. Required fields: `id`, `name`, `description`, `agent`
3. Optionally add `prompt.txt` for an external system prompt

## Adding API Endpoints

1. Create or modify a router in `src/soliplex/views/`
2. Register the router in `main.py` with the appropriate prefix
3. Add unit tests achieving 100% branch coverage

## Key Architecture

- FastAPI app created via `create_app()` in `main.py`
- Rooms contain agents, each with tools, skills, and an LLM provider config
- AG-UI protocol handles thread/run lifecycle with SSE event streaming
- Authorization via a policy engine in `authz/`
- MCP server exposes Soliplex tools; MCP client consumes external tool servers
- Authentication via OIDC/JWT in `authn.py`
- Public API models defined in `models.py`

## Key Dependencies

See `pyproject.toml` for authoritative version constraints.

- FastAPI / Uvicorn -- REST API and ASGI server
- pydantic-ai-slim[google] -- agent framework
- haiku.rag-slim -- RAG functionality
- FastMCP -- Model Context Protocol
- ag-ui-protocol -- AG-UI event protocol
- SQLModel / aiosqlite -- database ORM
- haiku-skills -- Haiku skills framework

## Entry Points

- `soliplex-cli` -- backend CLI; run `soliplex-cli --help` for the full
  command list
- `soliplex-tui` -- terminal UI client
- `soliplex-tui-serve` -- TUI server

## Environment Variables

See `.env.example` for the full reference. Key variables:

- `OLLAMA_BASE_URL` -- Ollama server URL (without `/v1` suffix)
- `OPENAI_API_KEY` / `GEMINI_API_KEY` -- LLM provider keys
- `SOLIPLEX_URL_SAFE_TOKEN_SECRET` -- MCP token secret (auto-generated if
  unset)
- `LOGFIRE_TOKEN` -- Pydantic Logfire token (optional)
- `SOLIPLEX_CLI_LOG_CONFIG` -- path to a Python logging-config YAML enabling
  audit logging for privileged CLI commands (also the `--cli-log-config`
  group option on `admin-users` / `room-authz` / `audit`); unset means CLI
  audit records are suppressed (see `docs/config/logging.md`)

## Documentation

Detailed configuration and usage docs are in [docs/](docs/) (served via
Zensical). Example configurations are in [example/](example/).
