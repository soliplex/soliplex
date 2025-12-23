# Claude Code Instructions

Project-specific instructions for Claude Code. Extends `/AGENTS.md`.

**Remember**: Default skeptical. "Do we need this yet?" "What's the simplest fix?"

## Tech Stack

- **Python**: 3.13+, pydantic-ai, FastAPI, SQLModel
- **Protocol**: AG-UI (ag-ui-protocol), fastmcp for MCP
- **Auth**: Authlib, python-keycloak, JWT
- **RAG**: haiku.rag-slim
- **Tests**: pytest with 100% coverage requirement

## Key Commands

```bash
# Run tests
uv run pytest

# Lint (must pass with zero warnings)
uv run ruff check src tests
uv run ruff format src tests

# Run server
uv run soliplex-cli serve

# TUI
uv run soliplex-tui
```

## Code Style

- Line length: 79 chars (ruff enforced)
- Single-line imports (isort force-single-line)
- Type hints required for public APIs
- Docstrings for public functions

## Test Requirements

- 100% branch coverage (`--cov-fail-under=100`)
- Tests in `tests/unit/` (functional tests optional)
- Use pytest fixtures from `conftest.py`
- Async tests with `pytest-asyncio`

## Project Layout

```
src/soliplex/
├── agents.py       pydantic-ai agent setup
├── config.py       Configuration (large, read carefully)
├── models.py       Data models
├── main.py         FastAPI app factory
├── views/          API endpoints
├── agui/           AG-UI protocol implementation
└── mcp_*.py        MCP client/server/auth
```

## Reference Documentation

- `/docs/config/agents.md` - Agent configuration reference
- `/example/*.yaml` - Configuration examples
- `/agents-monorepo.md` - Multi-agent strategy (reference only)
- Use `context7` MCP tools for up-to-date library docs (see `/AGENTS.md`)

## Domain Subconfigs

- `/src/flutter/CLAUDE.md` - Flutter frontend specifics
- `/src/soliplex/CLAUDE.md` - Python backend specifics (if exists)
