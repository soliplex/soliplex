# Documentation Process

> Master reference for the SOLIPLEX documentation lifecycle.
> Version: 3.1.0 | Last Updated: 2025-12-13

## Overview

This system tracks work through a structured lifecycle with clear audit trails. It separates human-oriented documentation (specs, ADRs) from machine-generated work artifacts (logs).

## Directory Structure

```
docs/
├── PROCESS.md          # This file - lifecycle overview
├── adr/                # Architecture Decision Records
│   └── NNNN-title.md
├── specs/              # Feature specifications
│   └── feature-name.md
├── work-logs/          # Per-feature work history
│   └── feature-name.md
├── lessons/            # Aggregated lessons learned (by category)
│   ├── riverpod.md
│   ├── testing.md
│   ├── architecture.md
│   ├── flutter.md
│   └── general.md
└── recipes/            # Machine instructions (context-efficient)
    ├── spec-recipe.md
    ├── adr-recipe.md
    └── work-log-recipe.md
```

## Lifecycle States

| State | Symbol | Meaning | Blocks new work? |
|-------|--------|---------|------------------|
| PLANNED | `[ ]` | Spec created, work not started | No |
| IN_PROGRESS | `[~]` | Active development | **Yes** |
| PAUSED | `[⏸]` | Shelved, can resume later | No |
| DONE | `[x]` | Complete, versioned | No |
| BLOCKED | `[!]` | Waiting on external dependency | No |

## Artifact Types

### Specs (`docs/specs/`)
- **Audience**: Human
- **Purpose**: Define *what* we're building
- **Lifecycle**: PLANNED → IN_PROGRESS → DONE
- **Naming**: `feature-name.md` (kebab-case)
- **Recipe**: `recipes/spec-recipe.md`

### ADRs (`docs/adr/`)
- **Audience**: Human
- **Purpose**: Record *why* decisions were made
- **Lifecycle**: proposed → accepted | deprecated | superseded
- **Naming**: `NNNN-title.md` (zero-padded sequence)
- **Recipe**: `recipes/adr-recipe.md`

### Work Logs (`docs/work-logs/`)
- **Audience**: Audit/Machine
- **Purpose**: Track *when/how* work happened
- **Lifecycle**: Append-only per feature
- **Naming**: `feature-name.md` (matches spec name)
- **Recipe**: `recipes/work-log-recipe.md`

### Lessons (`docs/lessons/`)
- **Audience**: Human/Machine
- **Purpose**: Searchable knowledge base of insights
- **Lifecycle**: Append-only, extracted at spec completion
- **Naming**: `{category}.md` (riverpod, testing, architecture, flutter, general)
- **Collection**: Automatic via `/docs-complete`

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  1. PLAN                                                    │
│     ├─ Human creates SPEC (status: PLANNED)                 │
│     └─ Defines requirements, acceptance criteria            │
├─────────────────────────────────────────────────────────────┤
│  2. EXECUTE (/docs-start)                                   │
│     ├─ Update SPEC status → IN_PROGRESS                     │
│     ├─ Capture baseline coverage                            │
│     ├─ Claude creates/appends WORK-LOG per session          │
│     ├─ If decision needed → create ADR, link from spec      │
│     └─ Check off requirements as completed                  │
├─────────────────────────────────────────────────────────────┤
│  2b. PAUSE (/docs-pause) - optional                         │
│     ├─ Update SPEC status → PAUSED                          │
│     ├─ Add pause entry to work log                          │
│     └─ Allows starting new work                             │
├─────────────────────────────────────────────────────────────┤
│  3. COMPLETE (/docs-complete)                               │
│     ├─ Update SPEC status → DONE                            │
│     ├─ Capture final coverage, calculate delta              │
│     ├─ ADR Wizard: prompt for ADRs from decisions           │
│     ├─ Lessons: extract and categorize insights             │
│     ├─ Deferred Items: prompt to create follow-up specs     │
│     └─ Final work-log entry with summary                    │
└─────────────────────────────────────────────────────────────┘
```

## Cross-Referencing

Use consistent reference formats:

| Type | Format | Example |
|------|--------|---------|
| Spec | `SPEC:name` | `SPEC:room-tags` |
| ADR | `ADR-NNNN` | `ADR-0012` |
| Work Log | `LOG:name` | `LOG:room-tags` |

## Versioning

- Specs get versions when completed: `1.0.0`
- Major: Breaking changes or complete rewrites
- Minor: New requirements added
- Patch: Clarifications, typo fixes

## Audit Trail Requirements

Every work session MUST:
1. Reference the active spec(s)
2. Include ISO 8601 timestamp
3. List concrete changes made
4. Note any decisions (with ADR refs if applicable)
5. State next actions or blockers
6. **Include Resume Context** with quality metrics (tests, coverage, analyzer, formatter)

## Enforced Rules

### Single Spec Rule
**Only ONE spec can be IN_PROGRESS at a time.**

- `/docs-start` will refuse to start a new spec if another is IN_PROGRESS
- No overrides - complete or pause current work first
- Rationale: Prevents context switching and ensures focus

### Test Requirements

Every spec completion requires:
1. **Test AC**: Specs include "Unit tests exist for new/modified code" as acceptance criterion
2. **Testing Session**: Work log must document a testing session
3. **Coverage Tracking**:
   - Baseline coverage captured at `/docs-start`
   - Final coverage captured at `/docs-complete`
   - Delta reported for touched files

### Coverage Metrics

Coverage is tracked per-file for files modified by the spec:

| Metric | When Captured | Tool |
|--------|---------------|------|
| Baseline | `/docs-start` | `flutter test --coverage` |
| Final | `/docs-complete` | `flutter test --coverage` |
| Delta | Completion record | Calculated from lcov.info |

### PAUSED State

Use `/docs-pause` to shelve work and allow starting something else:
- PAUSED specs can be resumed via `/docs-start`
- Multiple specs can be PAUSED simultaneously
- PAUSED does NOT block starting new work (unlike IN_PROGRESS)

### Resume Context (Critical for Session Continuity)

Every session entry MUST end with a Resume Context section containing:

```markdown
### Resume Context
**Modified files:**
- `path/to/file.dart:NN-MM` - brief description

**Quality metrics:**
- Tests: N passing, M failing
- Coverage: file.dart XX%→YY%
- Analyzer: N issues (or "clean")
- Formatter: N files changed (or "clean")

**Next action:** Single most important next step
```

**Why this matters:**
- New sessions start with zero context
- File paths alone don't show *where* in the file you were working
- Quality metrics show project health at session end

### Completion Wizards (Future Enhancement)

*Note: These wizards are planned but not yet implemented. Currently, ADRs and lessons are created manually.*

At `/docs-complete`, these wizards are planned:

1. **ADR Wizard**: Scan decisions for keywords, prompt to create ADRs
2. **Lessons Extraction**: Extract lessons, categorize, append to lessons files
3. **Deferred Items**: List uncompleted items, prompt to create follow-up specs

### Lessons Categories

| Category | File | Content |
|----------|------|---------|
| riverpod | `lessons/riverpod.md` | State management patterns |
| testing | `lessons/testing.md` | Testing gotchas |
| architecture | `lessons/architecture.md` | Design patterns |
| flutter | `lessons/flutter.md` | Flutter-specific |
| general | `lessons/general.md` | Catch-all |

## Recipe Loading (for Claude)

Claude infers which recipe to load based on context:
- Creating/updating a feature spec → `spec-recipe.md`
- Recording a technical decision → `adr-recipe.md`
- Logging work session → `work-log-recipe.md`

Recipes are modular to minimize context window usage.
