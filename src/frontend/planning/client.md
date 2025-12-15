# Client

Pure Dart component for backend communication via HTTP and AG-UI protocols.

## Architecture

### Network Stack (4 Layers)

```
┌─────────────────────────────────────────┐
│ Layer 3: SoliplexApi                    │
│ - Room/Thread/Run CRUD operations       │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│ Layer 2: HttpTransport                  │
│ - JSON serialization, timeout handling  │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│ Layer 1: HttpClientAdapter (interface)  │
│ - Abstract HTTP operations (DI)         │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│ Layer 0: Platform Implementations       │
│ - DartHttpAdapter (default)             │
│ - CupertinoHttpAdapter (iOS/macOS)      │
│ - AndroidHttpAdapter (Android)          │
│ - WindowsHttpAdapter (Windows)          │
│ - LinuxHttpAdapter (Linux)              │
│ - WebHttpAdapter (Web)                  │
└─────────────────────────────────────────┘
```

### Session Management

```
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

| Adapter | Platform | Client | Benefits |
|---------|----------|--------|----------|
| `DartHttpAdapter` | All | package:http | Default fallback |
| `CupertinoHttpAdapter` | iOS/macOS | NSURLSession | Native certs, background transfers, HTTP/2 |
| `AndroidHttpAdapter` | Android | OkHttp | Native certs, HTTP/2, connection pooling |
| `WindowsHttpAdapter` | Windows | WinHTTP | Native cert store, proxy settings |
| `LinuxHttpAdapter` | Linux | libcurl | Native certs, HTTP/2 |
| `WebHttpAdapter` | Web | fetch API | Browser cookies, CORS |

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
| 2 | HTTP foundation | HttpClientAdapter, DartHttpAdapter, HttpTransport, UrlBuilder, CancelToken |
| 3 | API layer | SoliplexApi (CRUD) |
| 4 | Sessions | ConnectionManager, RoomSession |
| 5 | AG-UI protocol | Thread, message buffers, tool registry |
| 6 | Facade | SoliplexClient, chat() flow |

**Note:** Native adapters (Cupertino, Android, Windows, Linux) are v1.1 scope.

## File Structure

```
lib/client/
├── soliplex_client.dart
├── api/soliplex_api.dart
├── models/{chat_message,room,thread_info,run_info}.dart
├── session/{connection_manager,room_session}.dart
├── agui/{thread,buffers,tool_registry}.dart
├── http/{http_client_adapter,http_transport,adapters/}.dart
└── utils/{url_builder,cancel_token}.dart
```

## Dependencies

```yaml
dependencies:
  http: ^1.2.0
  ag_ui: ^0.1.0
```
