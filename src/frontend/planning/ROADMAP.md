# Roadmap

## Version Overview

| Version | Theme | Status |
|---------|-------|--------|
| v1.0 | Core Functionality | In Planning |
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

### Priority 1: Client (6 Phases)

**Package:** `soliplex_client` (Pure Dart)

| Phase | Goal |
|-------|------|
| 1 | Models & errors |
| 2 | HTTP foundation (HttpClientAdapter, DartHttpAdapter, HttpTransport) |
| 3 | API layer (SoliplexApi) |
| 4 | AG-UI protocol (Thread, buffers, tool registry) |
| 5 | Sessions (ConnectionManager, RoomSession) |
| 6 | Facade (SoliplexClient) |

### Priority 2: Core Frontend (4 Phases)

Depends on: Client phases 1-4

| Phase | Goal |
|-------|------|
| 1 | Project setup, auth, navigation |
| 2 | ActiveRunNotifier + extensions |
| 3 | Extensibility: SoliplexConfig, SoliplexRegistry |
| 4 | Polish, extract to `soliplex_core` package |

**Extensibility (Level 2):**
- `SoliplexConfig`: Branding, feature flags, default routes, servers
- `SoliplexRegistry`: Custom widgets, slash commands, panels, routes
- `PanelRegistry`, `CommandRegistry`, `RouteDefinition` abstractions

### Priority 3: UI Components

Depends on: Core Frontend phase 2

| Component | Phases |
|-----------|--------|
| history | 4 |
| chat | 3 |
| detail | 4 |
| current_canvas | 3 |
| permanent_canvas | 3 |

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
