# Client

Pure Dart component that communicates with the external backend service via HTTP and AGUI protocols.

## Requirements

### Configuration

- Configurable base URL (default: `http://localhost:8000`)
- Accept `TokenStorage` interface via dependency injection for token management
- Accept `http.Client` via dependency injection for HTTP requests (enables mocking)
- Handle `Authorization: Bearer <token>` header injection automatically
- Configurable timeout (default: 30 seconds)
- Configurable retry policy (default: 3 retries with exponential backoff)

```dart
import 'package:http/http.dart' as http;

class SoliplexClient {
  final String baseUrl;
  final TokenStorage tokenStorage;
  final http.Client httpClient;
  final Duration timeout;
  final int maxRetries;

  SoliplexClient({
    this.baseUrl = 'http://localhost:8000',
    required this.tokenStorage,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 30),
    this.maxRetries = 3,
  }) : httpClient = httpClient ?? http.Client();
}

/// Token storage interface - caller provides implementation
abstract class TokenStorage {
  Future<String?> getToken();
  Future<void> setToken(String token);
  Future<void> clearToken();
}
```

### Testability

The client is fully testable standalone (no Flutter required):

- Pure Dart - runs with `dart test`
- Mock `TokenStorage` with in-memory implementation
- Mock HTTP with `http.MockClient` or `mocktail`
- **Minimum test coverage: 85%**

```dart
test('fetches rooms', () async {
  final mockHttp = MockClient((req) async => Response('{}', 200));
  final client = SoliplexClient(
    tokenStorage: MockTokenStorage(),
    httpClient: mockHttp,
  );
  // test client methods...
});
```

### Error Handling

Define custom exceptions for different error scenarios:

```dart
/// Base exception for all client errors
abstract class SoliplexException implements Exception {
  final String message;
  final int? statusCode;
  SoliplexException(this.message, [this.statusCode]);
}

/// Authentication errors (401, 403, token issues)
class AuthException extends SoliplexException { ... }

/// Network errors (timeout, no connection)
class NetworkException extends SoliplexException { ... }

/// API errors (4xx, 5xx responses)
class ApiException extends SoliplexException { ... }

/// Resource not found (404)
class NotFoundException extends SoliplexException { ... }
```

Error handling strategy:

- Map HTTP status codes to appropriate exceptions
- Include response body in exception for debugging
- Retry on 5xx errors and network timeouts (up to maxRetries)
- Do not retry on 4xx errors (client errors)

### Cancellation

Support request cancellation for long-running operations:

```dart
/// Cancel ongoing requests (e.g., event streams)
void cancelRequest(String requestId);

/// Execute run returns a cancellable stream
(Stream<AgUiEvent>, CancelToken) executeRunWithCancel(...);
```

### Authentication

- List available OIDC providers (`GET /api/login`)
- Initiate OIDC auth flow (`GET /api/login/{system}`)
- Handle auth callback/token receipt (`GET /api/auth/{system}`)
- Get authenticated user profile (`GET /api/user_info`)
- Logout and clear stored token
- Store tokens securely

**Note:** Pure Dart cannot handle browser redirects. The client provides auth helper methods, but the actual OIDC redirect flow must be handled by Flutter (using `flutter_appauth` or `url_launcher`) or browser. The client's role is to:

1. Provide auth URLs for the caller to open
2. Accept the callback token after redirect completes
3. Store and manage the token for subsequent requests

### Rooms

- List all available rooms (`GET /api/v1/rooms`)
- Get single room configuration (`GET /api/v1/rooms/{room_id}`)
- Get room background image (`GET /api/v1/rooms/{room_id}/bg_image`)
- Get MCP client token for room (`GET /api/v1/rooms/{room_id}/mcp_token`)
- List documents in room's RAG database (`GET /api/v1/rooms/{room_id}/documents`)

### AGUI Threads

- List user's threads in a room (`GET /api/v1/rooms/{room_id}/agui`)
- Create new thread (`POST /api/v1/rooms/{room_id}/agui`) → returns `thread_id` + initial `run_id`
- Get thread metadata and runs (`GET /api/v1/rooms/{room_id}/agui/{thread_id}`)
- Delete thread (`POST /api/v1/rooms/{room_id}/agui/{thread_id}`)
- Update thread metadata (`POST /api/v1/rooms/{room_id}/agui/{thread_id}/meta`)

### AGUI Runs

- Create new run (`POST /api/v1/rooms/{room_id}/agui/{thread_id}`) → returns new `run_id`
- Get run metadata (`GET /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}`)
- Execute run and stream events (`POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}`)
- Update run metadata (`POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta`)

**Run Creation:**

- The initial run is created automatically when creating a new thread
- Subsequent runs are created via `POST /api/v1/rooms/{room_id}/agui/{thread_id}` with body:

```json
{
  "parent_run_id": "string | null",  // Optional: link to previous run for continuations
  "metadata": {
    "label": "string | null"
  }
}
```

**Run Execution Request:**

`executeRun()` sends a `RunAgentInput` body conforming to the AG-UI protocol:

```json
{
  "threadId": "string",
  "runId": "string",
  "parentRunId": "string | null",
  "state": {},                        // Arbitrary state object
  "messages": [                       // Message history
    {"id": "...", "role": "user", "content": "Hello"},
    {"id": "...", "role": "assistant", "content": "Hi there!"}
  ],
  "tools": [],                        // Tool definitions (usually empty, backend provides)
  "context": [],                      // Additional context items
  "forwardedProps": {}                // Pass-through properties
}
```

> **Note:** The backend currently has a routing conflict where `POST /api/v1/rooms/{room_id}/agui/{thread_id}` may be shadowed by the delete thread handler. If run creation fails, this backend issue should be investigated.

- Handle all AG-UI event types:
  - Run lifecycle: `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`
  - Steps: `STEP_STARTED`, `STEP_FINISHED`
  - Text messages: `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`, `TEXT_MESSAGE_CHUNK`
  - Tool calls: `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`, `TOOL_CALL_RESULT`
  - State: `STATE_SNAPSHOT`, `STATE_DELTA`
  - Messages: `MESSAGES_SNAPSHOT`
  - Activity: `ACTIVITY_SNAPSHOT`, `ACTIVITY_DELTA`

**Streaming API:**

```dart
/// Execute run returns a stream of AG-UI events
Stream<AgUiEvent> executeRun(String roomId, String threadId, String runId);

/// Event base class - each event type extends this
abstract class AgUiEvent {
  final String type;
  final DateTime? timestamp;
}
```

### Quiz

- Get quiz configuration (`GET /api/v1/rooms/{room_id}/quiz/{quiz_id}`)
- Submit answer for evaluation (`POST /api/v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}`)

### Installation

- Get installation configuration (`GET /api/v1/installation`)

### Utility

- Health check (`GET /api/ok`)

## Dependencies

```yaml
# pubspec.yaml
name: soliplex_client
description: Pure Dart client for Soliplex backend

environment:
  sdk: ^3.0.0

dependencies:
  http: ^1.2.0          # HTTP client
  ag_ui:                # AG-UI protocol types (optional, or define locally)
    git:
      url: https://github.com/soliplex/ag-ui.git
      path: sdks/community/dart

dev_dependencies:
  test: ^1.25.0         # Testing framework
  mocktail: ^1.0.0      # Mocking library
  coverage: ^1.0.0      # Code coverage
```

**JSON Serialization:** Use `dart:convert` (built-in) for JSON parsing. Model classes implement `fromJson` factory constructors and `toJson` methods manually for simplicity and to avoid code generation.

## Implementation Plan

### Phase 1: Project Setup & Core Infrastructure

**Implementation:**

- Create Dart package with `pubspec.yaml`
- Set up `SoliplexClient` class with DI parameters (baseUrl, tokenStorage, httpClient)
- Implement `TokenStorage` abstract interface
- Create `InMemoryTokenStorage` for testing
- Implement exception classes (`SoliplexException`, `AuthException`, `NetworkException`, `ApiException`, `NotFoundException`)
- Implement base HTTP request helper with auth header injection and error mapping

**Testing:**

- Unit tests for `SoliplexClient` instantiation
- Unit tests for `InMemoryTokenStorage`
- Unit tests for auth header injection
- Unit tests for HTTP error → exception mapping

**Linting & Analysis:**

- Configure `analysis_options.yaml` with strict rules
- Enable all lint rules, strict-casts, strict-inference
- Run `dart analyze` - must pass with no issues

**Documentation:**

- Document package purpose in `README.md`
- Add dartdoc comments to all public APIs
- Document `TokenStorage` interface contract

---

### Phase 2: Authentication

**Implementation:**

- `getAuthProviders()` - list OIDC providers
- `initiateAuth(system)` - start OIDC flow
- `handleAuthCallback(system, params)` - process callback, store token
- `getUserInfo()` - get user profile
- `logout()` - clear token

**Testing:**

- Mock HTTP responses for each auth endpoint
- Test token storage/retrieval flow
- Test auth header presence after login
- Test error handling for auth failures

**Linting & Analysis:**

- Run `dart analyze` - must pass
- Run `dart format --set-exit-if-changed .`

**Documentation:**

- Document auth flow in README
- Dartdoc for all auth methods
- Add usage example for authentication

---

### Phase 3: Rooms

**Implementation:**

- `getRooms()` - list all rooms
- `getRoom(roomId)` - get room config
- `getRoomBackgroundImage(roomId)` - get background image
- `getRoomMcpToken(roomId)` - get MCP token
- `getRoomDocuments(roomId)` - list RAG documents
- Create `Room` model class

**Testing:**

- Unit tests for each room method
- Test JSON parsing into `Room` model
- Test error handling (room not found, unauthorized)

**Linting & Analysis:**

- Run `dart analyze` - must pass
- Verify no unused imports or variables

**Documentation:**

- Dartdoc for all room methods
- Document `Room` model fields
- Add usage example for rooms

---

### Phase 4: AGUI Threads

**Implementation:**

- `getThreads(roomId)` - list threads
- `createThread(roomId, metadata)` - create thread
- `getThread(roomId, threadId)` - get thread with runs
- `deleteThread(roomId, threadId)` - delete thread
- `updateThreadMetadata(roomId, threadId, metadata)` - update metadata
- Create `Thread`, `ThreadMetadata` model classes

**Testing:**

- Unit tests for each thread method
- Test thread creation returns thread_id and run_id
- Test metadata updates
- Test thread deletion

**Linting & Analysis:**

- Run `dart analyze` - must pass
- Check test coverage >= 85%

**Documentation:**

- Dartdoc for all thread methods
- Document thread lifecycle
- Add usage example for thread management

---

### Phase 5: AGUI Runs & Event Streaming

**Implementation:**

- `createRun(roomId, threadId, {parentRunId?, metadata?})` - create new run, returns `Run`
- `getRun(roomId, threadId, runId)` - get run metadata
- `executeRun(roomId, threadId, runId, RunAgentInput)` - execute and stream events
- `executeRunWithCancel(...)` - cancellable version returning `(Stream, CancelToken)`
- `cancelRequest(requestId)` - cancel ongoing request
- `updateRunMetadata(roomId, threadId, runId, metadata)` - update metadata
- Create `Run`, `RunMetadata`, `RunAgentInput`, `CancelToken` model classes
- Create message models: `UserMessage`, `AssistantMessage`, `ToolMessage`, `SystemMessage`
- Implement AG-UI event parsing for all event types
- Create event stream handler with callbacks or Stream

**Testing:**

- Unit tests for run metadata methods
- Test SSE/event stream parsing
- Test each AG-UI event type parsing
- Test stream cancellation and error handling

**Linting & Analysis:**

- Run `dart analyze` - must pass
- Check test coverage >= 85%

**Documentation:**

- Dartdoc for all run methods
- Document AG-UI event types and handling
- Add usage example for event streaming

---

### Phase 6: Quiz, Installation & Utility

**Implementation:**

- `getQuiz(roomId, quizId)` - get quiz config
- `submitQuizAnswer(roomId, quizId, questionUuid, answer)` - submit answer
- `getInstallation()` - get installation config
- `healthCheck()` - check server status
- Create `Quiz`, `QuizQuestion`, `Installation` model classes

**Testing:**

- Unit tests for quiz methods
- Test answer submission and evaluation response
- Test installation config parsing
- Test health check

**Linting & Analysis:**

- Run `dart analyze` - must pass
- Final coverage check >= 85%
- Run `dart doc` to verify documentation completeness

**Documentation:**

- Dartdoc for all remaining methods
- Complete README with full API overview
- Add integration example showing full client usage
- Update CLAUDE.md with client package structure and usage patterns

---

### Phase Completion Checklist

Each phase must complete before moving to next:

- [ ] All implementation tasks done
- [ ] All tests passing (`dart test`)
- [ ] Test coverage >= 85%
- [ ] Linting passes (`dart analyze`)
- [ ] Code formatted (`dart format`)
- [ ] Documentation complete with dartdoc
- [ ] README updated
- [ ] CLAUDE.md updated (final phase only)

## References

- AG-UI documentation: <https://docs.ag-ui.com/introduction>
- AG-UI SDK: `ag_ui` from `https://github.com/soliplex/ag-ui.git` (path: `sdks/community/dart`)
- Reference Dart code for AG-UI handling:
  - `../flutter/lib/infrastructure/quick_agui/thread.dart`
  - `../flutter/lib/infrastructure/quick_agui/run.dart`
  - `../flutter/lib/infrastructure/quick_agui/text_message_buffer.dart`
  - `../flutter/lib/infrastructure/quick_agui/tool_call_reception_buffer.dart`
  - `../flutter/lib/infrastructure/quick_agui/tool_call_registry.dart`
- Backend API reference: `./external_backend_service.md`
