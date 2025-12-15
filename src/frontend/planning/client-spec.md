# soliplex_client Package Specification

> Pure Dart package for Soliplex backend communication via HTTP and AG-UI protocols.

## 1. Overview

### 1.1 Purpose

Provide a reusable, testable, pure Dart client that:
- Connects to Soliplex backend servers
- Manages rooms, threads, and runs via REST API
- Streams AG-UI events for real-time chat
- Handles tool execution and message buffering

### 1.2 Design Principles

- **Pure Dart**: No Flutter dependencies, usable in CLI/server contexts
- **Dependency Injection**: All external dependencies injectable for testing
- **Immutable Models**: All data classes use `copyWith` pattern
- **Stream-Based**: AG-UI events exposed as Dart streams
- **Fail-Fast**: Validate inputs early, throw typed exceptions

### 1.3 Package Info

```yaml
name: soliplex_client
version: 1.0.0
environment:
  sdk: ^3.0.0

dependencies:
  http: ^1.2.0
  ag_ui: ^0.1.0
  meta: ^1.9.0

dev_dependencies:
  test: ^1.24.0
  mocktail: ^1.0.0
```

---

## 2. Public API

### 2.1 Exports (`lib/soliplex_client.dart`)

```dart
// Main client
export 'src/soliplex_client.dart' show SoliplexClient;

// Models
export 'src/models/room.dart';
export 'src/models/thread_info.dart';
export 'src/models/run_info.dart';
export 'src/models/chat_message.dart';
export 'src/models/tool_call_info.dart';

// Errors
export 'src/errors/exceptions.dart';

// HTTP (for custom adapters)
export 'src/http/http_client_adapter.dart';
export 'src/http/adapter_response.dart';

// Session (for advanced usage)
export 'src/session/room_session.dart' show RoomSession;
export 'src/session/connection_manager.dart' show ConnectionManager;

// AG-UI (for tool registration)
export 'src/agui/tool_registry.dart';
```

---

## 3. Data Models

### 3.1 Room

```dart
class Room {
  final String id;
  final String name;
  final String? description;
  final Map<String, dynamic> config;
  final DateTime createdAt;

  const Room({
    required this.id,
    required this.name,
    this.description,
    this.config = const {},
    required this.createdAt,
  });

  factory Room.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
  Room copyWith({...});
}
```

### 3.2 ThreadInfo

```dart
class ThreadInfo {
  final String id;
  final String roomId;
  final String? name;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final List<RunInfo> runs;

  const ThreadInfo({...});

  factory ThreadInfo.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
  ThreadInfo copyWith({...});
}
```

### 3.3 RunInfo

```dart
enum RunStatus { pending, running, completed, failed, cancelled }

class RunInfo {
  final String id;
  final String threadId;
  final RunStatus status;
  final String? label;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;
  final DateTime? completedAt;

  const RunInfo({...});

  factory RunInfo.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
  RunInfo copyWith({...});
}
```

### 3.4 ChatMessage

```dart
enum MessageType { text, error, toolCall, genUi, loading, system }
enum MessageRole { user, assistant, system }

class ChatMessage {
  final String id;
  final MessageRole role;
  final MessageType type;
  final String text;
  final String? thinkingText;
  final bool isStreaming;
  final List<ToolCallInfo> toolCalls;
  final Map<String, dynamic>? genUiData;
  final DateTime createdAt;

  const ChatMessage({...});

  factory ChatMessage.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
  ChatMessage copyWith({...});

  // Convenience constructors
  factory ChatMessage.user(String text);
  factory ChatMessage.assistant(String text);
  factory ChatMessage.error(String message);
  factory ChatMessage.loading();
}
```

### 3.5 ToolCallInfo

```dart
enum ToolCallStatus { pending, running, completed, failed }

class ToolCallInfo {
  final String id;
  final String name;
  final Map<String, dynamic> arguments;
  final ToolCallStatus status;
  final dynamic result;
  final String? error;
  final DateTime startedAt;
  final DateTime? completedAt;

  const ToolCallInfo({...});

  factory ToolCallInfo.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
  ToolCallInfo copyWith({...});
}
```

---

## 4. Error Handling

### 4.1 Exception Hierarchy

```dart
/// Base exception for all client errors
abstract class SoliplexException implements Exception {
  final String message;
  final Object? cause;
  const SoliplexException(this.message, [this.cause]);
}

/// Authentication/authorization failure (401, 403)
class AuthException extends SoliplexException {
  final int statusCode;
  const AuthException(super.message, this.statusCode, [super.cause]);
}

/// Network connectivity issues (timeout, DNS, connection refused)
class NetworkException extends SoliplexException {
  final Duration? timeout;
  const NetworkException(super.message, [this.timeout, super.cause]);
}

/// API errors (4xx, 5xx excluding 401/403/404)
class ApiException extends SoliplexException {
  final int statusCode;
  final Map<String, dynamic>? body;
  const ApiException(super.message, this.statusCode, [this.body, super.cause]);
}

/// Resource not found (404)
class NotFoundException extends SoliplexException {
  final String resource;
  final String id;
  const NotFoundException(this.resource, this.id)
      : super('$resource not found: $id');
}

/// Request cancelled by user
class CancelledException extends SoliplexException {
  const CancelledException() : super('Request cancelled');
}
```

### 4.2 Error Mapping

| HTTP Status | Exception |
|-------------|-----------|
| 401, 403 | `AuthException` |
| 404 | `NotFoundException` |
| 400, 402, 405-499 | `ApiException` |
| 500-599 | `ApiException` (with retry) |
| Timeout | `NetworkException` |
| Connection refused | `NetworkException` |
| DNS failure | `NetworkException` |

---

## 5. HTTP Layer

### 5.1 HttpClientAdapter (Interface)

```dart
/// Response from adapter
class AdapterResponse {
  final int statusCode;
  final Map<String, String> headers;
  final List<int> bodyBytes;

  const AdapterResponse({
    required this.statusCode,
    required this.headers,
    required this.bodyBytes,
  });

  String get body => utf8.decode(bodyBytes);
  Map<String, dynamic> get json => jsonDecode(body);
}

/// Abstract HTTP adapter for dependency injection
abstract class HttpClientAdapter {
  /// Make a request and return full response
  Future<AdapterResponse> request(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
    CancelToken? cancelToken,
  });

  /// Make a streaming request (for SSE)
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    CancelToken? cancelToken,
  });

  /// Close and release resources
  void close();
}
```

### 5.2 DartHttpAdapter (Default Implementation)

```dart
class DartHttpAdapter implements HttpClientAdapter {
  final http.Client _client;

  DartHttpAdapter([http.Client? client]) : _client = client ?? http.Client();

  @override
  Future<AdapterResponse> request(...) async {
    // Implementation using package:http
  }

  @override
  Stream<List<int>> requestStream(...) async* {
    // Implementation for SSE streaming
  }

  @override
  void close() => _client.close();
}
```

### 5.3 HttpTransport

```dart
class HttpTransport {
  final HttpClientAdapter _adapter;
  final Duration defaultTimeout;

  HttpTransport(
    this._adapter, {
    this.defaultTimeout = const Duration(seconds: 30),
  });

  /// GET request with JSON response
  Future<Map<String, dynamic>> get(
    Uri uri, {
    Map<String, String>? headers,
    Duration? timeout,
    CancelToken? cancelToken,
  });

  /// POST request with JSON body and response
  Future<Map<String, dynamic>> post(
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
    CancelToken? cancelToken,
  });

  /// DELETE request
  Future<void> delete(
    Uri uri, {
    Map<String, String>? headers,
    Duration? timeout,
    CancelToken? cancelToken,
  });

  /// Streaming POST (for AG-UI)
  Stream<List<int>> postStream(
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    CancelToken? cancelToken,
  });

  void close();
}
```

### 5.4 UrlBuilder

```dart
class UrlBuilder {
  final Uri baseUri;

  UrlBuilder(String baseUrl) : baseUri = _normalize(Uri.parse(baseUrl));

  /// Build API path: /api/v1/{path}
  Uri api(String path, [Map<String, String>? query]) {
    return baseUri.replace(
      path: '/api/v1/$path',
      queryParameters: query,
    );
  }

  /// Build rooms path: /api/v1/rooms/{roomId}
  Uri room(String roomId) => api('rooms/$roomId');

  /// Build threads path: /api/v1/rooms/{roomId}/agui
  Uri threads(String roomId) => api('rooms/$roomId/agui');

  /// Build thread path: /api/v1/rooms/{roomId}/agui/{threadId}
  Uri thread(String roomId, String threadId) =>
      api('rooms/$roomId/agui/$threadId');

  /// Build run path: /api/v1/rooms/{roomId}/agui/{threadId}/{runId}
  Uri run(String roomId, String threadId, String runId) =>
      api('rooms/$roomId/agui/$threadId/$runId');

  static Uri _normalize(Uri uri) {
    // Ensure https, remove trailing slash, etc.
  }
}
```

### 5.5 CancelToken

```dart
class CancelToken {
  bool _isCancelled = false;
  final _completer = Completer<void>();

  bool get isCancelled => _isCancelled;
  Future<void> get whenCancelled => _completer.future;

  void cancel() {
    if (!_isCancelled) {
      _isCancelled = true;
      _completer.complete();
    }
  }

  void throwIfCancelled() {
    if (_isCancelled) throw CancelledException();
  }
}
```

---

## 6. API Layer

### 6.1 SoliplexApi

```dart
class SoliplexApi {
  final HttpTransport _transport;
  final UrlBuilder _urls;

  SoliplexApi(this._transport, this._urls);

  // Room operations
  Future<List<Room>> getRooms({CancelToken? cancelToken});
  Future<Room> getRoom(String roomId, {CancelToken? cancelToken});

  // Thread operations
  Future<List<ThreadInfo>> getThreads(
    String roomId, {
    CancelToken? cancelToken,
  });

  Future<ThreadInfo> getThread(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  });

  Future<ThreadInfo> createThread(
    String roomId, {
    String? name,
    CancelToken? cancelToken,
  });

  Future<void> deleteThread(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  });

  // Run operations
  Future<RunInfo> createRun(
    String roomId,
    String threadId, {
    Map<String, dynamic>? metadata,
    CancelToken? cancelToken,
  });

  Future<RunInfo> getRun(
    String roomId,
    String threadId,
    String runId, {
    CancelToken? cancelToken,
  });

  Future<void> setRunMeta(
    String roomId,
    String threadId,
    String runId,
    Map<String, dynamic> metadata, {
    CancelToken? cancelToken,
  });

  // Streaming (returns raw stream for Thread to process)
  Stream<List<int>> runAgentStream(
    String roomId,
    String threadId,
    Map<String, dynamic> input, {
    CancelToken? cancelToken,
  });

  void close();
}
```

---

## 7. AG-UI Layer

### 7.1 Thread

```dart
/// Handles AG-UI protocol for a single conversation thread
class Thread {
  final String id;
  final ToolRegistry _toolRegistry;
  final TextMessageBuffer _textBuffer;
  final ToolCallReceptionBuffer _toolCallBuffer;

  Thread(this.id, {ToolRegistry? toolRegistry})
      : _toolRegistry = toolRegistry ?? ToolRegistry();

  /// Stream of assembled chat messages
  Stream<ChatMessage> get messageStream;

  /// Stream of raw AG-UI events (for Detail panel)
  Stream<AgUiEvent> get eventStream;

  /// Current messages list
  List<ChatMessage> get messages;

  /// Process incoming AG-UI event stream
  Future<void> processEventStream(Stream<AgUiEvent> events);

  /// Register a tool for client-side execution
  void registerTool(String name, ToolExecutor executor);

  /// Check if there are pending tool calls
  bool get hasPendingToolCalls;

  /// Get results of completed tool calls for next run
  List<ToolMessage> get toolResults;

  /// Clear state for new run
  void reset();
}

typedef ToolExecutor = Future<dynamic> Function(Map<String, dynamic> args);
```

### 7.2 TextMessageBuffer

```dart
/// Buffers streaming text chunks into complete messages
class TextMessageBuffer {
  String? _currentMessageId;
  final StringBuffer _textBuffer = StringBuffer();
  final StringBuffer _thinkingBuffer = StringBuffer();

  void startMessage(String id);
  void appendText(String chunk);
  void appendThinking(String chunk);
  ChatMessage? finishMessage();
  void reset();
}
```

### 7.3 ToolCallReceptionBuffer

```dart
/// Buffers streaming tool call arguments
class ToolCallReceptionBuffer {
  String? _currentCallId;
  String? _currentToolName;
  final StringBuffer _argsBuffer = StringBuffer();

  void startToolCall(String id, String name);
  void appendArgs(String chunk);
  ToolCallInfo? finishToolCall();
  void reset();
}
```

### 7.4 ToolRegistry

```dart
class ToolRegistry {
  final Map<String, ToolExecutor> _tools = {};
  final Set<String> _fireAndForget = {};

  void register(
    String name,
    ToolExecutor executor, {
    bool fireAndForget = false,
  });

  void unregister(String name);

  bool isRegistered(String name);
  bool isFireAndForget(String name);

  Future<dynamic> execute(String name, Map<String, dynamic> args);
}
```

---

## 8. Session Layer

### 8.1 RoomSession

```dart
/// Manages state for a single room
class RoomSession {
  final String roomId;
  final SoliplexApi _api;
  final Thread _thread;

  RoomSession(this.roomId, this._api);

  /// Current thread ID (null if no thread selected)
  String? get currentThreadId;

  /// Stream of message updates
  Stream<List<ChatMessage>> get messageStream;

  /// Current messages
  List<ChatMessage> get messages;

  /// Callbacks for canvas/context updates
  void Function(List<CanvasStateItem>)? onCanvasUpdate;
  void Function(List<ContextItem>)? onContextUpdate;
  void Function(ActivityStatus)? onActivityUpdate;

  /// Select or create a thread
  Future<void> selectThread(String? threadId);

  /// Send a message and process response
  Future<void> sendMessage(
    String text, {
    List<Tool>? tools,
    CancelToken? cancelToken,
  });

  /// Cancel current operation
  void cancel();

  /// Dispose resources
  void dispose();
}
```

### 8.2 ConnectionManager

```dart
/// Manages connections to multiple servers and rooms
class ConnectionManager {
  final HttpClientAdapter _adapter;
  final Map<String, RoomSession> _sessions = {};

  String? _currentServerUrl;
  String? _authToken;

  ConnectionManager({HttpClientAdapter? adapter})
      : _adapter = adapter ?? DartHttpAdapter();

  /// Current server URL
  String? get serverUrl => _currentServerUrl;

  /// Configure server connection
  void configure({
    required String serverUrl,
    String? authToken,
  });

  /// Get or create session for room
  RoomSession getSession(String roomId);

  /// Dispose session for room
  void disposeSession(String roomId);

  /// Switch to different server (disposes all sessions)
  void switchServer(String newServerUrl, {String? authToken});

  /// Dispose all resources
  void dispose();

  /// Event stream for connection events
  Stream<ConnectionEvent> get events;
}

abstract class ConnectionEvent {}
class SessionCreatedEvent extends ConnectionEvent { final String roomId; }
class SessionDisposedEvent extends ConnectionEvent { final String roomId; }
class ServerSwitchedEvent extends ConnectionEvent { final String serverUrl; }
```

---

## 9. Client Facade

### 9.1 SoliplexClient

```dart
/// Main entry point for the Soliplex client
class SoliplexClient {
  final ConnectionManager _connectionManager;
  final SoliplexApi _api;

  SoliplexClient({
    required String baseUrl,
    String? authToken,
    HttpClientAdapter? httpAdapter,
  });

  // === Configuration ===

  /// Current server URL
  String get serverUrl;

  /// Update auth token
  void setAuthToken(String? token);

  /// Switch to different server
  void switchServer(String newServerUrl, {String? authToken});

  // === Room Operations ===

  Future<List<Room>> getRooms({CancelToken? cancelToken});
  Future<Room> getRoom(String roomId, {CancelToken? cancelToken});

  // === Thread Operations ===

  Future<List<ThreadInfo>> getThreads(
    String roomId, {
    CancelToken? cancelToken,
  });

  Future<ThreadInfo> getThread(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  });

  Future<ThreadInfo> createThread(
    String roomId, {
    String? name,
    CancelToken? cancelToken,
  });

  Future<void> deleteThread(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  });

  // === Chat Operations ===

  /// Send a message and stream responses
  ///
  /// Returns a stream of message updates. The stream completes when
  /// the agent finishes responding (including all tool calls).
  Stream<List<ChatMessage>> chat({
    required String roomId,
    required String message,
    String? threadId,  // null = create new thread
    List<Tool>? tools,
    Map<String, ToolExecutor>? toolExecutors,
    CancelToken? cancelToken,
    void Function(List<CanvasStateItem>)? onCanvasUpdate,
    void Function(ActivityStatus)? onActivityUpdate,
  });

  /// Cancel current chat operation
  void cancelChat(String roomId);

  // === Session Access ===

  /// Get session for room (creates if needed)
  RoomSession getSession(String roomId);

  // === Lifecycle ===

  /// Dispose all resources
  void dispose();
}
```

---

## 10. Implementation Phases

### Phase 1: Models & Errors

**Files:**
- `lib/src/models/room.dart`
- `lib/src/models/thread_info.dart`
- `lib/src/models/run_info.dart`
- `lib/src/models/chat_message.dart`
- `lib/src/models/tool_call_info.dart`
- `lib/src/errors/exceptions.dart`

**Tests:**
- JSON serialization round-trip for all models
- `copyWith` behavior
- Exception instantiation and message formatting

**Acceptance Criteria:**
- [ ] All models parse from JSON fixtures matching backend format
- [ ] All models serialize back to JSON
- [ ] `copyWith` preserves unmodified fields
- [ ] Exceptions have meaningful `toString()` output
- [ ] 100% test coverage on models

---

### Phase 2: HTTP Foundation

**Files:**
- `lib/src/http/adapter_response.dart`
- `lib/src/http/http_client_adapter.dart`
- `lib/src/http/dart_http_adapter.dart`
- `lib/src/http/http_transport.dart`
- `lib/src/utils/url_builder.dart`
- `lib/src/utils/cancel_token.dart`

**Tests:**
- `UrlBuilder` path construction
- `CancelToken` cancellation flow
- `DartHttpAdapter` with mock HTTP client
- `HttpTransport` JSON handling, error mapping

**Acceptance Criteria:**
- [ ] `UrlBuilder` produces correct API paths
- [ ] `CancelToken` cancels pending requests
- [ ] `DartHttpAdapter` handles GET/POST/DELETE/streaming
- [ ] `HttpTransport` maps HTTP errors to exceptions
- [ ] Timeout handling works correctly
- [ ] 90% test coverage on HTTP layer

---

### Phase 3: API Layer

**Files:**
- `lib/src/api/soliplex_api.dart`

**Tests:**
- All CRUD operations with mock transport
- Error handling for 4xx/5xx responses
- Cancellation support

**Acceptance Criteria:**
- [ ] All API methods work with mock backend responses
- [ ] Proper exception types thrown for error responses
- [ ] Cancellation stops in-flight requests
- [ ] 90% test coverage on API layer

---

### Phase 4: AG-UI Protocol

**Files:**
- `lib/src/agui/thread.dart`
- `lib/src/agui/text_message_buffer.dart`
- `lib/src/agui/tool_call_reception_buffer.dart`
- `lib/src/agui/tool_registry.dart`

**Tests:**
- Event stream processing
- Message buffering and assembly
- Tool call buffering
- Tool execution and result collection
- Fire-and-forget tool handling

**Acceptance Criteria:**
- [ ] Thread correctly processes AG-UI event sequences
- [ ] Text messages assembled from streaming chunks
- [ ] Tool calls buffered and executed
- [ ] Tool results collected for next run iteration
- [ ] `messageStream` emits complete messages
- [ ] `eventStream` emits raw events
- [ ] 90% test coverage on AG-UI layer

---

### Phase 5: Sessions

**Files:**
- `lib/src/session/room_session.dart`
- `lib/src/session/connection_manager.dart`

**Tests:**
- Session lifecycle (create, use, dispose)
- Multi-room session management
- Server switching
- Message streaming

**Acceptance Criteria:**
- [ ] `RoomSession` manages thread selection
- [ ] `RoomSession` processes messages and updates callbacks
- [ ] `ConnectionManager` pools sessions by room
- [ ] Server switch disposes all sessions
- [ ] Connection events emitted correctly
- [ ] 85% test coverage on session layer

---

### Phase 6: Facade

**Files:**
- `lib/src/soliplex_client.dart`
- `lib/soliplex_client.dart` (exports)

**Tests:**
- Integration tests with mock backend
- Full chat flow (send message, receive response, tool calls)
- Cancellation during chat
- Server switching

**Acceptance Criteria:**
- [ ] `SoliplexClient` exposes clean public API
- [ ] `chat()` handles full conversation loop
- [ ] Tool execution works end-to-end
- [ ] Cancellation stops chat mid-stream
- [ ] All exports correct in barrel file
- [ ] 85% overall package coverage
- [ ] Example code in README works

---

## 11. Testing Strategy

### 11.1 Test Structure

```
test/
├── models/
│   ├── room_test.dart
│   ├── thread_info_test.dart
│   ├── run_info_test.dart
│   ├── chat_message_test.dart
│   └── tool_call_info_test.dart
├── errors/
│   └── exceptions_test.dart
├── http/
│   ├── url_builder_test.dart
│   ├── cancel_token_test.dart
│   ├── dart_http_adapter_test.dart
│   └── http_transport_test.dart
├── api/
│   └── soliplex_api_test.dart
├── agui/
│   ├── thread_test.dart
│   ├── text_message_buffer_test.dart
│   ├── tool_call_reception_buffer_test.dart
│   └── tool_registry_test.dart
├── session/
│   ├── room_session_test.dart
│   └── connection_manager_test.dart
├── soliplex_client_test.dart
├── fixtures/
│   ├── rooms.json
│   ├── threads.json
│   ├── agui_events.json
│   └── ...
└── mocks/
    ├── mock_http_adapter.dart
    └── mock_transport.dart
```

### 11.2 Test Fixtures

Create JSON fixtures matching backend API responses:
- `fixtures/rooms.json` - Room list response
- `fixtures/room.json` - Single room response
- `fixtures/threads.json` - Thread list response
- `fixtures/thread.json` - Single thread with runs
- `fixtures/agui_events/` - AG-UI event sequences

### 11.3 Coverage Requirements

| Layer | Target |
|-------|--------|
| Models | 100% |
| Errors | 100% |
| HTTP | 90% |
| API | 90% |
| AG-UI | 90% |
| Session | 85% |
| Facade | 85% |
| **Overall** | **85%** |

---

## 12. Documentation

### 12.1 README.md

```markdown
# soliplex_client

Pure Dart client for Soliplex backend.

## Installation

```yaml
dependencies:
  soliplex_client: ^1.0.0
```

## Quick Start

```dart
import 'package:soliplex_client/soliplex_client.dart';

final client = SoliplexClient(baseUrl: 'https://api.example.com');

// List rooms
final rooms = await client.getRooms();

// Chat in a room
await for (final messages in client.chat(
  roomId: rooms.first.id,
  message: 'Hello!',
)) {
  print('Messages: ${messages.length}');
}

// Cleanup
client.dispose();
```

## Native HTTP Adapters

For better performance on mobile/desktop, use native adapters:

```dart
import 'package:soliplex_client_native/soliplex_client_native.dart';

final client = SoliplexClient(
  baseUrl: 'https://api.example.com',
  httpAdapter: createPlatformAdapter(),
);
```

## API Reference

See [API documentation](link-to-dartdoc).
```

### 12.2 API Documentation

Generate with `dart doc`.

---

## 13. Appendix: Backend API Reference

### Endpoints Used

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms` | List rooms |
| GET | `/api/v1/rooms/{roomId}` | Get room |
| GET | `/api/v1/rooms/{roomId}/agui` | List threads |
| POST | `/api/v1/rooms/{roomId}/agui` | Create thread |
| GET | `/api/v1/rooms/{roomId}/agui/{threadId}` | Get thread |
| DELETE | `/api/v1/rooms/{roomId}/agui/{threadId}` | Delete thread |
| POST | `/api/v1/rooms/{roomId}/agui/{threadId}` | Create run (streaming) |
| GET | `/api/v1/rooms/{roomId}/agui/{threadId}/{runId}` | Get run |
| POST | `/api/v1/rooms/{roomId}/agui/{threadId}/{runId}/meta` | Set run metadata |

### AG-UI Events

| Event | Description |
|-------|-------------|
| `RUN_STARTED` | Run has started |
| `RUN_FINISHED` | Run completed successfully |
| `RUN_ERROR` | Run failed with error |
| `TEXT_MESSAGE_START` | Beginning of text message |
| `TEXT_MESSAGE_CONTENT` | Text chunk |
| `TEXT_MESSAGE_END` | End of text message |
| `TOOL_CALL_START` | Beginning of tool call |
| `TOOL_CALL_ARGS` | Tool arguments chunk |
| `TOOL_CALL_END` | End of tool call |
| `STATE_SNAPSHOT` | Full state snapshot |
| `STATE_DELTA` | State delta update |
| `ACTIVITY_SNAPSHOT` | Activity status snapshot |

---

*Last updated: 2024-12-15*
