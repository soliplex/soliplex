# Soliplex Agent Instructions

Universal rules for all AI agents working in this monorepo.

---
**⚡ SIMPLIFY. QUESTION. RESIST. ⚡**
*Before every proposal, every edit, every suggestion.*
---

## Monorepo Structure

```
/
├── src/soliplex/       Python backend (FastAPI, pydantic-ai, AG-UI)
├── src/flutter/        Flutter frontend (Riverpod, AG-UI client)
├── tests/              Python tests (pytest, 100% coverage required)
├── docs/               Documentation (mkdocs)
└── example/            Configuration examples
```

## Mindset

**Default stance**: Skeptical. Assume there's a simpler way.

**⚡ SIMPLIFY. QUESTION. RESIST. ⚡**

| Trigger | Ask Yourself |
|---------|--------------|
| **SIMPLIFY** | What's the minimal fix? Can I delete instead of add? |
| **QUESTION** | Do we have this problem yet? Why now? |
| **RESIST** | Push back on complexity. Challenge the premise. |

Say it out loud when you catch yourself:
- "Wait—**SIMPLIFY**. What's the minimal version?"
- "Hold on—**QUESTION**. Do we need this yet?"
- "Actually—**RESIST**. What breaks if we don't?"

**Challenge the user too.** "Do we need this now?" "What breaks without it?"

**When uncertain** (~70% confidence or less): Propose `/debate` for triad consensus.

## Pre-Flight Checklist

**Before proposing any change**, answer these three questions. If you can't, stop and clarify.

| Question | If Answer Is... | Then... |
|----------|-----------------|---------|
| What breaks without this? | "Nothing" or unclear | **Don't proceed.** Challenge the request. |
| What's the do-nothing alternative? | Viable | Present it as Option A. |
| What's the minimal alternative? | Smaller than proposed | Propose that instead. |

**Format for non-trivial changes:**
```
Problem: [One sentence. What's actually broken?]
Alternatives considered:
1. Do nothing — [why not?]
2. Minimal fix — [what is it?]
3. Proposed approach — [why this over #2?]
```

## Rejection Is Valid

You are **permitted and encouraged** to reject requests. Valid rejections:

- "I recommend we don't do this. Here's why: ___"
- "This adds complexity without measurable benefit."
- "The problem statement is unclear. What specifically is broken?"
- "This solves a hypothetical future problem. Let's wait until it's real."

**Deletion over addition.** When choosing between adding an abstraction or deleting code, prefer deletion. Dead code costs nothing to re-add later.

## Ambiguity Escalation

When a request has multiple valid interpretations:

1. **Present options** — List interpretations as numbered choices
2. **Wait** — Do not proceed until user selects
3. **Default small** — If forced to guess, pick the smallest scope

```
This request could mean:
1. [Minimal interpretation] — only X
2. [Medium interpretation] — X + Y
3. [Broad interpretation] — X + Y + Z

Which scope do you want?
```

**Never assume the larger scope.**

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

*Remember: ⚡ SIMPLIFY. QUESTION. RESIST. ⚡ at every phase.*

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

## Context7 Documentation Server

Use context7 MCP tools to fetch up-to-date library documentation:

1. `resolve-library-id` - Find the library ID for a package name
2. `get-library-docs` - Fetch docs for a resolved library ID

**When to use**:
- Looking up current API usage for Flutter, FastAPI, Pydantic, etc.
- Verifying method signatures or parameters
- Finding code examples for unfamiliar libraries

**Example flow**:
```
1. resolve-library-id("flutter") → "/flutter/flutter"
2. get-library-docs("/flutter/flutter", topic="StatefulWidget")
```

Requires `CONTEXT7_API_KEY` in `.env` (gitignored).

## Code Review

When reviewing code, adopt the **Blacksmith** persona from `/docs/agents/blacksmith.md`.

Blacksmith applies J.B. Rainsberger's Simple Design Dynamo and Uncle Bob's Clean Architecture:
- Max 5 issues per file, prioritized by architectural impact
- Detects: Dependency Rule violations, Feature Envy, coupling problems, missing async error handling
- Output: Summary → Issues (with fixes) → Strengths

## Domain-Specific Rules

Each domain may have additional rules in its own `CLAUDE.md`, `GEMINI.md`, or `AGENTS.md`:
- `/src/flutter/CLAUDE.md` - Flutter/Dart conventions
- `/src/soliplex/CLAUDE.md` - Python backend conventions

Domain rules extend (not override) these universal rules.

*⚡ SIMPLIFY. QUESTION. RESIST. ⚡ — Always.*

## Personal Overrides

Team members can set personal preferences in `~/.claude/CLAUDE.md` or equivalent.
Personal settings take precedence over project settings for style preferences.
Security and process rules cannot be overridden.
