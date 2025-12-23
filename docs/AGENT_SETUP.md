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

### 1. Declare Your Available Agents

Create `.agents.local.yaml` in the project root (gitignored):

```yaml
# Which agents you have access to
agents:
  claude:
    enabled: true
    primary: true  # Your default agent
  gemini:
    enabled: false  # No API key
  codex:
    enabled: true
```

### 2. Set Up Personal Preferences

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

### 3. Configure API Keys

Each agent needs its API key set as an environment variable:

```bash
# Claude (via Anthropic API or Claude Code)
export ANTHROPIC_API_KEY="..."

# Gemini
export GEMINI_API_KEY="..."

# Codex/Copilot (via GitHub)
# Configured through VS Code/IDE settings
```

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
| `AGENTS.md` | Universal rules (security, process) | `/AGENTS.md` |
| `CLAUDE.md` | Claude-specific project knowledge | `/CLAUDE.md`, `/src/*/CLAUDE.md` |
| `GEMINI.md` | Gemini-specific instructions | `/GEMINI.md`, `/src/*/GEMINI.md` |
| `.agents.local.yaml` | Your personal agent config | `/` (gitignored) |

## Getting Help

- Check `/agents-monorepo.md` for detailed multi-agent strategy
- Review domain-specific docs in `/src/flutter/CLAUDE.md` or `/src/soliplex/CLAUDE.md`
- Ask Claude: "What agents are configured for this project?"
