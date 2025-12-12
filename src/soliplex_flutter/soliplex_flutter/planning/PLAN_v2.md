# Implementation Plan v2: Soliplex Flutter

## References
- Planning files in current directory (highest priority)
- `/Users/jaeminjo/enfold/Soliplex-planning/new_dash_2/` (architecture patterns)
- AG-UI SDK: `https://github.com/soliplex/ag-ui.git` (path: `sdks/community/dart`)
- Existing code: `../flutter/lib/infrastructure/quick_agui/`

## Guiding Principles
- **Bare minimum** Flutter app, fully **cross-platform** (iOS, Android, Web, macOS, Windows, Linux)
- **Strict linting** with analyzer configured for everything
- **Automated testing** framework from day one
- **Client is pure Dart** - no Flutter imports, testable in isolation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ConnectionManager (singleton)                            ││
│  │   - Server switching, session pool, auth headers         ││
│  │   └─> RoomSession (per-room, MESSAGE AUTHORITY)         ││
│  │         - Owns messages list, event processing           ││
│  │         └─> Thread (AG-UI protocol)                     ││
│  │               - SSE streaming, tool registry, buffers    ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Models: Room, Thread, Run, Message, State               ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Utilities: UrlBuilder, HttpTransport, CancelToken       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  State Management: Riverpod (server-scoped providers)        │
│  ┌──────────┬──────────┬──────────┬──────────┬────────────┐ │
│  │ TestPage │  Chat    │ Canvas   │ History  │  Details   │ │
│  │ (debug)  │ (thread) │ (thread) │  (room)  │  (thread)  │ │
│  └──────────┴──────────┴──────────┴──────────┴────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Scope Corrections (from v1)
- **Chat**: scoped to **thread** (not run) - conversation spans multiple runs
- **CurrentCanvas**: scoped to **thread** (not run)
- **PermanentCanvas**: persists across app restarts (unchanged)

## Backend Endpoints
```
GET  /api/v1/rooms                              - List rooms
GET  /api/v1/rooms/{room_id}/agui               - List threads
GET  /api/v1/rooms/{room_id}/agui/{thread_id}   - Thread info
POST /api/v1/rooms/{room_id}/agui               - Create thread
POST /api/v1/rooms/{room_id}/agui/{thread_id}   - Create run
POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}      - Execute run
POST /api/v1/rooms/{room_id}/agui/{thread_id}/meta          - Thread metadata
POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta - Run metadata
DELETE /api/v1/rooms/{room_id}/agui/{thread_id} - Delete thread
```

---

# PHASE 0: PROJECT SETUP

## 0.1 Initial App Scaffold
**Goal:** Bare minimum Flutter app with cross-platform support.

- Create Flutter app with all platforms enabled
- Minimal `main.dart` with placeholder home screen
- Verify builds on: iOS, Android, Web, macOS, Windows, Linux

## 0.2 Strict Linting Configuration
**File:** `analysis_options.yaml`

```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  errors:
    missing_return: error
    dead_code: warning
    unused_import: warning
    unused_local_variable: warning
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true

linter:
  rules:
    - always_declare_return_types
    - always_put_required_named_parameters_first
    - avoid_print
    - avoid_relative_lib_imports
    - avoid_returning_null_for_future
    - avoid_slow_async_io
    - avoid_type_to_string
    - cancel_subscriptions
    - close_sinks
    - prefer_final_locals
    - prefer_const_constructors
    - prefer_const_declarations
    - prefer_single_quotes
    - require_trailing_commas
    - sort_constructors_first
    - unawaited_futures
```

## 0.3 Testing Framework Setup
**Structure:**
```
test/
├── client/          # Pure Dart tests (dart test)
│   ├── models/
│   ├── agui/
│   ├── session/
│   └── api/
└── widget/          # Flutter widget tests (flutter test)

integration_test/    # Full app integration tests
```

**Commands:**
```bash
dart test test/client/       # Fast, no Flutter required
flutter test test/widget/    # Widget tests
flutter test integration_test/  # Integration tests
```

## 0.4 Dependencies Setup
**File:** `pubspec.yaml`

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.4.0
  http: ^1.1.0
  shared_preferences: ^2.2.0
  ag_ui:
    git:
      url: https://github.com/soliplex/ag-ui.git
      path: sdks/community/dart

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
  mocktail: ^1.0.0
  test: ^1.24.0  # For pure Dart client tests
```

**Deliverable:** App runs on all platforms, `flutter analyze` returns 0 issues, test structure in place.

---

# PHASE 1: CLIENT (Pure Dart)

**Constraint: NO Flutter imports. Only `dart:*`, `http`, `ag_ui`.**
**Test with:** `dart test test/client/`

## 1.1 Models & Utilities
**Files:** `lib/client/models/`, `lib/client/utils/`

| Component | Purpose |
|-----------|---------|
| `Room` | Room data model |
| `ThreadInfo` | Thread metadata |
| `RunInfo` | Run metadata |
| `ChatMessage` | Message with type (text/genui/error/tool) |
| `UrlBuilder` | URL construction, normalization |
| `HttpTransport` | HTTP client wrapper with headers |
| `CancelToken` | Cancellation support |

**Tests:** Unit tests for each model (serialization, copyWith), UrlBuilder edge cases.

## 1.2 AG-UI Protocol Layer
**Files:** `lib/client/agui/`

| Component | Purpose |
|-----------|---------|
| `TextMessageBuffer` | Accumulate streaming text chunks |
| `ToolCallReceptionBuffer` | Accumulate tool call arguments |
| `ToolCallRegistry` | Track tool call lifecycle, prevent re-execution |
| `Thread` | SSE processing, tool execution, message history |

**Critical patterns to implement:**
- Thinking buffering (thinking events may arrive before message)
- Fire-and-forget tools (execute but don't return result)
- Tool call deduplication

**Tests:** Unit tests for buffers, registry state transitions, mock SSE event sequences.

## 1.3 Session Management
**Files:** `lib/client/session/`

| Component | Purpose |
|-----------|---------|
| `RoomSession` | Per-room state, **owns messages** (source of truth), event processing |
| `ConnectionManager` | Singleton, server switching, session pool |

**RoomSession responsibilities:**
- `_messages: List<ChatMessage>` (authoritative)
- `messageStream` for UI subscription
- Event processing (TextMessage*, Thinking*, ToolCall*, State*, Run*)
- Deduplication sets

**ConnectionManager responsibilities:**
- `switchServer(url, headers)` - dispose all sessions
- `getSession(roomId)` - create or return existing
- `chat(roomId, message, ...)` - full conversation flow

**Tests:** Session lifecycle, server switching clears sessions, message stream emissions.

## 1.4 API Client
**Files:** `lib/client/api/`

| Component | Purpose |
|-----------|---------|
| `SoliplexApi` | HTTP methods for all endpoints |

**Methods:**
```dart
Future<List<Room>> getRooms()
Future<List<ThreadInfo>> getThreads(roomId)
Future<ThreadInfo> getThread(roomId, threadId)
Future<ThreadInfo> createThread(roomId)
Future<RunInfo> createRun(roomId, threadId)
Future<void> deleteThread(roomId, threadId)
Future<void> setThreadMeta(roomId, threadId, name, description)
Future<void> setRunMeta(roomId, threadId, runId, label)
```

**Tests:** Mock HTTP responses, error handling, auth header injection.

## 1.5 Client Integration
**Files:** `lib/client/soliplex_client.dart`

Single entry point exposing:
```dart
class SoliplexClient {
  final SoliplexApi api;
  final ConnectionManager connectionManager;

  void configure(String baseUrl, {Map<String, String>? headers});
  Future<void> chat(String roomId, String message, {OnEvent? onEvent});
  Stream<List<ChatMessage>> getMessageStream(String roomId);
  // ... delegate to api and connectionManager
}
```

**Tests:** Integration tests with mock server.

---

# PHASE 2: FRONTEND

## 2.0 State Management Setup
**Files:** `lib/providers/`

| Provider | Type | Scope |
|----------|------|-------|
| `soliplexClientProvider` | Provider | App |
| `currentRoomProvider` | StateProvider | App |
| `currentThreadProvider` | StateProvider | App |
| `roomsProvider` | FutureProvider | App |
| `threadsProvider` | FutureProvider | Room |
| `messagesProvider` | StreamProvider | Thread |
| `canvasStateProvider` | StateNotifierProvider | Thread |

**Tests:** Provider unit tests with ProviderContainer.

## 2.1 TestPage (Debug UI)
**Files:** `lib/features/test_page/`

Interactive debug page for manual client testing:

```
┌─────────────────────────────────────────────────────────┐
│ Server URL: [________________] [Connect]                │
├─────────────────────────────────────────────────────────┤
│ Endpoint Buttons:                                       │
│ [Get Rooms] [Get Threads] [Create Thread] [Delete]     │
│ [Create Run] [Execute Run] [Set Meta]                  │
├─────────────────────────────────────────────────────────┤
│ Request: (editable JSON)                                │
│ ┌─────────────────────────────────────────────────────┐│
│ │ {"room_id": "...", "message": "..."}                ││
│ └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│ Response / Events: (scrollable, live-updating)          │
│ ┌─────────────────────────────────────────────────────┐│
│ │ > GET /api/v1/rooms → 200                           ││
│ │ > [Room(id=...), Room(id=...)]                      ││
│ │ > SSE: TextMessageStart(...)                        ││
│ │ > SSE: TextMessageContent(delta="Hello")            ││
│ └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

**Tests:** Widget tests for button actions, response display.

## 2.2 History Widget
**Files:** `lib/features/history/`

- Displays thread list for current room
- Thread cards with name, timestamp, preview
- Create new thread button
- Delete thread (with confirmation)
- Tap to select thread

**Tests:** Widget tests with mock thread data.

## 2.3 Chat Widget
**Files:** `lib/features/chat/`

- Scoped to **thread** (shows all messages across runs)
- Streaming message display
- Thinking blocks (collapsible)
- Tool call indicators
- Input area with send button
- Cancel button during streaming

**Tests:** Widget tests for message rendering, streaming updates.

## 2.4 CurrentCanvas Widget
**Files:** `lib/features/canvas/`

- Displays StateSnapshot / ActivitySnapshot from AG-UI events
- Scoped to **thread**
- GenUI widget rendering (via WidgetRegistry)
- Auto-updates on state changes

**Tests:** Widget tests with mock state events.

## 2.5 PermanentCanvas Widget
**Files:** `lib/features/permanent_canvas/`

- User-pinned items from any thread/room
- Persists to local storage
- Add/remove items
- Survives app restart

**Tests:** Widget tests, persistence tests.

## 2.6 Details Widget
**Files:** `lib/features/details/`

- All events for selected thread
- Run list with labels
- Thinking content
- State history
- Tool call details

**Tests:** Widget tests with mock event data.

## 2.7 App Shell & Layout
**Files:** `lib/app_shell.dart`, `lib/features/layouts/`

```
┌─────────┬───────────────────────┬─────────────┐
│         │                       │  Details    │
│ History │       Canvas          │─────────────│
│  (1/4)  │  (Current/Permanent)  │    Chat     │
│         │                       │             │
└─────────┴───────────────────────┴─────────────┘
```

- Collapsible panels
- Tab switching for canvas
- Room selector in app bar
- Route: `/test` for TestPage

**Tests:** Layout widget tests, navigation tests.

---

# Development Standards

## Per-Phase Checklist

### Phase 0-1 (Client - Pure Dart)
- [ ] `flutter analyze` returns 0 issues
- [ ] `dart test test/client/` passes
- [ ] No Flutter imports in `lib/client/`
- [ ] Unit test coverage >= 80%
- [ ] `dart format .` applied

### Phase 2 (Frontend - Flutter)
- [ ] `flutter analyze` returns 0 issues
- [ ] `flutter test` passes (all tests)
- [ ] Unit test coverage >= 80%
- [ ] `dart format .` applied

## File Structure
```
lib/
├── client/                    # PURE DART - no Flutter imports
│   ├── models/
│   ├── utils/
│   ├── agui/
│   ├── session/
│   ├── api/
│   └── soliplex_client.dart
├── providers/                 # Riverpod providers (Flutter)
├── features/                  # Flutter UI
│   ├── test_page/
│   ├── history/
│   ├── chat/
│   ├── canvas/
│   ├── permanent_canvas/
│   ├── details/
│   └── layouts/
├── app_shell.dart
└── main.dart

test/
├── client/                    # Pure Dart tests (dart test)
│   ├── models/
│   ├── agui/
│   ├── session/
│   └── api/
└── widget/                    # Flutter widget tests

integration_test/              # Full app tests
```
