# Multi-Agent Setup Guide

This project supports multiple AI agents (Claude, Gemini, Codex) working together. Team members may have access to different subsets of these agents.

## Agent Roles

| Agent | Primary Role | Best For |
|-------|-------------|----------|
| **Claude** | Reasoning & Architecture | Complex refactoring, code review, planning, writing business logic |
| **Gemini** | Context & Research | Large file analysis, documentation search, multimodal input |
| **Codex** | Inline Completion | Autocomplete, boilerplate generation, quick edits |

**Claude is the recommended primary agent** for most development tasks.

## Configuration Hierarchy

Agent instructions are loaded in this order (later overrides earlier):

1. **User global**: `~/.claude/CLAUDE.md` (or `~/.gemini/GEMINI.md`)
2. **Project global**: `/AGENTS.md`, `/CLAUDE.md`, `/GEMINI.md`
3. **Domain specific**: `/src/flutter/CLAUDE.md`, `/src/soliplex/CLAUDE.md`

Security and process rules from `/AGENTS.md` cannot be overridden.

## Personal Setup

### 1. Set Up Personal Preferences

Create `~/.claude/CLAUDE.md` for your personal style preferences:

```markdown
# My Claude Preferences

## Git Workflow
- Use conventional commits
- No emojis in commit messages

## Code Style
- Prefer explicit over implicit
- Add comments for non-obvious logic
```

These preferences apply across all projects.

### 2. Verify CLI Access

Each agent should work from command line:

```bash
# Claude
claude --version

# Gemini
gemini --version

# Codex
codex --version
```

If a CLI works, you're authenticated. No extra API key setup needed.

## Fallback Strategies

When your primary agent is unavailable:

| If Missing | Fallback | Notes |
|------------|----------|-------|
| Claude | Gemini | May need to break into smaller prompts |
| Gemini | Claude | Use explicit context boundaries |
| Codex | Claude/Gemini | Ask for "inline completion style" suggestions |

## Workflow Patterns

### Feature Development (Multi-Agent)

1. **Research** (Gemini): Explore codebase, find relevant files
2. **Plan** (Claude): Design implementation approach
3. **Implement** (Claude + Codex): Write code with inline completion
4. **Review** (Claude): Self-review before PR

### Bug Investigation

1. **Search** (Gemini): Find related code and history
2. **Analyze** (Claude): Identify root cause
3. **Fix** (Claude): Implement fix
4. **Test** (Claude): Write/update tests

### Single-Agent Workflow

If you only have one agent, it handles all phases. Adjust prompts accordingly:
- For Claude: Works well for all phases
- For Gemini: Break complex reasoning into steps, leverage context window
- For Codex: Use VS Code chat, combine with manual exploration

## Project Files

| File | Purpose | Location |
|------|---------|----------|
| `AGENTS.md` | Universal rules (all agents, Codex native) | `/AGENTS.md`, `/src/*/AGENTS.md` |
| `CLAUDE.md` | Claude-specific project knowledge | `/CLAUDE.md`, `/src/*/CLAUDE.md` |
| `GEMINI.md` | Gemini-specific instructions | `/GEMINI.md`, `/src/*/GEMINI.md` |

## Simultaneous Multi-Agent Usage

Use all three agents together in a "Relay Race" pattern:

```
┌─────────────────────────────────────────────────────────────┐
│  GEMINI (Research)                                          │
│  - Explore codebase, find files                             │
│  - Read large context (docs, history)                       │
│  - Generate initial scaffold from designs                   │
├─────────────────────────────────────────────────────────────┤
│  CLAUDE (Architect)                                         │
│  - Review Gemini's findings                                 │
│  - Design implementation approach                           │
│  - Write complex business logic                             │
│  - Refactor and integrate                                   │
├─────────────────────────────────────────────────────────────┤
│  CODEX (Driver)                                             │
│  - Inline completion while coding                           │
│  - Generate boilerplate/tests                               │
│  - Quick tactical edits                                     │
└─────────────────────────────────────────────────────────────┘
```

### Example: Adding a New Feature

1. **Gemini**: "Find all files related to authentication and summarize the current flow"
2. **Claude**: "Based on Gemini's findings, design an approach to add OAuth2 support"
3. **Codex**: (in IDE) Autocomplete as you implement Claude's design
4. **Claude**: "Review the implementation and suggest improvements"

### Handoff Protocol

When handing off between agents, provide:
- Summary of what was done
- Files identified/modified
- What the next agent should do

## Getting Help

- Review domain-specific docs in `/src/flutter/CLAUDE.md` or `/src/soliplex/CLAUDE.md`
- Ask Claude: "What agents are configured for this project?"
