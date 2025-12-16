# CLAUDE.md

Update this file when the project structure changes.

## Project Overview

Cross-platform Flutter frontend for Soliplex AI-powered RAG system.

## Planning Files

```
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

```
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

### Priority 1: Client (`soliplex_client` package)

**CURRENT FOCUS** - Pure Dart package, complete before moving to UI

| Phase | Goal |
|-------|------|
| 1 | Models & errors |
| 2 | HTTP foundation (HttpClientAdapter, DartHttpAdapter, HttpTransport) |
| 3 | API layer (SoliplexApi) |
| 4 | AG-UI protocol (Thread, buffers, tool registry) |
| 5 | Sessions (ConnectionManager, RoomSession) |
| 6 | Facade (SoliplexClient) |

### Priority 2: Core Frontend

Depends on: Client phases 1-4

| Phase | Goal |
|-------|------|
| 1 | Project setup, auth, navigation |
| 2 | ActiveRunNotifier + extensions |
| 3 | Extensibility (SoliplexConfig, SoliplexRegistry) |
| 4 | Polish, extract to `soliplex_core` package |

### Priority 3: UI Components (Parallel)

Depends on: Core Frontend phase 2

```
history (4) ─┐
chat (3) ────┼─► permanent_canvas (3)
detail (4) ──┤
current_canvas (3) ─┘
```

**Key dependency**: core_frontend Phase 2 must include `ActiveRunState` extensions (`rawEvents`, `stateItems`, `currentActivity`) before detail and current_canvas can function.

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
