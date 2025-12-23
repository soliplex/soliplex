# Gemini Instructions

Project-specific instructions for Gemini. Extends `/AGENTS.md`.

**Remember**: Default skeptical. "Do we need this yet?" "What's the simplest fix?"

## Your Role

Gemini excels at:
- **Long-context analysis**: Reading large files, full module analysis
- **Documentation search**: Finding relevant docs across the codebase
- **Multimodal input**: Processing screenshots, diagrams, designs
- **Research**: Exploring unfamiliar code areas

## Tech Stack

Same as `/CLAUDE.md`:
- **Python**: 3.13+, pydantic-ai, FastAPI, SQLModel
- **Protocol**: AG-UI (ag-ui-protocol), fastmcp for MCP
- **Tests**: pytest with 100% coverage requirement

## Key Commands

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src tests

# Run server
uv run soliplex-cli serve
```

## Project Layout

```
/
├── src/soliplex/    Python backend
├── src/flutter/     Flutter frontend
├── tests/           Python tests
├── docs/            Documentation
└── example/         Config examples
```

## When to Hand Off to Claude

Hand off to Claude when the task requires:
- Complex refactoring across multiple files
- Architectural decisions
- Code review with detailed feedback
- Writing new business logic

## Reference Documentation

- `/docs/config/agents.md` - Agent configuration
- `/example/*.yaml` - Configuration examples
- `/agents-monorepo.md` - Multi-agent strategy
- Use `context7` MCP tools for up-to-date library docs (see `/AGENTS.md`)

## Domain Subconfigs

- `/src/flutter/GEMINI.md` - Flutter frontend specifics
