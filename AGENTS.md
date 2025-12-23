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

| Agent | CLI | Primary Role | Best For |
|-------|-----|-------------|----------|
| Claude | `claude` | Reasoning & Architecture | Complex refactoring, code review, planning |
| Gemini | `gemini` | Context & Research | Large file analysis, documentation search |
| Codex | `codex` | Tactical Execution | Quick edits, boilerplate, running commands |

## Triad Workflow

Default sequence for multi-agent tasks:

```
GEMINI (Research) → CLAUDE (Architect) → CODEX (Execute)
```

| Phase | Agent | Action |
|-------|-------|--------|
| 1. Research | Gemini | Explore codebase, find files, gather context |
| 2. Plan | Claude | Design approach, make decisions, write complex logic |
| 3. Execute | Codex | Quick edits, boilerplate, run commands |

Single-agent tasks: any agent handles all phases.

## Handoff Protocol

When switching agents mid-task, append to `docs/work-logs/{feature}.md`:

```markdown
## Handoff [YYYY-MM-DD]
- **Done**: What was completed
- **Files**: Key files modified or identified
- **Next**: What the next agent should do
```

## Codex-Specific

Codex reads this file automatically. Additional guidance:
- Prefer `dart mcp-server` tools over CLI for Flutter (see `src/flutter/AGENTS.md`)
- Run `uv run pytest` for Python tests
- Run `uv run ruff check` before commits

## Domain-Specific Rules

Each domain may have additional rules in its own `CLAUDE.md`, `GEMINI.md`, or `AGENTS.md`:
- `/src/flutter/CLAUDE.md` - Flutter/Dart conventions
- `/src/soliplex/CLAUDE.md` - Python backend conventions

Domain rules extend (not override) these universal rules.

## Personal Overrides

Team members can set personal preferences in `~/.claude/CLAUDE.md` or equivalent.
Personal settings take precedence over project settings for style preferences.
Security and process rules cannot be overridden.
