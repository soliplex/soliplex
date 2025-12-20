# Gemini Code Notes

Project-specific instructions for Gemini when working on this codebase.

## Reference Documentation

- **GEMINI_UNDERSTANDING.md** - Deep dive into GenUI architecture, state management, and layout patterns.
- **PROJECT.md** - Implementation status, available widgets, and server endpoint flow.
- **SOLIPLEX.md** - Backend API documentation for AG-UI integration (endpoints, request/response schemas, state sync).
- **APP_FEATURES.md** - Planned, in-progress, and completed app features (feedback chips, notes pad, etc.).
- **IMPLEMENTATION_STREAMING_MARKDOWN.md** - Technical details on the streaming markdown system and hooks.
- **LESSONS.md** - Key engineering lessons learned during development (e.g., SSE handling, Riverpod patterns).
- **docs/PROCESS.md** - Documentation lifecycle process (specs, ADRs, work logs).

## Documentation Lifecycle System

Feature work follows a structured lifecycle with audit trails. See `docs/PROCESS.md` for full details.

### Quick Reference

| Artifact | Location | Purpose |
|----------|----------|---------|
| Spec | `docs/specs/{name}.md` | Define what we're building |
| ADR | `docs/adr/NNNN-{title}.md` | Record why decisions were made |
| Work Log | `docs/work-logs/{name}.md` | Track when/how work happened |

### Workflow

1. **Before starting a feature**: Create or locate the spec in `docs/specs/`
2. **During work**: Append session entries to `docs/work-logs/{feature}.md`
3. **When making decisions**: Create ADR in `docs/adr/`, link from spec
4. **When complete**: Update spec status to DONE, add completion record

### Machine Instructions (Recipes)

Use these recipes for formatting and content guidance:
- `docs/recipes/spec-recipe.md` - Creating/updating specs
- `docs/recipes/adr-recipe.md` - Creating ADRs
- `docs/recipes/work-log-recipe.md` - Maintaining work logs

## Commands

The following are not native CLI commands, but rather instructions for me to interpret and execute based on the corresponding instruction files in `.claude/commands/` (or `.gemini/commands/` if present).

| Instruction | Instruction File | Purpose |
|-------------|------------------|---------|
| `/process-list` | `docs-list.md` | List all specs, ADRs, and work logs |
| `/process-spec-new` | `docs-spec-new.md` | Create a new feature specification |
| `/process-adr-new` | `docs-adr-new.md` | Create a new Architecture Decision Record |
| `/process-status` | `docs-status.md` | Show active work |
| `/process-start` | `docs-start.md` | Start work on a PLANNED spec |
| `/process-complete` | `docs-complete.md` | Mark a spec as DONE |
| `/process-log` | `docs-log.md` | Add a work log entry |
| `/process-pause` | `docs-pause.md` | Pause work on a spec |
| `/process-index` | `docs-index.md` | Rebuild documentation index |

## Documentation Requirements

- **Backend API discoveries** should be documented in `SOLIPLEX.md`.
- **New Widgets**: When adding new GenUI widgets, update the table in `PROJECT.md`.
- **Feature tracking**: When working on new features, update `APP_FEATURES.md`:
  - Move features from "Planned" to "In Progress" when starting work.
  - Move features from "In Progress" to "Completed" when done.
  - Add implementation notes, files modified, and any gotchas discovered.
- **Architectural Changes**: Document major changes in `GEMINI_UNDERSTANDING.md`.

## Platform-Specific Code (dart:io)

SOLIPLEX must work on **Web**, **Mobile**, and **Desktop**. The `dart:io` package is NOT supported on web.

### Naming Convention
- `*_io.dart` - Native implementation using `dart:io`
- `*_web.dart` - Web implementation using `dart:html` or stubs

### Pattern
Use conditional imports:
```dart
import 'my_service_io.dart' if (dart.library.html) 'my_service_web.dart' as platform;
```

## Server-Scoped Provider Pattern

Panel state (chat, canvas, context pane, activity status) must reset when the server changes.
1. Extend `ServerScopedNotifier<State>` for panel notifiers
2. Declare providers in `lib/core/providers/panel_providers.dart`
3. Always `ref.watch(currentServerProvider)` in provider declarations

## Code Quality Requirements

- **Zero Tolerance Policy**: All linters and tests must pass 100%. No warnings or errors are acceptable in commits.
- **Workflow Order**: Before any commit, follow this sequence (preferring `dart mcp-server` tools when available):
    1. Format code
    2. Run analysis (Linter)
    3. Run tests
- **Tooling Preference**: Prefer the `dart mcp-server` over direct command line usage for all development tasks (formatting, linting, testing).
- **Linting**: Always use the latest `very_good_analysis` package. It is the project standard for strict enforcement of best practices.

### Analyzer

**`flutter analyze` must report ZERO errors and ZERO warnings.**
- Run analysis via `dart mcp-server` tools before committing.
- Fix all errors AND warnings immediately.

### Tests: All Must Pass

All tests must pass before any code is considered complete.

### Formatter

Code should be formatted before commits.

