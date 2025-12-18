# Roadmap

## Version Overview

| Version | Theme | Status |
|---------|-------|--------|
| v1.0 | Core Functionality | In Progress |
| v1.1 | Enhanced UX + Native Network | Future |
| v1.2 | Power User Features | Future |
| v2.0 | Advanced Features | Future |

---

## Packages

| Package | Type | Version | Description |
|---------|------|---------|-------------|
| `soliplex_client` | Pure Dart | v1.0 | HTTP/AG-UI client, models, sessions |
| `soliplex_client_native` | Flutter | v1.1 | Native HTTP adapters (iOS, Android, Windows, Linux, Web) |
| `soliplex_core` | Flutter | v1.0 P4 | Core frontend extracted (providers, config, registries) |

---

## v1.0 - Core Functionality

### Milestones

v1.0 uses a two-tier milestone system:

- **Developer Milestones (DM)**: Client library work, verified by unit tests (85%+ coverage)
- **App Milestones (AM)**: End-user testable features

#### Developer Milestones (DM) - Client Package

| # | Name | Components | Test Criteria | Status |
|---|------|------------|---------------|--------|
| **DM1** | Models & Errors | ChatMessage, Room, ThreadInfo, RunInfo, all exceptions | 100% model coverage | Done |
| **DM2** | HTTP Adapter | HttpClientAdapter (interface), DartHttpAdapter, AdapterResponse | Request/response cycle works | Done |
| **DM3** | Network Observer | HttpObserver (interface), ObservableHttpAdapter (decorator) | HTTP traffic observable | Done |
| **DM4** | HTTP Transport | HttpTransport, UrlBuilder, CancelToken | JSON serialization, URL building, cancellation | Done |
| **DM5** | API Layer | SoliplexApi (CRUD) | Can fetch rooms, threads via API | Done |
| **DM6** | AG-UI Protocol | Thread, TextMessageBuffer, ToolCallBuffer, ToolRegistry | Event streaming works | Done |
| **DM7** | Sessions | ConnectionManager, RoomSession | Multi-room management works | - |
| **DM8** | Facade | SoliplexClient, chat() flow | Integration tests pass | - |

#### App Milestones (AM) - End-User Testable

| # | Name | Phases | Requires DM | User Can Test | Status |
|---|------|--------|-------------|---------------|--------|
| **AM1** | App Shell | Core P1 | DM1 | Launch app, navigate | ✅ Done |
| **AM2** | Connected Data | - | DM1-DM5 | See real rooms & threads from backend | ✅ Done |
| **AM3** | Working Chat | Core P2, Chat P1, History P1 | DM6 | Send message, receive AI response | ✅ Done |
| **AM4** | Full Chat | Chat P2-P3, History P2-P4 | - | Streaming, markdown, thread management | - |
| **AM5** | Inspector | Detail P1-P4 | - | Events, thinking, tool calls, state | - |
| **AM6** | Canvas | Current Canvas P1-P3, Permanent Canvas P1-P3 | - | State snapshots, pin items | - |
| **AM7*** | Authentication | - | DM7-DM8 | Login, token refresh | - |
| **AM8*** | Polish | Core P3-P4 | DM7-DM8 | Multi-room, white-label ready | - |

#### Milestone Dependencies

```text
            DM Track (Developer Milestones)
DM1 → DM2 → DM3 → DM4 → DM5 → DM6 → DM7 → DM8
 │                        │      │          │
 ▼                        ▼      ▼          ▼
AM1 ──────────────────► AM2 ─► AM3 ──────────
(App Shell)         (Connected) (Chat)
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
                  AM4          AM5          AM6
                (Full Chat) (Inspector)  (Canvas)
                    │            │            │
                    └────────────┴────────────┘
                                 │
                                 ▼
                               AM7
```

---

### Priority 1: Client (Phases → DM1-DM8)

**Package:** `soliplex_client` (Pure Dart)

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

### Priority 2: Core Frontend (4 Phases)

Depends on: DM1 (AM1), DM6 (AM3)

| Phase | Goal | Milestone |
|-------|------|-----------|
| 1 | Project setup, navigation | AM1 |
| 2 | ActiveRunNotifier + extensions | AM3 |
| 3 | Extensibility: SoliplexConfig, SoliplexRegistry | AM7 |
| 4 | Polish, extract to `soliplex_core` package | AM7 |

**Extensibility (Level 2):**

- `SoliplexConfig`: Branding, feature flags, default routes, servers
- `SoliplexRegistry`: Custom widgets, slash commands, panels, routes
- `PanelRegistry`, `CommandRegistry`, `RouteDefinition` abstractions

### Priority 3: UI Components

Depends on: AM3 (Core Frontend phase 2)

| Component | Phases | Milestone |
|-----------|--------|-----------|
| history | 4 | AM3 (P1), AM4 (P2-P4) |
| chat | 3 | AM3 (P1), AM4 (P2-P3) |
| detail | 4 | AM5 |
| current_canvas | 3 | AM6 |
| permanent_canvas | 3 | AM6 |

---

## v1.1 - Enhanced UX + Native Network

**Chat**: Media messages, tool call visualization, message search
**History**: Thread deletion/renaming/grouping
**Detail**: Event export, chat message linking
**Core**: Token refresh, desktop polish
**Network** (`soliplex_client_native` package):

- Native HTTP adapters (Cupertino, Android, Windows, Linux, Web)
- Certificate pinning
- Platform auto-detection via `createPlatformAdapter()`

---

## v1.2 - Power User Features

**History**: Pagination, search, reorder
**Detail**: Event comparison/replay, performance metrics, timeline
**Canvas**: Export, history, custom renderers
**Permanent Canvas**: Folders, markdown export

---

## v2.0 - Advanced Features

Cloud sync, offline support, push notifications

---

## Dependencies

```text
v1.0 → v1.1 (Native adapters, UX polish)
     → v1.2 (Power features)
          → v2.0 (Cloud, offline)
```
