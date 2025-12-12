# Plan: Network Layer Refactoring

## Summary

Refactor network layer to support:
- **Concurrent SSE streams** across multiple rooms
- **Room session preservation** (switch away and come back)
- **Network Observer** for connection visibility
- **Stop/Cancel** functionality
- **Web compatible** + pluggable for future native backends

---

## Architecture Overview

```
                         NetworkObserver (read-only visibility)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ConnectionManager                          │
│  - Map<roomId, RoomSession> sessions                           │
│  - switchRoom() / cancelRun() / getSession()                   │
└─────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
     ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
     │ RoomSession │         │ RoomSession │         │ RoomSession │
     │   Room A    │         │   Room B    │         │   Room C    │
     │ - Thread    │         │ - Thread    │         │ - Thread    │
     │ - chatHist  │         │ - chatHist  │         │ - chatHist  │
     │ - state     │         │ - state     │         │ - state     │
     └─────────────┘         └─────────────┘         └─────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   NetworkTransport (abstract)                    │
├─────────────────────────────────────────────────────────────────┤
│   HttpTransport (web)     │    NativeTransport (future)         │
│   - ag_ui.AgUiClient      │    - NSURLSession, etc.             │
└─────────────────────────────────────────────────────────────────┘
```

---

## New Files to Create

| File | Purpose |
|------|---------|
| `lib/core/network/network_transport.dart` | Abstract interface for pluggable networking |
| `lib/core/network/http_transport.dart` | Default web-compatible implementation |
| `lib/core/network/room_session.dart` | Per-room state container (Thread, chat history, cancel token) |
| `lib/core/network/connection_manager.dart` | Central hub managing all room sessions |
| `lib/core/network/network_observer.dart` | Read-only observer for UI visibility |
| `lib/core/network/connection_events.dart` | Event types (created, switched, cancelled) |
| `lib/core/services/room_chat_service.dart` | Per-room chat state (family provider) |

---

## Files to Modify

| File | Changes |
|------|---------|
| `lib/infrastructure/quick_agui/thread.dart` | Add CancelToken support to startRun() |
| `lib/core/services/agui_service.dart` | Refactor to delegate to ConnectionManager |
| `lib/core/services/chat_service.dart` | Keep for compatibility, add migration path |
| `lib/features/chat/chat_content.dart` | Wire stop button, use per-room providers |
| `lib/features/chat/chat_screen.dart` | Use ConnectionManager.switchRoom() |
| `lib/features/layouts/threecol_layout.dart` | Update room switching logic |

---

## Implementation Phases

### Phase 1: Core Infrastructure
**Goal**: Create transport layer and session containers without breaking existing code.

1. Create `NetworkTransport` abstract interface
2. Create `HttpTransport` implementation (wraps ag_ui.AgUiClient)
3. Create `RoomSession` class with:
   - Thread management
   - Chat history preservation
   - CancelToken support
   - State: active / backgrounded / disposed
4. Create `ConnectionManager` with:
   - Session pool (Map<roomId, RoomSession>)
   - switchRoom() - suspend old, resume new
   - cancelRun() - cancel active run
5. Create `NetworkObserver` for read-only visibility
6. Add CancelToken param to `Thread.startRun()`

### Phase 2: Per-Room State
**Goal**: Replace global chat state with per-room state.

1. Create `roomChatProvider` family provider
2. Create `activeChatProvider` derived from selectedRoom
3. Update `ChatContent` to use per-room providers
4. Keep old `chatProvider` as fallback during transition

### Phase 3: Integration
**Goal**: Wire everything together.

1. Create Riverpod providers:
   ```dart
   connectionManagerProvider
   networkObserverProvider
   roomChatProvider.family(roomId)
   ```
2. Refactor `AgUiService` to use `ConnectionManager`
3. Update room switching in `ChatScreen` to use `ConnectionManager.switchRoom()`

### Phase 4: Stop Button
**Goal**: Make stop button functional.

1. Add cancel endpoint to `HttpTransport`:
   ```
   POST /rooms/{roomId}/agui/{threadId}/{runId}/cancel
   ```
2. Wire stop button in activity overlay to `ConnectionManager.cancelRun()`
3. Handle cancellation gracefully in UI

### Phase 5: Session Preservation
**Goal**: Full room switch with state preservation.

1. On room switch:
   - Save chat history to RoomSession
   - Suspend session (keeps Thread alive in background)
2. On room resume:
   - Restore chat history from session
   - Resume session

### Phase 6: Network Observer UI (Optional)
**Goal**: Debug visibility panel.

1. Create `NetworkStatusPanel` widget
2. Show list of active connections
3. Show real-time event log
4. Manual cancel button per connection

---

## Key Classes

### NetworkTransport (Abstract)
```dart
abstract class NetworkTransport {
  Stream<BaseEvent> runAgent({endpoint, input, cancelToken});
  Future<void> cancelRun({roomId, threadId, runId});
  Future<Response> post(uri, body);
  Future<void> close();
}
```

### RoomSession
```dart
class RoomSession {
  final String roomId;
  Thread? thread;
  String? activeRunId;
  CancelToken? cancelToken;
  SessionState state; // active, backgrounded, disposed
  List<ChatMessage> chatHistory;

  void suspend();
  void resume();
  Future<void> cancelActiveRun();
  Future<void> chat(message, onEvent);
  void dispose();
}
```

### ConnectionManager
```dart
class ConnectionManager extends ChangeNotifier {
  Map<String, RoomSession> sessions;
  String? activeRoomId;

  RoomSession getSession(roomId);
  void switchRoom(newRoomId);
  Future<void> cancelRun(roomId);
  List<ConnectionInfo> get activeConnections;
}
```

---

## Riverpod Provider Structure

```
connectionManagerProvider (singleton)
    └── networkObserverProvider (derived)

roomChatProvider.family(roomId) (per-room)
    └── activeChatProvider (derived from selectedRoom)

selectedRoomProvider (state)
```

---

## Stop Button Flow

```
User taps stop button
    │
    ▼
ChatContent calls connectionManager.cancelRun(roomId)
    │
    ├── RoomSession.cancelToken.cancel()  (client-side abort)
    │
    └── transport.cancelRun(roomId, threadId, runId)  (server notification)
    │
    ▼
SSE stream aborts, UI updates
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| ag_ui client not designed for reuse | Create one client per room in HttpTransport |
| Browser SSE connection limits (6) | Session suspension limits active streams |
| Cancel endpoint not supported by server | Client-side cancel works, server call optional |
| Memory growth with many rooms | LRU eviction of backgrounded sessions |

---

## Testing Strategy

- Unit tests: Transport, Session lifecycle, ConnectionManager
- Integration tests: Full chat flow, room switching, cancel
- Widget tests: Stop button, room switch UI state
