# Client

Pure Dart package (`soliplex_client`) for backend communication via HTTP and AG-UI protocols.

## Package Structure

| Package | Type | Contents |
|---------|------|----------|
| `soliplex_client` | Pure Dart | Core client, DartHttpAdapter, all business logic |
| `soliplex_client_native` | Flutter | Native HTTP adapters (v1.1) |

```text
packages/
├── soliplex_client/           # Pure Dart - this spec
└── soliplex_client_native/    # Flutter - v1.1 scope
```

## Architecture

### Network Stack (5 Layers)

```text
┌─────────────────────────────────────────┐
│ Layer 3: SoliplexApi                    │  soliplex_client
│ - Room/Thread/Run CRUD operations       │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│ Layer 2: HttpTransport                  │  soliplex_client
│ - JSON serialization, timeout handling  │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│ Layer 1: HttpClientAdapter (interface)  │  soliplex_client
│ - Abstract HTTP operations (DI)         │
└───────────────────┬─────────────────────┘
                    │ implements
┌───────────────────▼─────────────────────┐
│ Layer 0.5: ObservableHttpAdapter        │  soliplex_client
│ - Decorator wrapping any adapter        │
│ - Notifies HttpObserver on all activity │
└───────────────────┬─────────────────────┘
                    │ wraps
┌───────────────────▼─────────────────────┐
│ Layer 0: Platform Implementations       │
│ - DartHttpAdapter (default)             │  soliplex_client
│ - CupertinoHttpAdapter (iOS/macOS)      │  ┐
│ - AndroidHttpAdapter (Android)          │  │ soliplex_client_native
│ - WindowsHttpAdapter (Windows)          │  │ (v1.1)
│ - LinuxHttpAdapter (Linux)              │  │
│ - WebHttpAdapter (Web)                  │  ┘
└─────────────────────────────────────────┘
```

### Session Management

```text
SoliplexClient (facade) → ConnectionManager → RoomSession → Thread
```

## Security

- TLS 1.2+ required for all connections
- Tokens stored via platform secure storage (Keychain, Keystore, CredentialManager)
- No credentials in logs or error messages
- Input validation before network calls
- Certificate validation (native adapters can add pinning)

## Performance

- Connection keep-alive (HTTP/1.1 persistent, HTTP/2 multiplexing via native adapters)
- Request timeout: 30s default, configurable per-request
- SSE streaming with chunked transfer encoding
- Retry: 3x exponential backoff (500ms base) on 5xx/network errors
- Cancel in-flight requests via CancelToken

## HttpClientAdapter (Interface)

```dart
abstract class HttpClientAdapter {
  Future<AdapterResponse> request(String method, Uri uri, {Map<String, String>? headers, Object? body, Duration? timeout});
  Stream<List<int>> requestStream(String method, Uri uri, {Map<String, String>? headers, Object? body});
  void close();
}
```

### Platform Implementations

| Adapter | Package | Platform | Native Client |
|---------|---------|----------|---------------|
| `DartHttpAdapter` | `soliplex_client` | All | package:http |
| `CupertinoHttpAdapter` | `soliplex_client_native` | iOS/macOS | NSURLSession |
| `AndroidHttpAdapter` | `soliplex_client_native` | Android | OkHttp |
| `WindowsHttpAdapter` | `soliplex_client_native` | Windows | WinHTTP |
| `LinuxHttpAdapter` | `soliplex_client_native` | Linux | libcurl |
| `WebHttpAdapter` | `soliplex_client_native` | Web | fetch API |

### Adapter Injection

```dart
// Default (pure Dart)
final client = SoliplexClient(baseUrl: 'https://api.example.com');

// With native adapter (v1.1)
import 'package:soliplex_client_native/soliplex_client_native.dart';
final client = SoliplexClient(
  baseUrl: 'https://api.example.com',
  httpAdapter: createPlatformAdapter(),  // Auto-detects platform
);
```

## Error Handling

| Exception | Trigger | Action |
|-----------|---------|--------|
| `AuthException` | 401, 403 | Redirect to login |
| `NetworkException` | Timeout, unreachable | Show retry |
| `ApiException` | 4xx, 5xx | Show error |
| `NotFoundException` | 404 | Go back |
| `CancelledException` | User cancelled | Silent |

## Core Components

| Component | Responsibility |
|-----------|----------------|
| `UrlBuilder` | URL construction with normalization |
| `HttpTransport` | JSON wrapper using HttpClientAdapter |
| `HttpObserver` | Interface for observing HTTP activity |
| `ObservableHttpAdapter` | Decorator that notifies observers on all HTTP traffic |
| `ConnectionManager` | Server switching, session pooling |
| `RoomSession` | Per-room message state, event processing |
| `Thread` | AG-UI protocol, tool registration |
| `CancelToken` | Request cancellation |

## Data Models

| Model | Fields |
|-------|--------|
| `ChatMessage` | id, user, type, text, thinkingText, isStreaming, toolCalls |
| `ToolCallInfo` | id, name, arguments, result, status |
| `Room` | id, name, config |
| `ThreadInfo` | id, createdAt, runs |
| `RunInfo` | id, createdAt, metadata |

## API Methods (SoliplexApi)

| Method | Description |
|--------|-------------|
| `getRooms()` | List rooms |
| `getRoom(id)` | Get room config |
| `getThreads(roomId)` | List threads |
| `getThread(roomId, threadId)` | Get thread + runs |
| `createThread(roomId)` | Create thread + initial run |
| `deleteThread(roomId, threadId)` | Delete thread |
| `createRun(roomId, threadId)` | Create run |
| `getRun(roomId, threadId, runId)` | Get run metadata |

## Implementation Phases

| Phase | Goal | Components |
|-------|------|------------|
| 1 | Models & errors | ChatMessage, Room, ThreadInfo, RunInfo, all exceptions |
| 2 | HTTP foundation | HttpClientAdapter, DartHttpAdapter, HttpObserver, ObservableHttpAdapter, HttpTransport, UrlBuilder, CancelToken |
| 3 | API layer | SoliplexApi (CRUD) |
| 4 | AG-UI protocol | Thread, message buffers, tool registry |
| 5 | Sessions | ConnectionManager, RoomSession |
| 6 | Facade | SoliplexClient, chat() flow |

## File Structure

```text
packages/soliplex_client/
├── lib/
│   ├── soliplex_client.dart           # Public API exports
│   └── src/
│       ├── api/soliplex_api.dart
│       ├── models/
│       │   ├── chat_message.dart
│       │   ├── room.dart
│       │   ├── thread_info.dart
│       │   └── run_info.dart
│       ├── session/
│       │   ├── connection_manager.dart
│       │   └── room_session.dart
│       ├── agui/
│       │   ├── thread.dart
│       │   ├── buffers.dart
│       │   └── tool_registry.dart
│       ├── http/
│       │   ├── http_client_adapter.dart
│       │   ├── dart_http_adapter.dart
│       │   ├── http_observer.dart
│       │   ├── observable_http_adapter.dart
│       │   └── http_transport.dart
│       ├── errors/
│       │   └── exceptions.dart
│       └── utils/
│           ├── url_builder.dart
│           └── cancel_token.dart
├── test/
└── pubspec.yaml
```

## Dependencies

```yaml
# soliplex_client/pubspec.yaml
name: soliplex_client
description: Pure Dart client for Soliplex backend

dependencies:
  http: ^1.2.0
  ag_ui: ^0.1.0
  meta: ^1.9.0

dev_dependencies:
  very_good_analysis: ^6.0.0
  test: ^1.24.0
  mocktail: ^1.0.0
```

**Linting:** Use `very_good_analysis`. Run `dart format .` and `dart analyze` before commits.

**Note:** Native adapters are in separate `soliplex_client_native` package (v1.1 scope).
