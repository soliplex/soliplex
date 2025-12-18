# Soliplex Frontend Codebase Analysis

**Generated:** 2025-12-17
**Branch:** new_frontend
**Current Milestone:** AM3 (Working Chat) ✅

## 1. Project Structure

```text
frontend/
├── lib/                              # Main Flutter app (29 Dart files)
│   ├── main.dart                     # Entry point with ProviderScope
│   ├── app.dart                      # Root SoliplexApp widget
│   ├── core/                         # Infrastructure layer
│   │   ├── models/                   # Core data models
│   │   │   ├── active_run_state.dart # AG-UI streaming state
│   │   │   └── app_config.dart       # App configuration (baseUrl, version)
│   │   ├── providers/                # Riverpod state management (7 providers)
│   │   │   ├── api_provider.dart     # SoliplexApi singleton
│   │   │   ├── active_run_provider.dart
│   │   │   ├── active_run_notifier.dart
│   │   │   ├── config_provider.dart
│   │   │   ├── rooms_provider.dart
│   │   │   ├── threads_provider.dart
│   │   │   └── backend_health_provider.dart
│   │   └── router/
│   │       └── app_router.dart       # GoRouter (5 routes)
│   ├── features/                     # Feature screens
│   │   ├── home/                     # Welcome screen
│   │   ├── rooms/                    # Room list
│   │   ├── room/                     # Threads in room
│   │   ├── thread/                   # Main chat (dual panel desktop)
│   │   ├── chat/                     # Chat messaging
│   │   ├── history/                  # Thread list sidebar
│   │   ├── login/                    # Placeholder (AM7)
│   │   └── settings/                 # Settings screen
│   └── shared/                       # Reusable components
│       ├── widgets/
│       └── utils/
│
├── packages/soliplex_client/         # Pure Dart package (NO Flutter)
│   ├── lib/src/
│   │   ├── models/                   # Data models
│   │   ├── errors/                   # Exception hierarchy
│   │   ├── api/                      # REST API client
│   │   ├── http/                     # HTTP abstraction layer
│   │   ├── agui/                     # AG-UI protocol
│   │   └── utils/                    # Utilities
│   └── test/                         # 587 tests, 100% coverage
│
├── packages/soliplex_client_native/  # Flutter package - Native HTTP
│   └── lib/src/adapters/
│       └── cupertino_http_adapter.dart  # NSURLSession for iOS/macOS
│
├── test/                             # Integration and widget tests
├── android/, ios/, macos/, web/      # Platform-specific code
└── pubspec.yaml
```

## 2. Architecture

### 2.1 Three-Layer Design

```text
┌─────────────────────────────────────────────┐
│              UI Components                   │
│  (Chat, History, Detail, Canvas)            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Core Frontend                   │
│  Providers │ Navigation │ AG-UI Processing  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│      soliplex_client (Pure Dart package)    │
└─────────────────────────────────────────────┘
```

### 2.2 State Management: Riverpod

**Provider Hierarchy:**

```text
configProvider (StateProvider)
    │
    ├── urlBuilderProvider
    └── httpTransportProvider
            │
        apiProvider
            │
    ┌───────┴────────┐
    │                │
roomsProvider  threadsProvider(roomId)
    │                │
    └────┬───────────┘
         │
currentRoomIdProvider / currentThreadIdProvider
         │
activeRunNotifierProvider ← Main streaming orchestration
         │
Derived: canSendMessageProvider, allMessagesProvider, isStreamingProvider
```

### 2.3 HTTP Layer Architecture

```text
┌────────────────────────────────────────────────┐
│         SoliplexApi (REST client)              │  Layer 3: Business Logic
└───────────────┬────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────┐
│      HttpTransport (JSON + Error Mapping)      │  Layer 2: Transport
└───────────────┬────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────┐
│   HttpClientAdapter (Platform abstractions)    │  Layer 1: Adapters
│  - DartHttpAdapter (dart:http)                 │
│  - CupertinoHttpAdapter (NSURLSession)         │
└────────────────────────────────────────────────┘
```

### 2.4 Navigation: GoRouter

| Route | Screen | Description |
|-------|--------|-------------|
| `/` | HomeScreen | Welcome page |
| `/rooms` | RoomsScreen | List all rooms |
| `/rooms/:roomId` | RoomScreen | Threads in room |
| `/rooms/:roomId/thread/:threadId` | ThreadScreen | Chat interface |
| `/settings` | SettingsScreen | Backend config |

**Responsive Layout:**

- Desktop (≥600px): Sidebar history panel + chat panel side-by-side
- Mobile (<600px): Chat panel only

## 3. Key Components

### 3.1 Data Models

**ChatMessage:**

```dart
- id: String
- user: ChatUser (user | assistant | system)
- type: MessageType (text | error | toolCall | genUi | loading)
- text: String?
- isStreaming: bool
- thinkingText: String?
- toolCalls: List<ToolCallInfo>?
- errorMessage: String?
- createdAt: DateTime
```

**ActiveRunState:**

```dart
- status: ThreadRunStatus (idle | running | finished | error)
- messages: List<ChatMessage>
- threadId: String?
- runId: String?
- streamingText: String?
- isTextStreaming: bool
- activeToolCalls: List<ToolCallInfo>
- state: Map<String, dynamic>
- rawEvents: List<AgUiEvent>
```

### 3.2 AG-UI Protocol

**Event Types (sealed class hierarchy):**

- Run lifecycle: `RunStartedEvent`, `RunFinishedEvent`, `RunErrorEvent`
- Message streaming: `TextMessageStartEvent`, `TextMessageContentEvent`, `TextMessageEndEvent`
- Tool calls: `ToolCallStartEvent`, `ToolCallArgsEvent`, `ToolCallEndEvent`, `ToolCallResultEvent`
- State: `StateSnapshotEvent`, `StateDeltaEvent`
- Activity: `ActivitySnapshotEvent`, `ActivityDeltaEvent`
- Messages: `MessagesSnapshotEvent`
- Custom: `CustomEvent`, `UnknownEvent`

**Streaming Pipeline:**

```text
SSE Stream → Thread.run() → Event parsing → Buffers → ActiveRunNotifier → UI
```

### 3.3 Chat Flow

```text
User types message
    ↓
ChatInput.onSend(text)
    ↓
ChatPanel._handleSend()
    ├─ Create thread if needed (api.createThread)
    └─ activeRunNotifier.startRun(roomId, threadId, userMessage)
         ├─ Creates Thread
         ├─ Subscribes to eventStream
         └─ Updates ActiveRunState
    ↓
MessageList watches allMessagesProvider
    ├─ Merges history + run messages
    └─ Auto-scrolls to bottom
```

## 4. soliplex_client Package

**Pure Dart** - no Flutter dependency. Reusable on web, server, or desktop.

| Milestone | Description | Status |
|-----------|-------------|--------|
| DM1 | Models & errors | ✅ |
| DM2 | HTTP adapter interface + DartHttpAdapter | ✅ |
| DM3 | HttpObserver + ObservableHttpAdapter | ✅ |
| DM4 | HttpTransport, UrlBuilder, CancelToken | ✅ |
| DM5 | API layer (SoliplexApi) | ✅ |
| DM6 | AG-UI protocol (Thread, buffers, tool registry) | ✅ |
| DM7 | Sessions (ConnectionManager, RoomSession) | Not Started |
| DM8 | Facade (SoliplexClient) | Not Started |

**Test Coverage:** 587 tests, 100% coverage

## 5. UI Components

### Screens

| Screen | Purpose |
|--------|---------|
| HomeScreen | Welcome with navigation |
| RoomsScreen | List rooms from API |
| RoomScreen | List threads, create new |
| ThreadScreen | Main chat interface |
| SettingsScreen | Backend configuration |

### Panels

| Panel | Purpose |
|-------|---------|
| ChatPanel | Message list + input, send/cancel/error handling |
| HistoryPanel | Thread list, new conversation, auto-selection |

### Shared Widgets

- `AsyncValueHandler`: Wraps AsyncValue with error handling
- `ErrorDisplay`: Exception-aware error UI with retry
- `LoadingIndicator`: Spinner with optional message
- `EmptyState`: Icon + message for empty lists

## 6. Testing

**Test Coverage:**

- Frontend: 129 tests total
- soliplex_client: 587 tests, 100% coverage
- Zero analyzer issues

**Test Structure:**

```text
test/
├── core/providers/        # Provider tests
├── features/              # Screen and widget tests
├── shared/                # Shared widget tests
└── helpers/               # Mocks and utilities
```

**Key Utilities:**

- `MockSoliplexApi`: Mock API for testing
- `MockActiveRunNotifier`: Mock notifier with initial state
- `createTestApp()`: Helper to create testable app

## 7. Code Quality

**Analyzer:** Zero tolerance - no errors, warnings, or hints

**Linting:**

- `very_good_analysis` (strict rules)
- `dart format lib test` before commits
- `markdownlint-cli` for markdown

**Conventions:**

- PascalCase: Classes, enums, types
- camelCase: Variables, functions
- `_privateMethod`: Private members prefixed

## 8. Notable Patterns

### Sealed Classes for Events

```dart
sealed class AgUiEvent { ... }
final class RunStartedEvent extends AgUiEvent { ... }
// Enables exhaustive pattern matching
```

### Builder Pattern for Models

```dart
ChatMessage.text(...)
ChatMessage.error(...)
ChatMessage.toolCall(...)
```

### Observer Pattern for HTTP

`ObservableHttpAdapter` wraps adapters for request inspection/logging.

### Cancel Token

Graceful SSE stream cancellation via `Completer` pattern.

### Responsive Breakpoint

600px mobile/desktop boundary in ThreadScreen.

## 9. Dependencies

**Frontend App:**

```yaml
flutter_riverpod: ^2.6.1    # State management
go_router: ^14.7.1          # Navigation
http: ^1.2.0                # Health checks
intl: ^0.20.1               # Localization
meta: ^1.15.0               # Annotations
soliplex_client: path       # Pure Dart client
soliplex_client_native: path # Native adapters
```

**soliplex_client:**

```yaml
http: ^1.2.0
meta: ^1.9.0
```

**soliplex_client_native:**

```yaml
cupertino_http: ^2.0.0      # NSURLSession
flutter: >= 3.10.0
http: ^1.2.0
```

## 10. Milestone Progress

| Milestone | Description | Status |
|-----------|-------------|--------|
| AM1 | App shell, navigation | ✅ |
| AM2 | Real API integration | ✅ |
| AM3 | Working chat with streaming | ✅ |
| AM4 | Message history and persistence | Pending |
| AM5 | Detail panel (events, thinking, tools) | Pending |
| AM6 | Canvas components | Pending |
| AM7 | Authentication UI | Pending |
| AM8 | Multi-room package extraction | Pending |

## 11. Key Architectural Decisions

1. **Pure Dart client package** - Reusable across platforms without Flutter dependency
2. **Sealed classes for events** - Type-safe exhaustive pattern matching
3. **3-layer HTTP abstraction** - Testable adapters, transport, and API layers
4. **Platform-optimized adapters** - NSURLSession on iOS/macOS for better performance
5. **Manual Riverpod providers** - Explicit control over provider lifecycle
6. **Responsive dual-panel layout** - Desktop sidebar with mobile fallback

## 12. Summary

This is a well-architected, production-quality Flutter frontend featuring:

- ✅ Clean 3-layer HTTP abstraction with platform adapters
- ✅ Pure Dart client package reusable across platforms
- ✅ Sophisticated AG-UI event streaming protocol
- ✅ Responsive dual-panel desktop + mobile chat
- ✅ Comprehensive error handling with exception hierarchy
- ✅ Strict code quality (zero analyzer issues, 100% test coverage on client)
- ✅ Riverpod state management with clear provider hierarchy
- ✅ Sealed classes for type-safe event handling
- ✅ Platform-optimized native HTTP adapters
