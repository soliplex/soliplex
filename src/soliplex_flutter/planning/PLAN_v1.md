# Soliplex Flutter Implementation Plan v1

## Summary
Build a cross-platform Flutter app with two components:
1. **Soliplex Client** - Dart library for HTTP/AGUI backend communication
2. **Soliplex Frontend** - Flutter UI with Chat, Canvas, History, and Details widgets

**Key Decisions:**
- State Management: Riverpod
- Platforms: Web, iOS, Android, macOS, Windows (all platforms)
- AGUI: Full custom implementation
- Persistence: Hive (pure Dart, cross-platform)
- Models: Freezed sealed classes with pattern matching
- Chat UI: Custom-built (no third-party chat library)
- Authentication: OIDC/OAuth2

---

## Client Implementation Phases (C1-C12)

### Phase C1: Project Setup & Dependencies
- Update `pubspec.yaml` with dependencies:
  - `flutter_riverpod`, `riverpod_annotation`
  - `dio` (HTTP client)
  - `freezed`, `freezed_annotation`, `json_annotation`
  - `hive`, `hive_flutter`
  - `flutter_secure_storage` (for tokens)
  - `go_router`
- Create directory structure
- Configure `build.yaml` for code generation
- Set up analysis_options.yaml with strict linting

### Phase C2: Core Domain Models
- Create `lib/client/models/room.dart`:
  - `Room` freezed class with id, name, config
- Create `lib/client/models/thread.dart`:
  - `Thread` freezed class with id, roomId, runs, metadata, created
  - `ThreadMetadata` with name, description
- Create `lib/client/models/run.dart`:
  - `Run` freezed class with id, threadId, parentRunId, events, metadata, created
  - `RunMetadata` with label

### Phase C3: Message & Content Models
- Create `lib/client/models/message.dart`:
  - `Message` sealed class with `UserMessage`, `AssistantMessage`, `SystemMessage`
  - `MessageContent` sealed class for text/image/audio/video
- Create `lib/client/models/tool_call.dart`:
  - `ToolCall` freezed class with id, name, arguments
  - `ToolResult` freezed class with callId, result, error

### Phase C4: AGUI Event Models (Freezed Sealed Classes)
- Create `lib/client/agui/events/base.dart`:
  - `AguiEvent` sealed base class
- Create `lib/client/agui/events/message_events.dart`:
  - `TextMessageStartEvent`, `TextMessageContentEvent`, `TextMessageEndEvent`
- Create `lib/client/agui/events/tool_events.dart`:
  - `ToolCallStartEvent`, `ToolCallArgsEvent`, `ToolCallEndEvent`
- Create `lib/client/agui/events/state_events.dart`:
  - `StateSnapshotEvent`, `StateDeltaEvent`
- Create `lib/client/agui/events/run_events.dart`:
  - `RunStartedEvent`, `RunFinishedEvent`, `RunErrorEvent`
- Create `lib/client/agui/events/thinking_events.dart`:
  - `ThinkingStartEvent`, `ThinkingContentEvent`, `ThinkingEndEvent`

### Phase C5: HTTP Client Foundation
- Create `lib/client/http/dio_client.dart`:
  - Base Dio instance with interceptors
  - Request/response logging
  - Error transformation
- Create `lib/client/http/config.dart`:
  - `SoliplexConfig` class with baseUrl, timeout settings
  - Default localhost:8000 configuration

### Phase C6: HTTP Endpoints - Rooms
- Create `lib/client/http/endpoints/rooms.dart`:
  - `GET /v1/rooms` - listRooms()
  - Response parsing to `List<Room>`
- Create `lib/client/http/exceptions.dart`:
  - `SoliplexException` base
  - `NetworkException`, `ApiException`, `AuthException`

### Phase C7: HTTP Endpoints - Threads
- Create `lib/client/http/endpoints/threads.dart`:
  - `GET /api/v1/rooms/{room_id}/agui` - listThreads(roomId)
  - `POST /api/v1/rooms/{room_id}/agui` - createThread(roomId)
  - `GET /api/v1/rooms/{room_id}/agui/{thread_id}` - getThread(roomId, threadId)
  - `DELETE /api/v1/rooms/{room_id}/agui/{thread_id}` - deleteThread(roomId, threadId)
  - `POST .../meta` - updateThreadMeta(roomId, threadId, metadata)

### Phase C8: HTTP Endpoints - Runs
- Create `lib/client/http/endpoints/runs.dart`:
  - `GET .../agui/{thread_id}/{run_id}` - getRun()
  - `POST .../agui/{thread_id}` - createRun(threadId)
  - `POST .../agui/{thread_id}/{run_id}` - executeRun() (returns Stream)
  - `POST .../agui/{thread_id}/{run_id}/meta` - updateRunMeta()

### Phase C9: SSE Stream Handler
- Create `lib/client/agui/sse/sse_client.dart`:
  - SSE connection management
  - Reconnection logic with exponential backoff
  - Event stream parsing (line-by-line)
- Create `lib/client/agui/sse/event_parser.dart`:
  - JSON → AguiEvent deserialization
  - Unknown event type handling

### Phase C10: Message Buffering System
- Create `lib/client/agui/buffers/text_message_buffer.dart`:
  - Accumulate streaming text chunks by messageId
  - Return complete message content
- Create `lib/client/agui/buffers/tool_call_buffer.dart`:
  - Accumulate tool call arguments
  - Track tool name and id
- Create `lib/client/agui/buffers/thinking_buffer.dart`:
  - Handle out-of-order thinking events
  - Buffer until thinking complete

### Phase C11: Tool Call Registry & Execution
- Create `lib/client/tools/tool_registry.dart`:
  - Register pending tool calls
  - Mark completed with results
  - Track lifecycle states: pending → executing → completed/failed
- Create `lib/client/tools/tool_definition.dart`:
  - `LocalToolDefinition` interface
  - Execute method signature
- Create `lib/client/tools/fire_and_forget.dart`:
  - Special handling for UI tools (canvas_render, genui_render)
  - No result submission for these tools

### Phase C12: OIDC Authentication
- Create `lib/client/auth/oidc_config.dart`:
  - OIDC provider configuration (issuer, clientId, scopes)
- Create `lib/client/auth/token_storage.dart`:
  - Secure storage for access/refresh tokens
  - Token expiry tracking
- Create `lib/client/auth/auth_service.dart`:
  - Login flow (authorization code + PKCE)
  - Token refresh logic
  - Logout and token revocation
- Create `lib/client/http/auth_interceptor.dart`:
  - Dio interceptor to attach Bearer token
  - Auto-refresh on 401

---

## Riverpod State Management Phases (S1-S4)

### Phase S1: Client Providers
- Create `lib/shared/providers/config_provider.dart`:
  - `configProvider` - app configuration
- Create `lib/shared/providers/http_client_provider.dart`:
  - `dioProvider` - singleton Dio instance
  - `soliplexClientProvider` - HTTP client facade

### Phase S2: Auth Providers
- Create `lib/shared/providers/auth_providers.dart`:
  - `authServiceProvider` - OIDC auth service
  - `authStateProvider` - current auth state (logged in/out)
  - `currentUserProvider` - user info from token

### Phase S3: Data Providers
- Create `lib/shared/providers/room_providers.dart`:
  - `roomsProvider` - async list of rooms
  - `selectedRoomProvider` - currently selected room
- Create `lib/shared/providers/thread_providers.dart`:
  - `threadsProvider(roomId)` - family provider
  - `selectedThreadProvider` - current thread
- Create `lib/shared/providers/run_providers.dart`:
  - `runsProvider(threadId)` - family provider
  - `selectedRunProvider` - current run
  - `activeRunStreamProvider` - SSE event stream

### Phase S4: UI State Providers
- Create `lib/shared/providers/ui_state_providers.dart`:
  - `messagesProvider` - messages for current run
  - `canvasStateProvider` - current canvas state
  - `thinkingProvider` - current thinking content
  - `toolCallsProvider` - active tool calls

---

## Frontend Implementation Phases (F1-F12)

### Phase F1: App Bootstrap & Theme
- Update `lib/main.dart`:
  - ProviderScope wrapper
  - Hive initialization
- Create `lib/frontend/app.dart`:
  - MaterialApp.router setup
  - Theme configuration
- Create `lib/frontend/theme/app_theme.dart`:
  - Light and dark themes
  - Color scheme, typography

### Phase F2: Router & Navigation
- Create `lib/frontend/routing/router.dart`:
  - GoRouter configuration
  - Routes: /, /room/:roomId, /room/:roomId/thread/:threadId
- Create `lib/frontend/routing/guards.dart`:
  - Auth guard (redirect to login if unauthenticated)

### Phase F3: Login Screen
- Create `lib/frontend/screens/login_screen.dart`:
  - OIDC login button
  - Loading state during auth flow
  - Error display

### Phase F4: Main Layout Shell
- Create `lib/frontend/layouts/main_layout.dart`:
  - 3-panel responsive layout
  - Left: History (1/4, collapsible)
  - Center: Canvas (flexible)
  - Right: Details + Chat (collapsible, vertical split)
- Create `lib/frontend/layouts/responsive_breakpoints.dart`:
  - Breakpoint definitions for mobile/tablet/desktop

### Phase F5: Room Selector
- Create `lib/frontend/widgets/room_selector/room_selector.dart`:
  - Dropdown or drawer for room selection
  - Room list from roomsProvider
  - Updates selectedRoomProvider on selection

### Phase F6: History Widget - Thread List
- Create `lib/frontend/widgets/history/history_panel.dart`:
  - Container with collapse toggle
- Create `lib/frontend/widgets/history/thread_list.dart`:
  - List of threads for current room
  - Thread item with name, date, preview
- Create `lib/frontend/widgets/history/thread_list_item.dart`:
  - Single thread display
  - Tap to select, long-press for options

### Phase F7: History Widget - Thread Actions
- Create `lib/frontend/widgets/history/new_thread_button.dart`:
  - FAB or button to create new thread
- Create `lib/frontend/widgets/history/thread_actions_menu.dart`:
  - Rename, delete options
  - Confirmation dialogs

### Phase F8: Chat Widget - Message Display
- Create `lib/frontend/widgets/chat/chat_panel.dart`:
  - Container for chat UI
- Create `lib/frontend/widgets/chat/message_list.dart`:
  - Scrollable, reverse list of messages
  - Auto-scroll on new messages
- Create `lib/frontend/widgets/chat/message_bubble.dart`:
  - User vs assistant styling
  - Timestamp display

### Phase F9: Chat Widget - Input & Streaming
- Create `lib/frontend/widgets/chat/chat_input.dart`:
  - Text field with send button
  - Multiline support
  - Send on enter (configurable)
- Create `lib/frontend/widgets/chat/streaming_indicator.dart`:
  - Typing indicator during streaming
  - Partial message display
- Create `lib/frontend/widgets/chat/tool_call_chip.dart`:
  - Inline display of tool calls
  - Pending/completed states

### Phase F10: Canvas Widget - CurrentCanvas
- Create `lib/frontend/widgets/canvas/canvas_panel.dart`:
  - Tab bar for Current/Permanent
- Create `lib/frontend/widgets/canvas/current_canvas.dart`:
  - Render StateSnapshot events
  - Render ActivitySnapshot events
  - Real-time updates from stream
- Create `lib/frontend/widgets/canvas/canvas_item.dart`:
  - Generic item renderer
  - Save to permanent button

### Phase F11: Canvas Widget - PermanentCanvas
- Create `lib/frontend/widgets/canvas/permanent_canvas.dart`:
  - Items from Hive storage
  - Add/remove functionality
- Create `lib/shared/persistence/hive_service.dart`:
  - Hive box for permanent items
  - CRUD operations
- Create `lib/shared/persistence/canvas_item_adapter.dart`:
  - Hive TypeAdapter for canvas items

### Phase F12: Details Widget
- Create `lib/frontend/widgets/details/details_panel.dart`:
  - Vertical split container
- Create `lib/frontend/widgets/details/run_list.dart`:
  - List of runs in current thread
  - Run selection
- Create `lib/frontend/widgets/details/event_timeline.dart`:
  - Chronological event display
  - Expandable thinking sections
- Create `lib/frontend/widgets/details/state_inspector.dart`:
  - JSON tree view of current state

---

## Platform & Polish Phases (P1-P4)

### Phase P1: Platform Abstractions
- Create `lib/platform/sse_handler_stub.dart`:
  - Conditional export
- Create `lib/platform/sse_handler_io.dart`:
  - Native SSE implementation (dart:io HttpClient)
- Create `lib/platform/sse_handler_web.dart`:
  - Web SSE implementation (dart:html EventSource)

### Phase P2: Error Handling & Loading States
- Create `lib/frontend/widgets/common/error_display.dart`:
  - Consistent error presentation
  - Retry buttons
- Create `lib/frontend/widgets/common/loading_indicator.dart`:
  - Shimmer/skeleton loading
  - Full-screen loading overlay

### Phase P3: Unit Tests - Client Layer
- Create `test/client/models/` - model serialization tests
- Create `test/client/http/` - endpoint tests with mocked Dio
- Create `test/client/agui/` - event parsing, buffer tests
- Create `test/client/auth/` - auth flow tests
- Target: 80%+ coverage

### Phase P4: Widget Tests - Frontend
- Create `test/frontend/widgets/` - widget tests
- Create `test/frontend/integration/` - flow tests
- Create `test/shared/providers/` - provider tests

---

## Directory Structure

```
lib/
├── main.dart
├── client/
│   ├── auth/
│   │   ├── oidc_config.dart
│   │   ├── token_storage.dart
│   │   └── auth_service.dart
│   ├── http/
│   │   ├── dio_client.dart
│   │   ├── config.dart
│   │   ├── exceptions.dart
│   │   ├── auth_interceptor.dart
│   │   └── endpoints/
│   │       ├── rooms.dart
│   │       ├── threads.dart
│   │       └── runs.dart
│   ├── agui/
│   │   ├── events/
│   │   │   ├── base.dart
│   │   │   ├── message_events.dart
│   │   │   ├── tool_events.dart
│   │   │   ├── state_events.dart
│   │   │   ├── run_events.dart
│   │   │   └── thinking_events.dart
│   │   ├── sse/
│   │   │   ├── sse_client.dart
│   │   │   └── event_parser.dart
│   │   └── buffers/
│   │       ├── text_message_buffer.dart
│   │       ├── tool_call_buffer.dart
│   │       └── thinking_buffer.dart
│   ├── models/
│   │   ├── room.dart
│   │   ├── thread.dart
│   │   ├── run.dart
│   │   ├── message.dart
│   │   └── tool_call.dart
│   └── tools/
│       ├── tool_definition.dart
│       ├── tool_registry.dart
│       └── fire_and_forget.dart
├── frontend/
│   ├── app.dart
│   ├── routing/
│   │   ├── router.dart
│   │   └── guards.dart
│   ├── screens/
│   │   └── login_screen.dart
│   ├── layouts/
│   │   ├── main_layout.dart
│   │   └── responsive_breakpoints.dart
│   ├── widgets/
│   │   ├── room_selector/
│   │   │   └── room_selector.dart
│   │   ├── history/
│   │   │   ├── history_panel.dart
│   │   │   ├── thread_list.dart
│   │   │   ├── thread_list_item.dart
│   │   │   ├── new_thread_button.dart
│   │   │   └── thread_actions_menu.dart
│   │   ├── chat/
│   │   │   ├── chat_panel.dart
│   │   │   ├── message_list.dart
│   │   │   ├── message_bubble.dart
│   │   │   ├── chat_input.dart
│   │   │   ├── streaming_indicator.dart
│   │   │   └── tool_call_chip.dart
│   │   ├── canvas/
│   │   │   ├── canvas_panel.dart
│   │   │   ├── current_canvas.dart
│   │   │   ├── permanent_canvas.dart
│   │   │   └── canvas_item.dart
│   │   ├── details/
│   │   │   ├── details_panel.dart
│   │   │   ├── run_list.dart
│   │   │   ├── event_timeline.dart
│   │   │   └── state_inspector.dart
│   │   └── common/
│   │       ├── error_display.dart
│   │       └── loading_indicator.dart
│   └── theme/
│       └── app_theme.dart
├── shared/
│   ├── providers/
│   │   ├── config_provider.dart
│   │   ├── http_client_provider.dart
│   │   ├── auth_providers.dart
│   │   ├── room_providers.dart
│   │   ├── thread_providers.dart
│   │   ├── run_providers.dart
│   │   └── ui_state_providers.dart
│   └── persistence/
│       ├── hive_service.dart
│       └── canvas_item_adapter.dart
└── platform/
    ├── sse_handler_stub.dart
    ├── sse_handler_io.dart
    └── sse_handler_web.dart
```

---

## Phase Summary (32 total phases)

| Category | Phases | Description |
|----------|--------|-------------|
| Client Setup | C1-C3 | Project setup, domain models |
| AGUI Events | C4 | Freezed sealed event classes |
| HTTP Layer | C5-C8 | Dio client, all endpoints |
| SSE/Streaming | C9-C10 | SSE handler, buffers |
| Tools | C11 | Tool registry and execution |
| Auth | C12 | OIDC authentication |
| Providers | S1-S4 | Riverpod state management |
| Frontend Core | F1-F4 | App shell, routing, layout |
| History | F5-F7 | Room selector, thread list |
| Chat | F8-F9 | Messages, input, streaming |
| Canvas | F10-F11 | Current + Permanent canvas |
| Details | F12 | Run list, event timeline |
| Platform | P1 | Web/native abstractions |
| Polish | P2-P4 | Error handling, tests |

---

## Critical Files (in build order)

1. `pubspec.yaml` - dependencies
2. `lib/client/models/*.dart` - domain models
3. `lib/client/agui/events/*.dart` - AGUI event types
4. `lib/client/http/dio_client.dart` - HTTP foundation
5. `lib/client/http/endpoints/*.dart` - API endpoints
6. `lib/client/agui/sse/sse_client.dart` - SSE streaming
7. `lib/client/auth/auth_service.dart` - OIDC auth
8. `lib/shared/providers/*.dart` - state management
9. `lib/frontend/layouts/main_layout.dart` - app shell
10. `lib/frontend/widgets/chat/chat_panel.dart` - core chat
11. `lib/frontend/widgets/canvas/current_canvas.dart` - canvas
