# Gemini Code Notes

Project-specific instructions for Gemini when working on this codebase.

## Reference Documentation

- **SOLIPLEX.md** - Backend API documentation for AG-UI integration (endpoints, request/response schemas, state sync)
- **QUICK_AGUI.md** - Notes on the quick_agui Flutter library (issues, workarounds, architecture)
- **APP_FEATURES.md** - Planned, in-progress, and completed app features (feedback chips, notes pad, etc.)
- **GENUI-WIDGETS.md** - Widget system documentation (registry, creating widgets, semantic IDs, limitations)
- **STATE_MANAGEMENT.md** - Riverpod state management patterns (server-scoped providers, adding new panels)
- **docs/PROCESS.md** - Documentation lifecycle process (specs, ADRs, work logs)

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

- Any newly discovered information about `quick_agui` - especially design shortcomings, bugs, or architectural issues - should be documented in `QUICK_AGUI.md`
- This includes issues like:
  - Concurrency problems (e.g., shared state causing duplicate processing)
  - Event streaming edge cases
  - Tool registration/execution quirks
  - Any workarounds implemented in the app layer to compensate for library limitations
- Backend API discoveries should be documented in `SOLIPLEX.md`
- **Widget system**: When adding new GenUI widgets, update `GENUI-WIDGETS.md`:
  - Add to the registered widgets table
  - Document data schema
  - Add semantic ID logic if widget supports canvas
- **Feature tracking**: When working on new features, update `APP_FEATURES.md`:
  - Move features from "Planned" to "In Progress" when starting work
  - Move features from "In Progress" to "Completed" when done
  - Add implementation notes, files modified, and any gotchas discovered

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

### Analyzer: Zero Tolerance Policy

**`flutter analyze` must report ZERO errors and ZERO warnings.**
- Run `flutter analyze` before committing.
- Fix all errors AND warnings immediately.

### Tests: All Must Pass

All tests must pass before any code is considered complete:
```bash
flutter test
```

### Formatter

Code should be formatted before commits:
```bash
dart format lib test
```
