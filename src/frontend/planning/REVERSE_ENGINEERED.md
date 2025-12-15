# SOLIPLEX Flutter Application - Architecture Documentation

**Version**: 1.0.0
**Last Updated**: 2025-12-15
**Audience**: Internal developers maintaining and extending this codebase

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Network Infrastructure (Deep Dive)](#network-infrastructure-deep-dive)
4. [State Management](#state-management)
5. [AG-UI Protocol Integration](#ag-ui-protocol-integration)
6. [Widget System](#widget-system)
7. [Cross-Platform Considerations](#cross-platform-considerations)
8. [Security Architecture](#security-architecture)
9. [Key Files Reference](#key-files-reference)
10. [Extension Guide](#extension-guide)

---

## Overview

### What is SOLIPLEX?

SOLIPLEX is a cross-platform Flutter application that provides an AI-powered chat interface with **Agentic Generative UI** capabilities. It connects to backend servers running the AFSOC-RAG system to enable RAG (Retrieval-Augmented Generation) conversations with native UI widget rendering.

**Platform Support**: Web, iOS, macOS, Linux, Windows

**Key Capabilities**:

- Multi-server connections with concurrent session management
- Real-time SSE (Server-Sent Events) streaming from AI agents
- Native widget rendering via GenUI protocol
- Canvas-based visual workspace for widget composition
- OIDC authentication with PKCE
- Offline session persistence and recovery

### Architecture Philosophy

The application follows a **clean layered architecture** with emphasis on:

- **Separation of concerns**: Clear boundaries between UI, business logic, and infrastructure
- **Testability**: Pure functions for event processing, dependency injection via Riverpod
- **Observability**: Network inspector for traffic capture and debugging
- **Resilience**: Retry logic, cancellation tokens, graceful error handling
- **Cross-platform**: Conditional imports for platform-specific features

---

## System Architecture

### High-Level Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Chat Screen  │  │ Canvas View  │  │ Context Pane │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
┌─────────┼──────────────────┼──────────────────┼─────────────────┐
│         │      STATE MANAGEMENT LAYER (Riverpod)                │
│  ┌──────▼──────────────────▼──────────────────▼─────────┐       │
│  │  Panel Providers (Server-scoped, per-room families)  │       │
│  │  - activeCanvasProvider                               │       │
│  │  - activeContextPaneProvider                          │       │
│  │  - roomMessageStreamProvider                          │       │
│  │  - roomActivityStatusProvider                         │       │
│  └──────┬────────────────────────────────────────────────┘       │
└─────────┼──────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │              SERVICE LAYER                            │
│  ┌──────▼────────┐  ┌────────────────┐  ┌──────────────┐       │
│  │ ConnectionReg │  │ EventProcessor │  │ WidgetReg    │       │
│  │ (Multi-server)│  │ (Pure function)│  │ (17 widgets) │       │
│  └──────┬────────┘  └────────────────┘  └──────────────┘       │
└─────────┼──────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │            PROTOCOL LAYER                             │
│  ┌──────▼─────────┐  ┌─────────────────┐                       │
│  │ RoomSession    │  │ HttpTransport   │                       │
│  │ (Chat history, │  │ (HTTP POST/GET) │                       │
│  │  event loop)   │  │                 │                       │
│  └──────┬─────────┘  └────────┬────────┘                       │
└─────────┼─────────────────────┼──────────────────────────────┘
          │                     │
┌─────────┼─────────────────────┼──────────────────────────────┐
│         │       NETWORK INFRASTRUCTURE LAYER                   │
│  ┌──────▼─────────────────────▼────────┐                       │
│  │   NetworkTransportLayer              │                       │
│  │   - http.Client (HTTP)               │                       │
│  │   - ag_ui.AgUiClient (SSE)           │                       │
│  │   - 401 Retry + Token Refresh        │                       │
│  │   - NetworkInspector (observability) │                       │
│  └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Codebase Statistics

- **Total Dart Files**: ~181 files
- **Lines of Code**: ~35,000 lines
- **Core Network Layer**:
  - `NetworkTransportLayer`: 518 lines
  - `ConnectionRegistry`: 514 lines
  - `RoomSession`: 1,345 lines

### Design Patterns

| Pattern | Usage | Location |
|---------|-------|----------|
| **Repository** | Data access abstraction for rooms, servers | `lib/core/services/rooms_service.dart` |
| **Facade** | Simplified API for AG-UI interaction | `lib/core/protocol/chat_session.dart` |
| **Observer** | Reactive state updates via Riverpod providers | `lib/core/providers/` |
| **Strategy** | Pluggable network transports (HTTP vs native) | `lib/core/network/http_transport.dart` |
| **Registry** | Widget factory for GenUI rendering | `lib/core/services/widget_registry.dart` |
| **Single-Flight** | Token refresh deduplication | `NetworkTransportLayer._handle401()` |
| **Factory** | Tool registration and execution | `lib/infrastructure/quick_agui/thread.dart` |

---

## Network Infrastructure (Deep Dive)

### Three-Layer Transport Architecture

SOLIPLEX uses a **3-layer network stack** to separate concerns and enable observability:

```text
┌─────────────────────────────────────────────────┐
│ Layer 3: HttpTransport (JSON serialization)    │
│ - post() → NetworkTransportLayer.post()        │
│ - get() → NetworkTransportLayer.get()          │
│ - Handles JSON encoding/decoding                │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│ Layer 2: NetworkTransportLayer (HTTP/SSE)      │
│ - Owns http.Client and ag_ui.AgUiClient        │
│ - 401 retry with single-flight token refresh   │
│ - SSE streaming with retry logic               │
│ - NetworkInspector hooks for observability     │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│ Layer 1: http.Client (dart:io or dart:html)    │
│ - Platform-specific HTTP implementation        │
│ - Web: XMLHttpRequest                          │
│ - Native: dart:io.HttpClient                   │
└─────────────────────────────────────────────────┘
```

### NetworkTransportLayer (`lib/core/network/network_transport_layer.dart`)

**Key Responsibilities**:

- Single source of truth for all network I/O
- Owns both HTTP client and SSE client
- Provides observable hooks for traffic capture
- Handles 401 Unauthorized with token refresh

**Key Interfaces**:

```dart
class NetworkTransportLayer {
  /// HTTP POST with 401 retry
  Future<http.Response> post(Uri uri, String body, {
    Map<String, String>? additionalHeaders,
  });

  /// HTTP GET with 401 retry
  Future<http.Response> get(Uri uri, {
    Map<String, String>? additionalHeaders,
  });

  /// SSE streaming with retry and watchdog timeout
  Stream<ag_ui.BaseEvent> runAgent(
    String endpoint,
    ag_ui.SimpleRunAgentInput input,
  );

  /// Update auth headers (recreates SSE client)
  void updateHeaders(Map<String, String> headers);
}
```

**Token Refresh Flow**:

```text
1. Request fails with 401
2. Check if refresh already in-flight (_refreshFuture)
3. If yes → wait for existing refresh
4. If no → acquire lock, call headerRefresher()
5. Update headers, recreate SSE client
6. Retry original request
7. Release lock
```

**Implementation Details**:

- **Single-flight lock**: `Completer<void>` prevents concurrent refreshes
- **Retry strategy**: 3 retries with exponential backoff (500ms intervals)
- **SSE watchdog**: 2-minute timeout if no events received (configurable)
- **Inspector hooks**: Records request/response metadata for debugging

### ConnectionRegistry (`lib/core/network/connection_registry.dart`)

**Purpose**: Top-level registry managing multiple server connections.

**Key Features**:

- **Multi-server support**: Maintains separate `ServerConnectionState` per server
- **Session pooling**: Per-server room sessions with LRU eviction
- **Automatic cleanup**: Background timer for inactive session disposal
- **Server focus**: Suspends old sessions when switching servers

**Session Lifecycle States**:

```dart
enum SessionState {
  active,        // UI visible, ready for messages
  streaming,     // Active SSE stream in progress
  backgrounded,  // UI hidden, preserved for quick resume
  suspended,     // Deep sleep, resources released
  disposed       // Permanent cleanup
}
```

**State Transitions**:

```text
active ─┬─> streaming (startRun called)
        └─> backgrounded (UI switches room)

streaming ─┬─> active (run completed)
           ├─> backgrounded (UI switches room, cancels run)
           └─> disposed (error or manual disposal)

backgrounded ─┬─> active (UI returns to room)
              ├─> suspended (inactivity timeout ~24h)
              └─> disposed (explicit removal)

suspended ──> disposed (cleanup timer or manual removal)
```

**Configuration**:

```dart
class ConnectionConfig {
  Duration serverInactivityTimeout;  // Default: 1 hour
  Duration roomInactivityTimeout;    // Default: 30 minutes
  Duration cleanupInterval;          // Default: 5 minutes
  int maxBackgroundedSessionsPerServer; // Default: 5 (LRU eviction)
}
```

### RoomSession (`lib/core/network/room_session.dart`)

**Purpose**: Per-room session managing thread lifecycle, chat history, and event processing.

**Key Responsibilities**:

- Thread creation and run management
- Message state (THE source of truth for chat messages)
- Event processing (AG-UI events → ChatMessage updates)
- Tool registration and execution
- Cancellation support via CancelToken

**Message State Architecture**:

```dart
class RoomSession {
  // THE authoritative message list
  final List<ChatMessage> _messages = [];

  // Stream for UI updates
  final StreamController<List<ChatMessage>> _messageController;

  // Event processing state
  final Map<String, String> _messageIdMap = {};  // AG-UI ID → Chat ID
  final Map<String, StringBuffer> _textBuffers = {};
  final Map<String, String> _toolCallMessageIds = {};

  // Deduplication
  final Set<String> _processedToolCalls = {};
}
```

**Event Processing Flow**:

```text
1. SSE event arrives → RoomSession.processEvent()
2. Build EventProcessingState snapshot
3. Call EventProcessor.process() (pure function)
4. Apply EventProcessingResult mutations to mutable state
5. Throttle updates (50ms) and emit to _messageController
6. Dispatch side effects (canvas, context pane, activity)
```

**Tool Execution**:

```dart
// Internal tools (fire-and-forget)
static const _genUiTool = ag_ui.Tool(
  name: 'genui_render',
  description: 'Render a UI widget',
  // ...
);

// External tools (with result response)
void _registerTools(LocalToolsService service) {
  for (final toolDef in service.tools) {
    addTool(agTool, (call) async {
      handleLocalToolExecution(call.id, toolName, 'executing');
      final result = await service.executeTool(...);
      handleLocalToolExecution(call.id, toolName, 'completed');
      return jsonEncode(result.result);
    });
  }
}
```

### SSE Streaming with Retry

**Watchdog Timeout**: Prevents zombie streams if server stops responding.

```dart
// In Thread.startRun()
final eventStream = _getRunAgentStream(endpoint, input);
final watchdogStream = streamTimeout
    ? eventStream.timeout(
        Duration(minutes: 2),
        onTimeout: (sink) => throw StreamTimeoutException(),
      )
    : eventStream;
```

**Retry Logic** (in `NetworkTransportLayer.runAgent()`):

```dart
var retryCount = 0;
const maxRetries = 3;

while (true) {
  try {
    await for (final event in _agUiClient.runAgent(endpoint, input)) {
      eventCount++;
      yield event;
    }
    break; // Success
  } catch (e) {
    if (eventCount > 0 || retryCount >= maxRetries) {
      rethrow; // Don't retry mid-stream
    }
    retryCount++;
    await Future.delayed(Duration(milliseconds: 500 * retryCount));
  }
}
```

### URL Building

**UrlBuilder** (`lib/core/utils/url_builder.dart`) provides centralized URL construction:

```dart
final builder = UrlBuilder('https://server.com');

builder.rooms();                              // /api/v1/rooms
builder.room(roomId);                         // /api/v1/rooms/{roomId}
builder.createThread(roomId);                 // /api/v1/rooms/{roomId}/agui (POST)
builder.executeRun(roomId, threadId, runId);  // /api/v1/rooms/{roomId}/agui/{threadId}/{runId}
```

**URL Normalization**:

- Ensures trailing slash for base URL
- Auto-adds `/api/v1` prefix
- Handles both `/` and no-`/` prefixed paths consistently

### NetworkInspector (`lib/core/network/network_inspector.dart`)

**Purpose**: Observability layer for debugging network traffic.

**Captured Metadata**:

- Request: method, URI, headers, body
- Response: status code, headers, body (or SSE event count)
- Timing: duration, timestamp
- Errors: exception messages

**Usage Pattern**:

```dart
final inspector = NetworkInspector();

// Inspector is injected into NetworkTransportLayer
final transport = NetworkTransportLayer(
  baseUrl: serverUrl,
  inspector: inspector,
);

// UI subscribes to inspector for debugging panel
ref.watch(networkInspectorProvider);
```

---

## State Management

### Riverpod Architecture (3-Tier)

SOLIPLEX uses **Riverpod** with a **3-tier provider hierarchy**:

```text
┌─────────────────────────────────────────────────┐
│ Tier 1: App-Level Providers                    │
│ - authStateProvider (global auth state)        │
│ - connectionRegistryProvider (singleton)       │
│ - currentServerProvider (selected server)      │
│ - selectedRoomProvider (selected room)         │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│ Tier 2: Panel-Level Providers (per-room)       │
│ - roomCanvasProvider(ServerRoomKey)            │
│ - roomContextPaneProvider(ServerRoomKey)       │
│ - roomActivityStatusProvider(ServerRoomKey)    │
│ - roomMessageStreamProvider(ServerRoomKey)     │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│ Tier 3: Feature-Level Providers                │
│ - markdownHooksProvider (callbacks)            │
│ - feedbackServiceProvider (per-room family)    │
│ - notesServiceProvider (per-room family)       │
└─────────────────────────────────────────────────┘
```

### ServerScopedNotifier Pattern

**Problem**: Panel state (canvas, context pane) must reset when server changes.

**Solution**: All panel providers watch `currentServerFromAppStateProvider`:

```dart
// lib/core/providers/panel_providers.dart

/// Canvas state clears when server changes
final canvasProvider = StateNotifierProvider<CanvasNotifier, CanvasState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return CanvasNotifier(serverId: server?.id);
});
```

**When to Use**:

- Panel state tied to server connection (canvas, context pane, activity)
- State should NOT persist when switching servers

**When NOT to Use**:

- App-level state (auth, settings)
- Per-room state that should persist across server switches

### Family Providers with ServerRoomKey

**Composite Key Pattern**:

```dart
@immutable
class ServerRoomKey {
  const ServerRoomKey({
    required this.serverId,
    required this.roomId,
  });

  final String serverId;
  final String roomId;

  @override
  bool operator ==(Object other) => /* equality check */;

  @override
  int get hashCode => Object.hash(serverId, roomId);
}
```

**Usage**:

```dart
// Per-room canvas state
final roomCanvasProvider = StateNotifierProvider.family<
  CanvasNotifier,
  CanvasState,
  ServerRoomKey
>((ref, key) => CanvasNotifier(
  serverId: key.serverId,
  roomId: key.roomId,
));

// Convenience provider for active room
final activeCanvasProvider = Provider<CanvasState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const CanvasState();
  return ref.watch(roomCanvasProvider(key));
});
```

### Message Stream Bridge

**Challenge**: UI needs reactive updates from RoomSession message changes.

**Solution**: `roomMessageStreamProvider` bridges session to UI:

```dart
final roomMessageStreamProvider = StreamProvider.family<
  List<ChatMessage>,
  ServerRoomKey
>((ref, key) {
  final registry = ref.watch(connectionRegistryProvider);
  final session = registry.getSession(key);
  return session.messageStream.startWith(session.messages);
});
```

**Key Pattern**: `startWith()` ensures current state is immediately available (no initial loading spinner).

### Provider Declaration Rules

**CRITICAL**: All panel providers MUST be declared in `lib/core/providers/panel_providers.dart`.

**Why**:

- Centralized visibility of server-scoped providers
- Ensures all panel state watches `currentServerFromAppStateProvider`
- Prevents accidental imports from service files (breaks reset behavior)

**How to Add a New Panel**:

**Step 1:** Create notifier extending `ServerScopedNotifier`:

```dart
class MyPanelNotifier extends StateNotifier<MyPanelState> {
  MyPanelNotifier({String? serverId, String? roomId})
    : _serverId = serverId, super(const MyPanelState());

  final String? _serverId;
}
```

**Step 2:** Declare provider in `panel_providers.dart`:

```dart
final roomMyPanelProvider = StateNotifierProvider.family<
  MyPanelNotifier,
  MyPanelState,
  ServerRoomKey
>((ref, key) => MyPanelNotifier(
  serverId: key.serverId,
  roomId: key.roomId,
));

final activeMyPanelProvider = Provider<MyPanelState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const MyPanelState();
  return ref.watch(roomMyPanelProvider(key));
});
```

**Step 3:** UI watches the active provider:

```dart
final panelState = ref.watch(activeMyPanelProvider);
```

---

## AG-UI Protocol Integration

### AG-UI Overview

**AG-UI** (Agentic Generative UI) is a protocol for real-time AI agent communication with UI rendering capabilities.

**Key Concepts**:

- **Thread**: Conversation context (persistent)
- **Run**: Single agent execution within a thread
- **Messages**: User, Assistant, Tool messages
- **Tools**: Client-side functions the agent can invoke
- **State**: Arbitrary JSON passed to agent (e.g., canvas contents)

### Thread Lifecycle

```text
1. Create Thread (POST /api/v1/rooms/{roomId}/agui)
   ← { thread_id, runs: { run_id: {...} } }

2. Send User Message
   a. Create Run (POST /api/v1/rooms/{roomId}/agui/{threadId})
      ← { run_id }
   b. Execute Run (POST .../agui/{threadId}/{runId}) [SSE stream]
      → { threadId, runId, messages, state, tools }
      ← SSE events: RUN_STARTED, TEXT_MESSAGE_*, TOOL_CALL_*, ...

3. Tool Execution Loop
   - Client executes tools locally
   - Creates new run with ToolMessage results
   - Repeats until no more tool calls

4. Conversation continues...
```

### Event Types

**Run Lifecycle**:

- `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`

**Text Streaming**:

- `TEXT_MESSAGE_START` → create message
- `TEXT_MESSAGE_CONTENT` → append delta
- `TEXT_MESSAGE_END` → finalize

**Tool Calls**:

- `TOOL_CALL_START` → tool invoked
- `TOOL_CALL_ARGS` → arguments streaming
- `TOOL_CALL_END` → arguments complete
- `TOOL_CALL_RESULT` → result returned

**State Updates**:

- `STATE_SNAPSHOT` → full state replacement
- `STATE_DELTA` → incremental update

**Thinking** (extended reasoning):

- `THINKING_TEXT_MESSAGE_START`
- `THINKING_TEXT_MESSAGE_CONTENT`
- `THINKING_TEXT_MESSAGE_END`

**Activity**:

- `ACTIVITY_SNAPSHOT` → agent activity status

**Custom** (GenUI):

- `CUSTOM` → custom events for UI tools

### EventProcessor (`lib/core/network/event_processor.dart`)

**Purpose**: Pure function for testable event processing.

**Key Abstraction**:

```dart
class EventProcessor {
  const EventProcessor();

  /// Process a single event and return mutations.
  /// Pure function - no side effects, no mutable state.
  EventProcessingResult process(
    EventProcessingState state,
    ag_ui.BaseEvent event,
  );
}
```

**EventProcessingResult** contains:

- `messageMutations`: Add/update chat messages
- `messageIdMapUpdate`: Update AG-UI ID mapping
- `textBuffersUpdate`: Update streaming buffers
- `thinkingBufferUpdate`: Update thinking state
- `contextUpdate`: Side effect for context pane
- `activityUpdate`: Side effect for activity status
- `canvasUpdate`: Side effect for canvas operations

**Benefits**:

- **Testability**: Easy to unit test with mock events
- **Determinism**: Same input → same output
- **Debugging**: No hidden state changes
- **Concurrency**: Thread-safe by design

### Tool Execution System

**Fire-and-Forget vs Standard Tools**:

```dart
// Fire-and-forget (UI tools, no result needed)
addTool(_genUiTool, executeInternalTool, fireAndForget: true);

// Standard (result sent back to agent)
addTool(agTool, (call) async {
  final result = await service.executeTool(call.id, call.function.name, args);
  return jsonEncode(result);
});
```

**Internal Tools** (registered by RoomSession):

- `genui_render`: Render widget in chat
- `canvas_render`: Render widget on canvas

**External Tools** (registered by LocalToolsService):

- `get_my_location`: GPS location
- Custom tools defined by backend

### State Sync

**Sending Canvas State to Agent**:

```dart
// In chat_content.dart
final canvasState = ref.read(activeCanvasProvider);
await session.sendMessage(
  text,
  state: canvasState.toJson(),  // {"canvas": [...]}
);
```

**Backend Requirement**: Agent must implement `StateHandler` protocol (see `SOLIPLEX.md` for details).

---

## Widget System

### Widget Registry

**Purpose**: Factory for rendering native Flutter widgets from JSON data.

**Registration**:

```dart
class WidgetRegistry {
  void register(String widgetName, WidgetBuilder builder) {
    _builders[widgetName.toLowerCase()] = builder;
  }

  Widget? build(BuildContext context, String widgetName,
                Map<String, dynamic> data, {
    void Function(String eventName, Map<String, dynamic> args)? onEvent,
  });
}
```

**Registered Widgets** (17 total):

| Widget | Purpose | Canvas Support | Event Callback |
|--------|---------|----------------|----------------|
| `InfoCard` | Info display with icon | Yes | Yes |
| `MetricDisplay` | Metric with trend indicator | No | No |
| `DataList` | Key-value list | No | No |
| `ErrorDisplay` | Error message | No | No |
| `LoadingIndicator` | Spinner | No | No |
| `ActionButton` | Clickable button | No | Yes |
| `ProgressCard` | Progress bar | No | No |
| `LocationCard` | GPS coordinates | No | No |
| `GISCard` | OpenStreetMap view | Yes | Yes |
| `SearchWidget` | Search interface | No | Yes |
| `SkillsCard` | Skills display | Yes | Yes |
| `ProjectCard` | Project summary | Yes | Yes |
| `NoteCard` | Note display | Yes | No |
| `CodeCard` | Code snippet | Yes | No |
| `MarkdownCard` | Markdown content | Yes | No |

**Widget Builder Signature**:

```dart
typedef WidgetBuilder = Widget Function(
  BuildContext context,
  Map<String, dynamic> data,
  void Function(String eventName, Map<String, dynamic> args)? onEvent,
);
```

### Semantic IDs for Canvas Widgets

**Purpose**: Stable IDs for canvas operations (update, remove).

**Pattern**:

```dart
// Generate semantic ID from data
String getSemanticId(Map<String, dynamic> data) {
  final type = data['type'] as String?;
  final id = data['id'] as String?;
  if (type != null && id != null) {
    return '$type-$id';  // e.g., "staff-u1", "project-p1"
  }
  return 'widget-${uuid.v4()}';  // Fallback to random ID
}
```

**Canvas Operations**:

```dart
// Append (default)
canvas_render(widget_name="ProjectCard", data={...}, position="append")

// Replace by semantic ID
canvas_render(widget_name="ProjectCard", data={id: "p1", ...}, position="replace")

// Clear all
canvas_render(widget_name="ProjectCard", position="clear")
```

### Adding a New Widget

**Step 1:** Create widget file:

```dart
// lib/widgets/registry/my_widget.dart
class MyWidget extends StatelessWidget {
  const MyWidget({required this.data, this.onEvent});

  final Map<String, dynamic> data;
  final void Function(String, Map<String, dynamic>)? onEvent;

  factory MyWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    return MyWidget(data: data, onEvent: onEvent);
  }

  @override
  Widget build(BuildContext context) {
    final title = data['title'] as String? ?? 'No Title';
    return Card(
      child: ListTile(
        title: Text(title),
        onTap: () => onEvent?.call('tap', {}),
      ),
    );
  }
}
```

**Step 2:** Register in WidgetRegistry:

```dart
// lib/core/services/widget_registry.dart
void _registerDefaultWidgets() {
  // ...
  register('MyWidget', (context, data, onEvent) {
    return MyWidget.fromData(data, onEvent);
  });
}
```

**Step 3:** Document in this file and `GENUI-WIDGETS.md`.

---

## Cross-Platform Considerations

### Platform-Specific Code Pattern

**CRITICAL**: SOLIPLEX must work on **Web**, **Mobile**, and **Desktop**. The `dart:io` package is **NOT** available on web.

**Conditional Imports**:

```dart
// my_service.dart
import 'my_service_io.dart' if (dart.library.html) 'my_service_web.dart' as platform;

Future<void> saveData(String data) async {
  await platform.saveDataImpl(data);
}

// my_service_io.dart (native)
import 'dart:io';

Future<void> saveDataImpl(String data) async {
  final file = File('path/to/file');
  await file.writeAsString(data);
}

// my_service_web.dart (web)
import 'dart:html';

Future<void> saveDataImpl(String data) async {
  window.localStorage['key'] = data;
}
```

**Naming Convention**:

- `*_io.dart`: Native implementation using `dart:io`
- `*_web.dart`: Web implementation using `dart:html` or stubs

**Current Platform-Specific Features**:

| Feature | Web | Native | Implementation |
|---------|-----|--------|----------------|
| Room Notes | Hidden (`kIsWeb` check) | File I/O | `notes_service_io.dart` |
| Feedback Storage | localStorage | File I/O | `feedback_service_io.dart` / `_web.dart` |
| Secure Storage | localStorage | flutter_secure_storage | `secure_storage_service_io.dart` / `_web.dart` |

**When to Hide UI on Web**:

```dart
// In build method
if (!kIsWeb)
  IconButton(
    icon: Icon(Icons.notes),
    onPressed: () => _showNotesDialog(),
  )
```

### HTTP Client Differences

**Web**: Uses `XMLHttpRequest` (browser-managed, no custom SSL)
**Native**: Uses `dart:io.HttpClient` (can customize SSL, certificates)

**Implication**: HTTPS enforcement and SSRF prevention differ by platform.

---

## Security Architecture

### Authentication Flow (OIDC + PKCE)

**1. Login Initiation**:

```text
User → LoginScreen → AuthManager.login(provider, server)
  ↓
AuthManager → OidcAuthInteractor.authorizeAndExchangeCode()
  ↓
OidcAuthInteractor → flutter_appauth (native OIDC flow)
  ↓
Browser/WebView → OIDC Provider (Keycloak)
  ↓
Authorization Code → flutter_appauth
  ↓
Token Exchange (PKCE) → Access Token + Refresh Token
  ↓
AuthManager → SecureTokenStorage.storeTokens()
```

**2. Token Storage**:

**Platform-Specific**:

- **iOS/macOS**: Keychain via `flutter_secure_storage`
- **Android**: KeyStore via `flutter_secure_storage`
- **Web**: `localStorage` (fallback, less secure)
- **Linux/Windows**: Encrypted file via `flutter_secure_storage`

**3. Token Refresh**:

```text
NetworkTransportLayer receives 401
  ↓
_handle401() → headerRefresher()
  ↓
AuthManager.refreshToken(serverId)
  ↓
SecureTokenStorage.getRefreshToken()
  ↓
HTTP POST to token endpoint with refresh_token
  ↓
New access_token + refresh_token
  ↓
SecureTokenStorage.storeTokens()
  ↓
NetworkTransportLayer.updateHeaders()
  ↓
Retry original request
```

**Single-Flight Lock**: Prevents concurrent refreshes for same server.

### HTTPS Enforcement

**URL Normalization**:

```dart
// In UrlBuilder
String normalizeServerUrl(String url) {
  // Upgrade http:// to https:// (except localhost)
  if (url.startsWith('http://') && !url.contains('localhost')) {
    url = url.replaceFirst('http://', 'https://');
  }
  return url;
}
```

**SSRF Prevention**:

- URL validation before network calls
- No arbitrary redirects
- Certificate pinning (native platforms only)

### Security Recommendations

**Completed**:

- ✅ OIDC with PKCE (no client secret exposure)
- ✅ Platform-appropriate secure storage
- ✅ HTTPS enforcement
- ✅ Token refresh with single-flight lock
- ✅ No sensitive data in logs (tokens redacted)

**Future Enhancements**:

- 🔄 Certificate pinning for production servers
- 🔄 Biometric authentication for token access
- 🔄 Token expiry warnings before expiration
- 🔄 Audit logging for security events

---

## Key Files Reference

### Network Layer

| File | Lines | Purpose |
|------|-------|---------|
| `lib/core/network/network_transport_layer.dart` | 518 | Low-level HTTP/SSE client with 401 retry |
| `lib/core/network/connection_registry.dart` | 514 | Multi-server connection manager |
| `lib/core/network/room_session.dart` | 1,345 | Per-room session with message state |
| `lib/core/network/http_transport.dart` | ~200 | JSON-level HTTP transport facade |
| `lib/core/network/network_inspector.dart` | ~150 | Traffic capture for debugging |
| `lib/core/network/cancel_token.dart` | ~50 | Cancellation support |
| `lib/core/network/connection_events.dart` | ~200 | Event types for session lifecycle |

### State Management Files

| File | Lines | Purpose |
|------|-------|---------|
| `lib/core/providers/panel_providers.dart` | 307 | All panel provider declarations |
| `lib/core/providers/app_providers.dart` | ~300 | App-level providers |
| `lib/core/services/canvas_service.dart` | ~250 | Canvas state management |
| `lib/core/services/context_pane_service.dart` | ~200 | Context pane state |
| `lib/core/services/activity_status_service.dart` | ~300 | Activity status with timers |

### Protocol Layer

| File | Lines | Purpose |
|------|-------|---------|
| `lib/infrastructure/quick_agui/thread.dart` | ~600 | Thread management and tool execution |
| `lib/core/network/event_processor.dart` | ~500 | Pure function event processing |
| `lib/core/protocol/chat_session.dart` | ~100 | ChatSession interface |
| `lib/infrastructure/quick_agui/tool_call_registry.dart` | ~200 | Tool state tracking |

### UI Layer

| File | Lines | Purpose |
|------|-------|---------|
| `lib/features/chat/chat_screen.dart` | ~600 | Main chat interface |
| `lib/features/chat/chat_content.dart` | ~800 | Message rendering and input |
| `lib/features/canvas/canvas_panel.dart` | ~400 | Canvas widget display |
| `lib/features/context/context_pane.dart` | ~300 | Context pane UI |

### Widget System Files

| File | Lines | Purpose |
|------|-------|---------|
| `lib/core/services/widget_registry.dart` | 146 | Widget factory registry |
| `lib/widgets/registry/*.dart` | ~150 each | Individual widget implementations |

### Authentication

| File | Lines | Purpose |
|------|-------|---------|
| `lib/core/services/auth_manager.dart` | ~400 | OIDC auth operations |
| `lib/core/auth/oidc_auth_interactor.dart` | ~300 | flutter_appauth wrapper |
| `lib/core/auth/secure_token_storage.dart` | ~150 | Token persistence |
| `lib/core/services/secure_storage_service.dart` | ~200 | Platform-specific storage |

### Utilities

| File | Lines | Purpose |
|------|-------|---------|
| `lib/core/utils/url_builder.dart` | ~200 | URL construction and normalization |
| `lib/core/utils/debug_log.dart` | ~100 | Categorized logging |
| `lib/core/utils/update_throttler.dart` | ~80 | UI update throttling |

---

## Extension Guide

### Adding a New Panel

**Scenario**: Add a "Notes Sidebar" panel to the UI.

**Step 1:** Create state model:

```dart
// lib/core/models/notes_sidebar_models.dart
@immutable
class NotesSidebarState {
  const NotesSidebarState({this.notes = const []});
  final List<Note> notes;

  NotesSidebarState copyWith({List<Note>? notes}) => /* ... */;
}
```

**Step 2:** Create notifier:

```dart
// lib/core/services/notes_sidebar_service.dart
class NotesSidebarNotifier extends StateNotifier<NotesSidebarState> {
  NotesSidebarNotifier({
    String? serverId,
    String? roomId,
  }) : _serverId = serverId,
       _roomId = roomId,
       super(const NotesSidebarState());

  final String? _serverId;
  final String? _roomId;

  void addNote(Note note) {
    state = state.copyWith(notes: [...state.notes, note]);
  }
}
```

**Step 3:** Declare provider in panel_providers.dart:

```dart
// lib/core/providers/panel_providers.dart
final roomNotesSidebarProvider = StateNotifierProvider.family<
  NotesSidebarNotifier,
  NotesSidebarState,
  ServerRoomKey
>((ref, key) => NotesSidebarNotifier(
  serverId: key.serverId,
  roomId: key.roomId,
));

final activeNotesSidebarProvider = Provider<NotesSidebarState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const NotesSidebarState();
  return ref.watch(roomNotesSidebarProvider(key));
});
```

**Step 4:** Create UI:

```dart
// lib/features/notes_sidebar/notes_sidebar.dart
class NotesSidebar extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(activeNotesSidebarProvider);
    final notifier = ref.read(activeNotesSidebarNotifierProvider);

    return ListView.builder(
      itemCount: state.notes.length,
      itemBuilder: (context, index) => /* ... */,
    );
  }
}
```

**Step 5:** Integrate into layout:

```dart
// lib/features/chat/chat_screen.dart
Row(
  children: [
    Expanded(child: ChatContent()),
    if (showNotesSidebar)
      Container(width: 300, child: NotesSidebar()),
  ],
)
```

### Adding a New Widget Type

**Scenario**: Add a "ChartWidget" for data visualization.

**Steps**:

**Step 1:** Create widget file:

```dart
// lib/widgets/registry/chart_widget.dart
import 'package:fl_chart/fl_chart.dart';

class ChartWidget extends StatelessWidget {
  const ChartWidget({required this.data, this.onEvent});

  final Map<String, dynamic> data;
  final void Function(String, Map<String, dynamic>)? onEvent;

  factory ChartWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    return ChartWidget(data: data, onEvent: onEvent);
  }

  @override
  Widget build(BuildContext context) {
    final chartType = data['chart_type'] as String? ?? 'line';
    final dataPoints = (data['data'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    if (chartType == 'bar') {
      return BarChart(/* ... */);
    } else {
      return LineChart(/* ... */);
    }
  }
}
```

**Step 2:** Register widget:

```dart
// lib/core/services/widget_registry.dart
void _registerDefaultWidgets() {
  // ...
  register('ChartWidget', (context, data, onEvent) {
    return ChartWidget.fromData(data, onEvent);
  });
}
```

**Step 3:** Add semantic ID logic (if canvas-compatible):

```dart
String getSemanticId(Map<String, dynamic> data) {
  final chartId = data['chart_id'] as String?;
  if (chartId != null) {
    return 'chart-$chartId';
  }
  return 'chart-${uuid.v4()}';
}
```

**Step 4:** Document:

- Add to table in `GENUI-WIDGETS.md`
- Update this file's widget table

### Adding a New Network Feature

**Scenario**: Add "request queueing" when offline.

**Steps**:

**Step 1:** Add state to RoomSession:

```dart
// In RoomSession
final Queue<PendingRequest> _queuedRequests = Queue();

class PendingRequest {
  final String text;
  final Map<String, dynamic>? state;
  final Completer<void> completer;
}
```

**Step 2:** Modify sendMessage:

```dart
Future<void> sendMessage(String text, {Map<String, dynamic>? state}) async {
  if (!_isOnline()) {
    // Queue request
    final request = PendingRequest(
      text: text,
      state: state,
      completer: Completer<void>(),
    );
    _queuedRequests.add(request);
    return request.completer.future;
  }

  // Normal flow
  await _sendMessageImpl(text, state: state);
}
```

**Step 3:** Add queue processor:

```dart
void _processQueue() async {
  while (_queuedRequests.isNotEmpty && _isOnline()) {
    final request = _queuedRequests.removeFirst();
    try {
      await _sendMessageImpl(request.text, state: request.state);
      request.completer.complete();
    } catch (e) {
      request.completer.completeError(e);
    }
  }
}
```

**Step 4:** Add connectivity monitoring:

```dart
StreamSubscription<ConnectivityResult>? _connectivitySubscription;

void _setupConnectivityMonitoring() {
  _connectivitySubscription =
    Connectivity().onConnectivityChanged.listen((result) {
      if (result != ConnectivityResult.none) {
        _processQueue();
      }
    });
}
```

**Step 5:** Update dispose:

```dart
@override
void dispose() {
  _connectivitySubscription?.cancel();
  // ... existing disposal
}
```

### Testing Patterns

**Network Layer Testing**:

```dart
// Use MockHttpTransport
final mockTransport = MockHttpTransport();
when(() => mockTransport.post(any(), any()))
  .thenAnswer((_) async => {'thread_id': 'test-123'});

final session = RoomSession(
  roomId: 'test-room',
  baseUrl: 'https://test.com',
  transport: mockTransport,
);
```

**Event Processing Testing**:

```dart
// EventProcessor is pure - easy to test
final processor = EventProcessor();
final state = EventProcessingState(/* ... */);
final event = ag_ui.TextMessageStartEvent(/* ... */);

final result = processor.process(state, event);

expect(result.messageMutations, hasLength(1));
expect(result.messageMutations.first, isA<AddMessage>());
```

**Widget Testing**:

```dart
testWidgets('ChartWidget renders bar chart', (tester) async {
  final widget = ChartWidget.fromData({
    'chart_type': 'bar',
    'data': [{'x': 1, 'y': 10}],
  }, null);

  await tester.pumpWidget(MaterialApp(home: widget));

  expect(find.byType(BarChart), findsOneWidget);
});
```

---

## Appendix: Architecture Decisions

### Why 3-Layer Network Stack?

**Rationale**:

- **Separation**: HTTP logic (Layer 2) separate from JSON serialization (Layer 3)
- **Observability**: NetworkInspector hooks in Layer 2 without coupling to business logic
- **Testability**: Can mock at any layer (HttpTransport for integration tests, NetworkTransportLayer for unit tests)
- **Platform Independence**: Layer 1 swaps based on platform without affecting Layers 2-3

### Why Riverpod Over BLoC or Provider?

**Rationale**:

- **Compile-time safety**: No runtime errors from typos
- **Family providers**: Natural multi-server, per-room state
- **Auto-disposal**: Providers dispose when no longer watched
- **Testing**: Easy to override providers in tests
- **Composition**: Providers can watch other providers

### Why Pure EventProcessor Instead of StatefulWidget?

**Rationale**:

- **Testability**: No async, no side effects, deterministic output
- **Debugging**: Easy to log input/output for troubleshooting
- **Concurrency**: Thread-safe by design (no shared mutable state)
- **Reproducibility**: Can replay events for bug reproduction

### Why ConnectionRegistry Instead of Global AgUiService?

**Rationale**:

- **Multi-server**: Users can connect to multiple backend servers simultaneously
- **Session Isolation**: Each server-room combo gets independent state
- **Resource Management**: LRU eviction and inactivity timeouts prevent memory leaks
- **Scalability**: Can handle dozens of backgrounded sessions without degradation

---

## Glossary

| Term | Definition |
|------|------------|
| **AG-UI** | Agentic Generative UI protocol for AI agent communication |
| **SSE** | Server-Sent Events, HTTP streaming for real-time updates |
| **GenUI** | Generative UI, AI-generated native widget rendering |
| **OIDC** | OpenID Connect, authentication protocol |
| **PKCE** | Proof Key for Code Exchange, security extension for OAuth |
| **Riverpod** | Flutter state management library |
| **Family Provider** | Riverpod provider parameterized by a key (e.g., ServerRoomKey) |
| **ServerRoomKey** | Composite key (serverId + roomId) for multi-server state |
| **RoomSession** | Per-room session managing thread, messages, and event processing |
| **ConnectionRegistry** | Top-level manager for multi-server connections |
| **EventProcessor** | Pure function for processing AG-UI events |
| **Thread** | AG-UI conversation context (persistent across runs) |
| **Run** | Single agent execution within a thread |
| **Tool** | Client-side function the agent can invoke |
| **Fire-and-Forget Tool** | Tool executed without sending result back (e.g., UI tools) |
| **Watchdog Timeout** | Timer that kills stalled SSE streams |
| **Single-Flight Lock** | Concurrency pattern to deduplicate parallel operations |

---

**Document Maintenance**: Update this file when adding major features, refactoring network layer, or changing state management patterns.

**Questions?** See existing documentation:

- `SOLIPLEX.md` - Backend API and AG-UI integration details
- `APP_FEATURES.md` - Feature tracking and implementation notes
- `PROJECT.md` - Project overview and status

**Last Reviewed**: 2025-12-15
**Reviewers**: Documentation Engineer
