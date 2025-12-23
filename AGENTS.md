# Soliplex Agent Instructions

Universal rules for all AI agents working in this monorepo.

## Monorepo Structure

```
/
├── src/soliplex/       Python backend (FastAPI, pydantic-ai, AG-UI)
├── src/flutter/        Flutter frontend (Riverpod, AG-UI client)
├── tests/              Python tests (pytest, 100% coverage required)
├── docs/               Documentation (mkdocs)
└── example/            Configuration examples
```

## Security

- Never commit secrets, API keys, or credentials
- Never bypass CI checks or pre-commit hooks
- Never modify production configurations without explicit approval
- Never execute destructive database operations

## Process

- Run tests before suggesting code is complete
- Run linters/analyzers before commits (zero warnings)
- Follow existing code patterns in each domain
- Link PRs to issues when applicable

## Agent Roles

| Agent | Primary Role | Best For |
|-------|-------------|----------|
| Claude | Reasoning & Architecture | Complex refactoring, code review, planning |
| Gemini | Context & Research | Large file analysis, documentation search |
| Codex | Inline Completion | Autocomplete, boilerplate generation |

## Domain-Specific Rules

Each domain may have additional rules in its own `CLAUDE.md`, `GEMINI.md`, or `AGENTS.md`:
- `/src/flutter/CLAUDE.md` - Flutter/Dart conventions
- `/src/soliplex/CLAUDE.md` - Python backend conventions

Domain rules extend (not override) these universal rules.

## Personal Overrides

Team members can set personal preferences in `~/.claude/CLAUDE.md` or equivalent.
Personal settings take precedence over project settings for style preferences.
Security and process rules cannot be overridden.
