# CLAUDE.md

Update this file when the project structure changes.

## Project Overview

Cross-platform Flutter frontend for Soliplex AI-powered RAG system.

## Planning Files

```text
planning/
├── ROADMAP.md                 - Version roadmap and future enhancements
├── BRANDING-APPROACH.md       - White-label extensibility design
├── client.md                  - soliplex_client package spec
├── client-worklog.md          - soliplex_client progress tracking
├── core_frontend.md           - Flutter infrastructure (Riverpod, navigation)
├── core-frontend-worklog.md   - Core frontend progress tracking (resume here)
├── external_backend_service.md - Backend API reference
├── REVERSE_ENGINEERED.md      - Prototype architecture reference
└── ui/
    ├── chat.md                - Message display and input
    ├── history.md             - Thread list for current room
    ├── detail.md              - Event log, thinking, tool calls, state
    ├── current_canvas.md      - Ephemeral AG-UI snapshots
    └── permanent_canvas.md    - User-pinned items
```

## Architecture

### 3-Layer Structure

```text
┌─────────────────────────────────────────────┐
│              UI Components                   │
│  (Chat, History, Detail, Canvas)            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Core Frontend                   │
│  Providers │ Navigation │ AG-UI Processing  │
│  Config │ Registries (Widget, Panel, Route) │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│      soliplex_client (Pure Dart package)    │
└──────────────────────────────────────────────┘
         ▲ (optional, v1.1)
┌────────┴─────────────────────────────────────┐
│  soliplex_client_native (Flutter package)    │
│  Native HTTP adapters                        │
└──────────────────────────────────────────────┘
```

**Extensibility**: Core Frontend provides `SoliplexConfig` (branding, features) and `SoliplexRegistry` (custom widgets, commands, panels, routes) for white-label deployments.

### UI Component Scopes

| Component | Scope | Description |
|-----------|-------|-------------|
| History | Room | Thread list, auto-selection |
| Chat | Thread | Messages, streaming, input |
| Detail | Thread | Events, thinking, tools, state |
| CurrentCanvas | Thread | Ephemeral StateSnapshot/ActivitySnapshot |
| PermanentCanvas | Global | Persistent pinned items |

## Implementation Order (v1.0)

v1.0 uses a two-tier milestone system:

- **Developer Milestones (DM1-DM8)**: Client library work, verified by unit tests (85%+ coverage)
- **App Milestones (AM1-AM8)**: End-user testable features

See `planning/ROADMAP.md` for full milestone details and dependency graph.

**Note**: Backend runs without authentication for AM1-AM6. AM7 adds authentication UI for future backend auth.

### Priority 1: Client (`soliplex_client` package)

**CURRENT FOCUS** - Pure Dart package, complete before moving to UI

| Phase | Goal | Milestone | Status |
|-------|------|-----------|--------|
| 1 | Models & errors | DM1 | ✅ Done |
| 2a | HTTP adapter interface + DartHttpAdapter | DM2 | ✅ Done |
| 2b | HttpObserver + ObservableHttpAdapter | DM3 | ✅ Done |
| 2c | HttpTransport, UrlBuilder, CancelToken | DM4 | ✅ Done |
| 3 | API layer (SoliplexApi) | DM5 | ✅ Done |
| 4 | AG-UI protocol (Thread, buffers, tool registry) | DM6 | ✅ Done |
| 5 | Sessions (ConnectionManager, RoomSession) | DM7 | Not Started |
| 6 | Facade (SoliplexClient) | DM8 | Not Started |

**Progress:** 6/8 developer milestones complete. 587 tests, 100% coverage.

### Priority 2: Core Frontend

Depends on: DM1 (AM1), DM6 (AM3)

| Phase | Goal | Milestone | Status |
|-------|------|-----------|--------|
| 1 | Project setup, navigation (NO AUTH) | AM1 | Not Started |
| 2 | ActiveRunNotifier + extensions | AM3 | - |
| 3 | Authentication + Extensibility | AM7 | - |
| 4 | Multi-room, extract to `soliplex_core` package | AM8 | - |

### Priority 3: UI Components (Parallel)

Depends on: AM3 (Core Frontend phase 2)

| Component | Phases | Milestone |
|-----------|--------|-----------|
| history | 4 | AM3 (P1), AM4 (P2-P4) |
| chat | 3 | AM3 (P1), AM4 (P2-P3) |
| detail | 4 | AM5 |
| current_canvas | 3 | AM6 |
| permanent_canvas | 3 | AM6 |

**Key dependency**: Core Frontend Phase 2 (AM3) must include `ActiveRunState` extensions (`rawEvents`, `stateItems`, `currentActivity`) before detail and current_canvas can function.

**Future versions**: See `planning/ROADMAP.md` for v1.1, v1.2, and v2.0 feature plans.

## Development Rules

- Test coverage: 85%+
- Follow strict Flutter linting (`very_good_analysis` library)
- KISS, YAGNI, SOLID principles
- When adding a new Flutter or Dart package, add a `.gitignore` file based on: <https://github.com/flutter/flutter/blob/master/.gitignore>

## Terminology

- Milestone a significant, specific point in time that marks the completion of a major phase with deliverables that are testable by end user.

## Code Quality Requirements

### Formatter

Code should be formatted before commits:

```bash
dart format lib test
```

### Markdown Linting

All markdown files must pass markdownlint with zero errors:

```bash
npx markdownlint-cli "**/*.md"
```

**Configuration:** `.markdownlint.json` at project root.

**Disabled rules** (stylistic preferences):

- `MD013` - Line length (allows flexible formatting)
- `MD024` - Duplicate headings (needed for repeated section patterns)
- `MD033` - Inline HTML (allows HTML when needed)
- `MD036` - Emphasis as heading (allows **bold** labels)
- `MD041` - First line heading (CLAUDE.md starts with `#`)
- `MD060` - Table column style (allows compact tables)

**Key enforced rules:**

- `MD022` - Headings must have blank lines around them
- `MD032` - Lists must have blank lines around them

### Analyzer: Zero Tolerance Policy

**`flutter analyze` must report ZERO errors and ZERO warnings.**

This is mandatory for all code changes:

- Run `flutter analyze` before committing
- Fix all errors AND warnings AND hints immediately
- **No exceptions** - warnings are not "acceptable technical debt"

```bash
# Check before committing
flutter analyze

# Expected output: "No issues found!"
```

**Why this matters:**

- Analyzer warnings often indicate real bugs (null safety violations, unused variables, type mismatches)
- Warnings accumulate quickly - "just one" becomes hundreds
- Treating analyzer as strictly as tests prevents regression
- Clean analyzer output makes code review faster

### Tests: All Must Pass

All tests must pass before any code is considered complete:

```bash
flutter test
```

## Git Recommendations

### Files to Commit

Always commit these configuration files:

- `.markdownlint.json` - Markdown linting rules
- `analysis_options.yaml` - Dart analyzer rules
- `pubspec.yaml` - Package dependencies

### Files to Gitignore

Standard Flutter/Dart ignores (see `packages/soliplex_client/.gitignore`):

- `.dart_tool/`
- `build/`
- `.packages`
- `pubspec.lock` (for packages, not apps)
- `*.iml`
- `.idea/`

**Never gitignore** project configuration files like `.markdownlint.json` - they ensure team consistency.

### Dependencies

Keep non-major dependencies up to date:

```bash
flutter pub upgrade
cd ./packages/soliplex_client/ && flutter pub upgrade
```

Check for outdated dependencies (for major version upgrade):

```bash
flutter pub outdated
cd ./packages/soliplex_client/ && flutter pub outdated
```
