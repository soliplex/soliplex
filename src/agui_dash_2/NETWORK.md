# Network Subsystem Architecture

This document describes the network architecture for the AGUI Dashboard application.

## Overview

The network layer uses a **Facade Pattern** where `AgUiService` provides a simplified API for the UI layer while delegating all networking and session management to `ConnectionManager`.

```
┌─────────────────────────────────────────────────────────────┐
│                    UI Layer                                  │
│  chat_content.dart, chat_screen.dart, threecol_layout.dart  │
└─────────────────────────────────────────────────────────────┘
                              │
                    ref.watch(configuredAgUiServiceProvider)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AgUiService (Facade)                      │
│  - Preserves existing API surface                           │
│  - Delegates to ConnectionManager                           │
│  - Maintains provider structure                             │
│  - Connection state tracking for UI                         │
└─────────────────────────────────────────────────────────────┘
                              │
                      delegates to
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ConnectionManager                          │
│  - Multi-room session management                            │
│  - Cancellation, observability                              │
│  - Tool registration and execution                          │
│  - LRU session eviction                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   RoomSession (per room)                     │
│  - Thread wrapper                                           │
│  - Chat history preservation                                │
│  - Session lifecycle (active/backgrounded/disposed)         │
│  - Tool call deduplication                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   HttpTransport                              │
│  - HTTP operations (POST, GET, SSE)                         │
│  - Web-compatible implementation                            │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### AgUiService (`lib/core/services/agui_service.dart`)

**Purpose:** Simplified API facade for UI layer.

**Key Methods:**
- `configure(config)` - Set current room, delegates to ConnectionManager
- `chat(message, ...)` - Send message, delegates to ConnectionManager.chat()
- `cancelCurrentRun()` - Cancel active run via ConnectionManager
- `loadThreadHistory(threadId)` - Fetch and parse thread history
- `resetConversation()` - Clear current session

**State:**
- `AgUiConnectionState` - UI binding for connection status
- `_config` - Current room configuration
- `_chatLock` - Mutex preventing concurrent chat() calls

### ConnectionManager (`lib/core/network/connection_manager.dart`)

**Purpose:** Central hub managing all room sessions.

**Key Methods:**
- `getSession(roomId)` - Get or create a RoomSession
- `switchRoom(roomId)` - Switch active room (suspend/resume sessions)
- `chat(roomId, message, ...)` - Full chat flow with tool execution
- `cancelRun(roomId)` - Cancel active run for a room
- `initializeSession(roomId)` - Create thread for session

**Features:**
- Multi-room session pool
- Room switching with state preservation
- LRU eviction of backgrounded sessions
- Observable events stream

### RoomSession (`lib/core/network/room_session.dart`)

**Purpose:** Per-room state container.

**Key Methods:**
- `initialize(client)` - Create thread
- `startRun(messages, state)` - Start chat run
- `sendToolResults(runId, results)` - Continue with tool results
- `cancelActiveRun(reason)` - Cancel via CancelToken
- `suspend()` / `resume()` - Session lifecycle
- `markToolCallProcessed(id)` - Deduplication tracking

**State:**
- `Thread` instance
- `SessionState` (active/streaming/backgrounded/disposed)
- Chat history preservation
- Tool call deduplication sets

### HttpTransport (`lib/core/network/http_transport.dart`)

**Purpose:** Low-level HTTP operations.

**Key Methods:**
- `post(uri, body)` - HTTP POST returning JSON
- `cancelRun(roomId, threadId, runId)` - Cancel notification to server

## Provider Structure

Providers are declared in `lib/core/services/agui_service.dart`:

```dart
// Server-scoped - recreated when server changes
final connectionManagerProvider = ChangeNotifierProvider<ConnectionManager>((ref) {
  final server = ref.watch(currentServerProvider);
  final config = ref.watch(agUiConfigProvider);
  return ConnectionManager(baseUrl: baseUrl, headers: config?.headers);
});

// Depends on ConnectionManager
final agUiServiceProvider = ChangeNotifierProvider<AgUiService>((ref) {
  final connectionManager = ref.watch(connectionManagerProvider);
  return AgUiService(connectionManager);
});

// Room configuration - resets on server change
final agUiConfigProvider = StateProvider<AgUiServiceConfig?>((ref) {
  ref.watch(currentServerProvider);
  return null;
});

// Auto-configures AgUiService when config changes
final configuredAgUiServiceProvider = Provider<AgUiService>((ref) {
  // ... auto-configuration logic
});
```

## Session Lifecycle

```
                    ┌──────────────┐
                    │   Created    │
                    └──────┬───────┘
                           │ initialize()
                           ▼
                    ┌──────────────┐
        ┌───────────│    Active    │───────────┐
        │           └──────┬───────┘           │
        │ suspend()        │ startRun()        │ dispose()
        ▼                  ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Backgrounded │    │  Streaming   │    │   Disposed   │
└──────┬───────┘    └──────┬───────┘    └──────────────┘
       │                   │
       │ resume()          │ run completes
       └───────────────────┴───────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Active    │
                    └──────────────┘
```

## Tool Call Deduplication

Tool call deduplication is handled at the session level:

```dart
// In RoomSession
final Set<String> _processedToolCalls = {};
final Set<String> _processedToolNotifications = {};

bool markToolCallProcessed(String toolCallId) {
  return _processedToolCalls.add(toolCallId);  // Returns false if duplicate
}
```

UI layer uses session methods instead of local tracking:

```dart
// In chat_content.dart
final session = connectionManager.getSession(roomId);
if (!session.markToolCallProcessed(toolCallId)) {
  return {'skipped': true, 'reason': 'duplicate'};
}
```

## Cancellation

Cancellation is handled at multiple levels:

1. **Client-side:** `CancelToken` in RoomSession aborts the stream
2. **Server-side:** HTTP POST to cancel endpoint notifies backend

```dart
// Cancel via AgUiService (facade)
await agUiService.cancelCurrentRun();

// Internally delegates to ConnectionManager
await _connectionManager.cancelRun(_config!.roomId);

// Which calls RoomSession
session.cancelActiveRun();
```

## Observability

ConnectionManager provides event streams:

```dart
final networkObserverProvider = Provider<NetworkObserver>((ref) {
  final manager = ref.watch(connectionManagerProvider);
  return NetworkObserver(manager);
});
```

Events include:
- `SessionCreatedEvent`
- `RunStartedEvent` / `RunCompletedEvent` / `RunCancelledEvent` / `RunFailedEvent`
- `SessionSuspendedEvent` / `SessionResumedEvent`
- `RoomSwitchedEvent`

## Future: Platform Transports

The architecture supports pluggable transports:

```
lib/core/network/
├── network_transport.dart      # Abstract interface (future)
├── http_transport.dart         # Web (current)
└── native_transport.dart       # iOS/Android (future)
```

When adding platform-specific implementations:

1. Create abstract `NetworkTransport` interface
2. Implement `NativeTransport` using platform HTTP clients
3. Use factory to select transport based on platform

```dart
NetworkTransport createTransport(String baseUrl) {
  if (kIsWeb) {
    return HttpTransport(baseUrl);
  } else {
    return NativeTransport(baseUrl);
  }
}
```

## Key Files

| File | Purpose |
|------|---------|
| `lib/core/services/agui_service.dart` | Facade + providers |
| `lib/core/network/connection_manager.dart` | Session pool management |
| `lib/core/network/room_session.dart` | Per-room state |
| `lib/core/network/http_transport.dart` | HTTP operations |
| `lib/core/network/connection_events.dart` | Event types |
| `lib/core/network/network_observer.dart` | Observability |
| `lib/core/network/cancel_token.dart` | Cancellation |
