---
description: Show available documentation commands and usage
---

# Documentation System Help

Show the user available documentation commands and how to use the docs system.

## Available Commands

| Command | Purpose |
|---------|---------|
| `/docs` | This help message |
| `/docs-list` | List all specs, ADRs, and work logs with their status |
| `/docs-spec-new` | Create a new feature specification |
| `/docs-adr-new` | Create a new Architecture Decision Record |
| `/docs-status` | Show active work: in-progress specs, recent activity |
| `/docs-start` | Start work on a PLANNED spec (updates status, creates work log) |
| `/docs-complete` | Mark a spec as DONE (adds completion record) |
| `/docs-log` | Add a work log entry for current session |

## Quick Workflow

1. **New feature?** → `/docs-spec-new`
2. **Starting work?** → `/docs-start`
3. **Made a decision?** → `/docs-adr-new`
4. **End of session?** → `/docs-log`
5. **Feature done?** → `/docs-complete`

## Documentation Structure

```
docs/
├── PROCESS.md          # Master lifecycle documentation
├── specs/              # Feature specifications
├── adr/                # Architecture Decision Records
├── work-logs/          # Per-feature work history
└── recipes/            # Machine instructions (loaded automatically)
```

Display this information clearly to the user.
