# Flutter Architecture

The Soliplex Flutter app uses a layered architecture with Riverpod for state management.

## Directory Structure

```
lib/
├── core/
│   ├── auth/           # OIDC authentication
│   ├── chat/           # Chat session abstractions
│   ├── config/         # Connection configuration
│   ├── controllers/    # UI controllers
│   ├── models/         # Domain models
│   ├── network/        # AG-UI transport, event processing
│   ├── protocol/       # Protocol implementations
│   ├── providers/      # Riverpod providers
│   ├── router/         # App routing
│   ├── services/       # Business logic services
│   ├── state/          # State management utilities
│   └── utils/          # Utilities
├── features/
│   ├── auth/           # Authentication UI
│   ├── canvas/         # Canvas view
│   ├── chat/           # Chat UI, view models, widgets
│   ├── context/        # Context pane
│   ├── endpoints/      # Endpoint management
│   ├── inspector/      # Debug inspector
│   ├── keyboard/       # Keyboard shortcuts
│   ├── layouts/        # Layout components
│   ├── navigation/     # Navigation UI
│   ├── notes/          # Room notes
│   ├── room/           # Room selection
│   └── server/         # Server management
├── infrastructure/     # External integrations (quick_agui)
└── widgets/            # Shared widgets, registry
```

## State Management

Soliplex uses Riverpod for state management with server-scoped providers.

### Provider Hierarchy

```
App State (persisted)
    ↓
Server State (per connection)
    ↓
Room State (per room)
    ↓
UI State (ephemeral)
```

### Server-Scoped Providers

Panel state resets when the server changes. Providers watch `currentServerFromAppStateProvider`:

```dart
final myProvider = StateNotifierProvider<MyNotifier, MyState>((ref) {
  ref.watch(currentServerFromAppStateProvider);  // Required for reset
  return MyNotifier();
});
```

### Per-Room State (Family Providers)

Room-specific state uses `ServerRoomKey` as the family key:

```dart
// Define family provider
final roomCanvasProvider = StateNotifierProvider.family<
  CanvasNotifier,
  CanvasState,
  ServerRoomKey
>((ref, key) => CanvasNotifier(serverId: key.serverId, roomId: key.roomId));

// Convenience provider for active room
final activeCanvasProvider = Provider<CanvasState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const CanvasState();
  return ref.watch(roomCanvasProvider(key));
});
```

### Key Providers

| Provider | Purpose |
|----------|---------|
| `currentServerFromAppStateProvider` | Current server connection |
| `selectedRoomProvider` | Currently selected room |
| `activeServerRoomKeyProvider` | Combined server+room key |
| `roomMessageStreamProvider` | Per-room message stream |
| `unifiedMessageStreamProvider` | Messages for current mode |
| `roomCanvasProvider` | Per-room canvas state |
| `roomContextPaneProvider` | Per-room context pane |
| `roomActivityStatusProvider` | Per-room activity indicators |
| `roomToolExecutionProvider` | Per-room tool execution state |

## Event Processing

Events flow through a pipeline:

```
NetworkTransportLayer
    ↓ HTTP/SSE
EventProcessor
    ↓ Parse events
ChatSession
    ↓ Update state
UI (via providers)
```

### AG-UI Event Handling

```dart
void handleEvent(Map<String, dynamic> event) {
  switch (event['type']) {
    case 'STATE_SNAPSHOT':
      // Full state replacement
      _state = event['snapshot'];
      break;
    case 'STATE_DELTA':
      // Incremental JSON Patch update
      _applyDelta(event['delta']);
      break;
    case 'TEXT_MESSAGE_CONTENT':
      // Append to current message
      _appendContent(event['delta']);
      break;
  }
}
```

### Buffer States

Buffers accumulate data across events:

- `ThinkingBufferState` - Accumulates thinking/reasoning text
- `CitationsBufferState` - Collects citations for attachment to messages

## View Model Pattern

Domain models are mapped to view models for UI rendering:

```dart
// Domain model
class ChatMessage {
  final String id;
  final String content;
  final MessageRole role;
}

// View model for UI
abstract class ChatMessageViewModel {
  Widget build(BuildContext context);
}

class TextMessageViewModel extends ChatMessageViewModel {
  final String content;
  final bool isUser;

  @override
  Widget build(BuildContext context) => TextBubble(content: content);
}

// Mapper
class MessageViewModelMapper {
  ChatMessageViewModel map(ChatMessage message) {
    return switch (message) {
      TextMessage m => TextMessageViewModel(content: m.content),
      ToolCallMessage m => ToolCallViewModel(toolName: m.toolName),
      _ => ErrorMessageViewModel(),
    };
  }
}
```

### View Model Types

- `TextMessageViewModel` - Text/markdown content
- `ToolCallViewModel` - Tool execution display
- `GenUiViewModel` - Native widget rendering
- `ErrorMessageViewModel` - Error display

## Platform-Specific Code

The app runs on Web, Mobile, and Desktop. Platform differences are handled via conditional imports:

```dart
// Main file
import 'my_service_io.dart'
    if (dart.library.html) 'my_service_web.dart' as platform;

// Usage
final service = platform.createService();
```

### Platform Patterns

| Feature | Approach |
|---------|----------|
| Room Notes | Hidden on web (`kIsWeb`) |
| Feedback Storage | Conditional imports |
| Secure Storage | Platform-specific implementations |

## Authentication Flow

OIDC authentication uses middleware-based token handling:

```dart
// OidcClient wraps HTTP client with auth middleware
class OidcClient implements http.Client {
  final http.Client client;
  final OidcAuthInteractor middleware;
  final String serverId;

  // All HTTP methods apply auth via middleware before executing
  Future<http.Response> get(Uri url, {Map<String, String>? headers}) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(serverId, requestHeaders);
    return client.get(url, headers: requestHeaders);
  }
}

// Auth interactor interface handles token lifecycle
abstract class OidcAuthInteractor {
  // Apply Bearer token to headers map
  Future<void> applyToHeader(String serverId, Map<String, String> headers);

  // Apply Bearer token to HTTP request
  Future<void> applyToRequest(String serverId, http.BaseRequest request);

  // OAuth flow methods
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(String serverId, SsoConfig config);
  Future<OidcAuthTokenResponse?> refreshAccessToken(String serverId, SsoConfig config);
  Future<void> logout(String serverId, SsoConfig config);
}
```

Login flow is initiated via browser redirect to the server's `/login/{system}` endpoint.

## Network Layer

### Connection Registry

Manages connections per server+room:

```dart
class ConnectionRegistry {
  final Map<ServerRoomKey, RoomSession> _sessions = {};

  RoomSession getSession(ServerRoomKey key) {
    return _sessions.putIfAbsent(key, () => RoomSession(key));
  }
}
```

### Network Transport Layer

Handles SSE streaming for AG-UI:

```dart
class NetworkTransportLayer {
  final ag_ui.AgUiClient _agUiClient;

  /// Run an SSE agent stream with observable hooks
  Stream<ag_ui.BaseEvent> runAgent(
    String endpoint,
    ag_ui.SimpleRunAgentInput input,
  ) async* {
    final stream = _agUiClient.runAgent(
      threadId: input.threadId,
      runId: input.runId,
      input: input,
    );

    await for (final event in stream) {
      yield event;
    }
  }
}
```

## Adding Features

1. **Add models** to `core/models/`
2. **Add event handling** to `core/network/`
3. **Create view models** in `features/*/view_models/`
4. **Build widgets** in `features/*/widgets/`
5. **Add providers** to `core/providers/panel_providers.dart`
6. **Write tests** in `test/`

## Common Files

| Task | Files to Modify |
|------|-----------------|
| New message type | `chat_models.dart`, `event_processor.dart`, `message_view_model_mapper.dart` |
| New API endpoint | `api_constants.dart`, `url_builder.dart` |
| New provider | `panel_providers.dart` |
| New GenUI widget | `widgets/registry/`, `widget_registry.dart` |

## Source Code

- Providers: `lib/core/providers/`
- Network: `lib/core/network/`
- Chat: `lib/features/chat/`
- Services: `lib/core/services/`
