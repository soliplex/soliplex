# AGENTS.md

Detailed guidance for AI coding agents working on the Soliplex project.
See CLAUDE.md for a concise project overview and quick reference.

## Build and Test

```bash
# Install dependencies (use uv, not pip)
uv sync --group dev

# Run unit tests with 100% coverage requirement
uv run pytest

# Run a specific test file
uv run pytest tests/unit/test_agents.py

# Run functional tests (require a running LLM)
uv run pytest tests/functional/ -m needs_llm

# Lint and format
uv run ruff check
uv run ruff format --check

# Auto-fix lint and format issues
uv run ruff check --fix
uv run ruff format
```

## Code Style

- Line length: 79 characters
- Single-line imports enforced (isort via ruff)
- Ruff rule sets: F, E, B, U, I, PD, TRY, PT
- Target version: Python 3.13
- Use `uv run` to execute all Python commands

## Testing Requirements

- Unit tests live in `tests/unit/`, mirroring the `src/soliplex/` structure
- 100% branch coverage is enforced via pytest-cov (`--cov-fail-under=100`)
- Coverage omits: `cli.py`, `examples.py`, `tui.py`
- Use pytest-asyncio for async tests
- Functional tests (`tests/functional/`) require a running LLM and are
  skipped by default (marker: `needs_llm`)

## Configuration System

- YAML-based hierarchical config in `src/soliplex/config/` (16 modules)
- Top-level entry: `InstallationConfig` in `config/installation.py`
- Config classes use dataclasses with a `from_yaml` classmethod
- Private fields `_installation_config` and `_config_path` carry context
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

## File Reference

- `pyproject.toml` -- Dependencies, scripts, tool config
- `src/soliplex/config/installation.py` -- Master config parsing
- `src/soliplex/main.py` -- FastAPI app factory
- `example/installation.yaml` -- Full config example
- `example/minimal.yaml` -- Minimal config for development
- `.env.example` -- Environment variable reference
- `docs/` -- MkDocs documentation site
