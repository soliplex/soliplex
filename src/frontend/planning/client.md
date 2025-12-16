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
│ Layer 3: SoliplexApi                    │  DM5 ✓
│ - Room/Thread/Run CRUD operations       │
│ - 8 methods: getRooms, getRoom,         │
│   getThreads, getThread, createThread,  │
│   deleteThread, createRun, getRun       │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│ Layer 2: HttpTransport                  │  DM4 ✓
│ - JSON serialization/deserialization    │
│ - HTTP status → exception mapping       │
│ - Request timeout handling              │
│ - Streaming with cancellation           │
│   ┌───────────────────────────────┐     │
│   │ Utils: UrlBuilder, CancelToken│     │
│   └───────────────────────────────┘     │
└───────────────────┬─────────────────────┘
                    │ uses
┌───────────────────▼─────────────────────┐
│ Layer 1: HttpClientAdapter (interface)  │  DM2 ✓
│ - Abstract HTTP operations (DI)         │
│ - Returns AdapterResponse               │
└───────────────────┬─────────────────────┘
                    │ implements
┌───────────────────▼─────────────────────┐
│ Layer 0.5: ObservableHttpAdapter        │  DM3 ✓
│ - Decorator wrapping any adapter        │
│ - Notifies HttpObserver on all activity │
│ - Request/response/error/stream events  │
└───────────────────┬─────────────────────┘
                    │ wraps
┌───────────────────▼─────────────────────┐
│ Layer 0: Platform Implementations       │
│ ✓ DartHttpAdapter (default)             │  soliplex_client (DM2)
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

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `AdapterResponse` | HTTP response model with status helpers | Done |
| `HttpClientAdapter` | Abstract HTTP operations interface (DI) | Done |
| `DartHttpAdapter` | Default HTTP adapter using package:http | Done |
| `HttpObserver` | Interface for observing HTTP activity | Done |
| `ObservableHttpAdapter` | Decorator that notifies observers on all HTTP traffic | Done |
| `HttpTransport` | JSON wrapper using HttpClientAdapter | Done |
| `UrlBuilder` | URL construction with normalization | Done |
| `CancelToken` | Request cancellation | Done |
| `SoliplexApi` | Room/Thread/Run CRUD operations | Done |
| `Thread` | AG-UI protocol, tool registration | - |
| `ConnectionManager` | Server switching, session pooling | - |
| `RoomSession` | Per-room message state, event processing | - |

## Data Models

| Model | Fields |
|-------|--------|
| `ChatMessage` | id, user, type, text, thinkingText, isStreaming, toolCalls |
| `ToolCallInfo` | id, name, arguments, result, status |
| `Room` | id, name, config |
| `ThreadInfo` | id, createdAt, runs |
| `RunInfo` | id, threadId, status, createdAt, metadata |

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

Each phase maps to a Developer Milestone (DM). See `ROADMAP.md` for full milestone details.

| Phase | Goal | Components | Milestone | Status |
|-------|------|------------|-----------|--------|
| 1 | Models & errors | ChatMessage, Room, ThreadInfo, RunInfo, all exceptions | DM1 | Done |
| 2a | HTTP adapter | HttpClientAdapter (interface), DartHttpAdapter, AdapterResponse | DM2 | Done |
| 2b | Network observer | HttpObserver (interface), ObservableHttpAdapter (decorator) | DM3 | Done |
| 2c | HTTP transport | HttpTransport, UrlBuilder, CancelToken | DM4 | Done |
| 3 | API layer | SoliplexApi | DM5 | Done |
| 4 | AG-UI protocol | Thread, message buffers, tool registry | DM6 | - |
| 5 | Sessions | ConnectionManager, RoomSession | DM7 | - |
| 6 | Facade | SoliplexClient, chat() flow | DM8 | - |

## File Structure

```text
packages/soliplex_client/
├── lib/
│   ├── soliplex_client.dart           # Public API exports
│   └── src/
│       ├── api/                        # DM5 ✓
│       │   ├── api.dart                # Barrel export
│       │   └── soliplex_api.dart
│       ├── agui/                       # DM6
│       │   ├── thread.dart
│       │   ├── buffers.dart
│       │   └── tool_registry.dart
│       ├── errors/                     # DM1 ✓
│       │   ├── errors.dart             # Barrel export
│       │   └── exceptions.dart
│       ├── http/                       # DM2, DM3, DM4 ✓
│       │   ├── adapter_response.dart
│       │   ├── dart_http_adapter.dart
│       │   ├── http.dart               # Barrel export
│       │   ├── http_client_adapter.dart
│       │   ├── http_observer.dart
│       │   ├── http_transport.dart
│       │   └── observable_http_adapter.dart
│       ├── models/                     # DM1 ✓
│       │   ├── chat_message.dart
│       │   ├── models.dart             # Barrel export
│       │   ├── room.dart
│       │   ├── run_info.dart
│       │   └── thread_info.dart
│       ├── session/                    # DM7
│       │   ├── connection_manager.dart
│       │   └── room_session.dart
│       └── utils/                      # DM4 ✓
│           ├── cancel_token.dart
│           ├── url_builder.dart
│           └── utils.dart              # Barrel export
├── test/
│   ├── api/
│   │   └── soliplex_api_test.dart
│   ├── errors/
│   │   └── exceptions_test.dart
│   ├── http/
│   │   ├── adapter_response_test.dart
│   │   ├── dart_http_adapter_test.dart
│   │   ├── http_observer_test.dart
│   │   ├── http_transport_test.dart
│   │   └── observable_http_adapter_test.dart
│   ├── models/
│   │   ├── chat_message_test.dart
│   │   ├── room_test.dart
│   │   ├── run_info_test.dart
│   │   └── thread_info_test.dart
│   └── utils/
│       ├── cancel_token_test.dart
│       └── url_builder_test.dart
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
  very_good_analysis: ^10.0.0
  test: ^1.24.0
  mocktail: ^1.0.0
```

**Linting:** Use `very_good_analysis`. Run `dart format .` and `dart analyze` before commits.

**Note:** Native adapters are in separate `soliplex_client_native` package (v1.1 scope).
