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
├── client-worklog.md          - Progress tracking (resume here)
├── core_frontend.md           - Flutter infrastructure (Riverpod, navigation)
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
- **App Milestones (AM1-AM7)**: End-user testable features

See `planning/ROADMAP.md` for full milestone details and dependency graph.

### Priority 1: Client (`soliplex_client` package)

**CURRENT FOCUS** - Pure Dart package, complete before moving to UI

| Phase | Goal | Milestone |
|-------|------|-----------|
| 1 | Models & errors | DM1 |
| 2a | HTTP adapter interface + DartHttpAdapter | DM2 |
| 2b | HttpObserver + ObservableHttpAdapter | DM3 |
| 2c | HttpTransport, UrlBuilder, CancelToken | DM4 |
| 3 | API layer (SoliplexApi) | DM5 |
| 4 | AG-UI protocol (Thread, buffers, tool registry) | DM6 |
| 5 | Sessions (ConnectionManager, RoomSession) | DM7 |
| 6 | Facade (SoliplexClient) | DM8 |

### Priority 2: Core Frontend

Depends on: DM1 (AM1), DM6 (AM3)

| Phase | Goal | Milestone |
|-------|------|-----------|
| 1 | Project setup, auth, navigation | AM1 |
| 2 | ActiveRunNotifier + extensions | AM3 |
| 3 | Extensibility (SoliplexConfig, SoliplexRegistry) | AM7 |
| 4 | Polish, extract to `soliplex_core` package | AM7 |

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
- Run `flutter analyze` and `dart format` before commits
- Make sure there are no linter errors or warnings in the project
- Follow strict Flutter linting (`very_good_analysis` library)
- All tests must pass
- KISS, YAGNI, SOLID principles

## Terminology

- Milestone a significant, specific point in time that marks the completion of a major phase with deliverables that are testable by end user.
