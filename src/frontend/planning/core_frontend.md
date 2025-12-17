# Core Frontend

Flutter infrastructure using the `soliplex_client` package for backend interactions.

## Responsibilities

- Authentication (login/logout via OIDC)
- Backend URL configuration
- Navigation (go_router)
- State management (Riverpod)
- AG-UI event processing
- Extensibility (config, registries)

## Platforms

Web (primary), iOS, Android, macOS, Windows, Linux

## Key Providers

| Provider | Type | Purpose |
|----------|------|---------|
| `configProvider` | StateProvider | App configuration |
| `clientProvider` | Provider | SoliplexClient instance (AM7+) |
| `authStateProvider` | StateProvider | Auth state (AM7+) |
| `roomsProvider` | FutureProvider | Room list |
| `currentRoomProvider` | StateProvider | Selected room |
| `threadsProvider` | FutureProvider | Thread list for room |
| `currentThreadProvider` | StateProvider | Selected thread |
| `activeRunProvider` | StateNotifierProvider | AG-UI run state |

## ActiveRunState

```dart
class ActiveRunState {
  final String? threadId;
  final RunStatus status;           // idle, running, finished, error
  final List<Message> messages;
  final String? error;
  // Extensions for Detail/CurrentCanvas:
  final List<RawAgUiEvent> rawEvents;
  final List<CanvasStateItem> stateItems;
  final CanvasActivity? currentActivity;
}
```

## Authentication Flow

1. Open webview to `{baseUrl}/api/login/{provider}`
2. Server handles OIDC flow
3. Callback returns token
4. Store token securely

## Routes

| Route | Screen |
|-------|--------|
| `/login` | Login |
| `/settings` | Settings |
| `/rooms` | Room list |
| `/rooms/:roomId` | Room view |
| `/rooms/:roomId/thread/:threadId` | Thread view |

## AG-UI Event Handling

| Event | Action |
|-------|--------|
| `RUN_STARTED` | status = running |
| `TEXT_MESSAGE_*` | Update messages |
| `TOOL_CALL_*` | Update activity |
| `STATE_SNAPSHOT/DELTA` | Update stateItems |
| `RUN_FINISHED/ERROR` | status = finished/error |

## Error Handling

| Exception | Action |
|-----------|--------|
| `AuthException` | Redirect to login |
| `NetworkException` | Show retry |
| `NotFoundException` | Go back |
| `ApiException` | Show error |

## Extensibility (Level 2)

### SoliplexConfig

Configuration-driven customization at startup.

| Field | Purpose |
|-------|---------|
| `appName` | Display name |
| `theme` | ThemeData override |
| `features` | Enable/disable panels |
| `routes` | Initial route, hidden routes |
| `defaultServers` | Pre-configured backends |

### SoliplexRegistry

Runtime extension registration.

| Registry | Extensions |
|----------|------------|
| `widgets` | Custom GenUI widget builders |
| `commands` | Custom slash commands |
| `panels` | Custom panel definitions |
| `routes` | Custom route definitions |

### Key Abstractions

```dart
class SlashCommand {
  final String name;
  final String description;
  final bool Function(List<String> args, RoomSession session) handler;
}

class PanelDefinition {
  final String id;
  final String name;
  final IconData icon;
  final Widget Function(BuildContext, WidgetRef) builder;
  final PanelPosition defaultPosition;
}

class RouteDefinition {
  final String path;
  final Widget Function(BuildContext, GoRouterState) builder;
}
```

## Implementation Phases

| Phase | Goal | Milestone | Status |
|-------|------|-----------|--------|
| 1 | Project setup, navigation (NO AUTH) | AM1 | - |
| 2 | ActiveRunNotifier + extensions | AM3 | - |
| 3 | Authentication + Extensibility: SoliplexConfig, SoliplexRegistry | AM7 | - |
| 4 | Multi-room, extract to `soliplex_core` package | AM8 | - |

## Dependencies

```yaml
dependencies:
  soliplex_client:
    path: packages/soliplex_client    # Or published version
  flutter_riverpod: ^2.5.0
  go_router: ^14.0.0
  flutter_secure_storage: ^9.0.0
  # Optional for native HTTP adapters (v1.1):
  # soliplex_client_native: ^1.0.0

dev_dependencies:
  very_good_analysis: ^10.0.0
  flutter_test:
    sdk: flutter
  mocktail: ^1.0.0
```

**Linting:** Use `very_good_analysis`. Run `flutter analyze` and `dart format .` before commits.
