# Core Frontend

Flutter infrastructure that uses the `client` component for backend interactions and provides plumbing for UI components.

## Responsibilities

- User authentication (login/logout)
- Backend URL configuration
- Navigation between screens
- State management (Riverpod)
- AG-UI event processing
- Client-side tool calls (extensible)

## Technology Stack

| Category | Technology |
|----------|------------|
| State Management | Riverpod |
| Routing | go_router |
| Secure Storage | flutter_secure_storage |

### Target Platforms

- **Web** (primary)
- **Mobile** (iOS, Android)
- **Desktop** (macOS, Windows, Linux)

## Architecture

```
┌─────────────────────────────────────────────┐
│              UI Components                   │
│  (Chat, History, Detail, Canvas)            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Core Frontend                   │
│  Providers │ Navigation │ AG-UI Processor   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Client (Pure Dart)              │
└──────────────────────────────────────────────┘
```

## State Management

### Providers

```dart
// Config
final configProvider = StateProvider<AppConfig>((ref) => AppConfig.defaults());

// Token storage
final tokenStorageProvider = Provider<TokenStorage>((ref) => SecureTokenStorage());

// Client
final clientProvider = Provider<SoliplexClient>((ref) {
  final config = ref.watch(configProvider);
  final tokenStorage = ref.watch(tokenStorageProvider);
  return SoliplexClient(baseUrl: config.backendUrl, tokenStorage: tokenStorage);
});

// Auth
final authStateProvider = StateProvider<AuthState>((ref) => AuthState.initial());
final userProvider = FutureProvider<UserProfile?>((ref) async {
  final auth = ref.watch(authStateProvider);
  if (!auth.isLoggedIn) return null;
  return ref.watch(clientProvider).getUserInfo();
});

// Rooms & Threads
final roomsProvider = FutureProvider((ref) => ref.watch(clientProvider).getRooms());
final currentRoomProvider = StateProvider<Room?>((ref) => null);
final threadsProvider = FutureProvider((ref) {
  final room = ref.watch(currentRoomProvider);
  if (room == null) return <Thread>[];
  return ref.watch(clientProvider).getThreads(room.id);
});
final currentThreadProvider = StateProvider<Thread?>((ref) => null);

// New thread intent (signals user wants to start a new conversation)
// Set to true by History "New Conversation" button, cleared on thread selection or send
final newThreadIntentProvider = StateProvider<bool>((ref) => false);

// Thread message history (loaded when switching threads)
final threadMessagesProvider = FutureProvider.family<List<Message>, String>((ref, threadId) async {
  // Load message history from backend for the given thread
  // Returns empty list for new threads
});

// Last thread storage (persists last used thread per room)
final lastThreadStorageProvider = Provider((ref) => LastThreadStorage());

// Auto-select last used thread when room changes
final autoSelectedThreadProvider = FutureProvider<Thread?>((ref) async {
  final room = ref.watch(currentRoomProvider);
  if (room == null) return null;

  final storage = ref.watch(lastThreadStorageProvider);
  final lastThreadId = await storage.getLastThread(room.id);
  if (lastThreadId == null) return null;

  // Find thread in the list
  final threads = await ref.watch(threadsProvider.future);
  return threads.firstWhereOrNull((t) => t.id == lastThreadId);
});

// Active run (AG-UI events)
final activeRunProvider = StateNotifierProvider<ActiveRunNotifier, ActiveRunState>(
  (ref) => ActiveRunNotifier(ref.watch(clientProvider)),
);
```

### Key State Classes

```dart
class AppConfig {
  final String backendUrl;
  AppConfig({this.backendUrl = 'http://localhost:8000'});
}

class AuthState {
  final bool isLoggedIn;
  final bool isLoading;
  final String? error;
}

class Message {
  final String id;
  final String role;             // 'user', 'assistant', 'tool', 'system'
  final String content;
  final MessageType type;        // text, image, audio, video, file
  final bool isStreaming;        // true while content is being appended
  final Map<String, dynamic>? metadata;  // media URLs, dimensions, tool info, etc.
}

enum MessageType { text, image, audio, video, file }

class ActiveRunState {
  final String? threadId;        // Thread for current run
  final RunStatus status;        // idle, running, finished, error
  final List<Message> messages;  // messages for current run (merged with history in UI)
  final String? activity;        // "Thinking...", "Calling tool..."
  final String? error;
}

enum RunStatus { idle, running, finished, error }

class LastThreadStorage {
  static const _key = 'last_thread_per_room';

  Future<String?> getLastThread(String roomId);
  Future<void> setLastThread(String roomId, String threadId);
  Future<void> clear(String roomId);
}
```

## Authentication

The backend uses **server-mediated OIDC** - the server handles redirects to the identity provider and returns a token. This works for all platforms using a webview.

### Flow

1. App opens webview to `{baseUrl}/api/login/{provider}`
2. Server redirects to OIDC provider
3. After auth, server redirects to callback with token
4. App captures token from callback URL, stores it

```dart
class AuthService {
  Future<void> login(String provider) async {
    // Open webview to auth URL
    final authUrl = '${client.baseUrl}/api/login/$provider';
    final callbackUrl = await openAuthWebview(authUrl);

    // Extract token from callback
    final token = Uri.parse(callbackUrl).queryParameters['token'];
    if (token != null) {
      await tokenStorage.setToken(token);
    }
  }

  Future<void> logout() async {
    await tokenStorage.clearToken();
  }
}
```

### Platform Notes

| Platform | Implementation |
|----------|----------------|
| Web | Full page redirect, capture token from URL on return |
| Mobile/Desktop | In-app webview (flutter_inappwebview or url_launcher) |

## Navigation

### Routes

```dart
final router = GoRouter(
  initialLocation: '/login',
  redirect: (context, state) {
    final isLoggedIn = /* check auth state */;
    if (!isLoggedIn && state.matchedLocation != '/login') return '/login';
    if (isLoggedIn && state.matchedLocation == '/login') return '/rooms';
    return null;
  },
  routes: [
    GoRoute(path: '/login', builder: (_, __) => LoginScreen()),
    GoRoute(path: '/settings', builder: (_, __) => SettingsScreen()),
    ShellRoute(
      builder: (_, __, child) => MainShell(child: child),
      routes: [
        GoRoute(path: '/rooms', builder: (_, __) => RoomListScreen()),
        GoRoute(
          path: '/rooms/:roomId',
          builder: (_, state) => RoomScreen(roomId: state.pathParameters['roomId']!),
          routes: [
            GoRoute(
              path: 'thread/:threadId',
              builder: (_, state) => ThreadScreen(
                roomId: state.pathParameters['roomId']!,
                threadId: state.pathParameters['threadId']!,
              ),
            ),
          ],
        ),
      ],
    ),
  ],
);
```

## AG-UI Event Processing

The `ActiveRunNotifier` transforms the AG-UI event stream into UI-friendly state.

### ActiveRunNotifier Methods

```dart
class ActiveRunNotifier extends StateNotifier<ActiveRunState> {
  /// Send a message and start a new run
  /// Creates thread if threadId is null (only valid when room has no threads)
  /// Returns the thread (newly created or existing)
  Future<Thread> sendMessage(String roomId, String? threadId, String content);

  /// Cancel the current run
  void cancel();

  /// Reset state (when switching threads)
  void reset();
}
```

### Event Handling

| Event | Action |
|-------|--------|
| `RUN_STARTED` | Set status to running |
| `TEXT_MESSAGE_START` | Add new message to list (isStreaming: true) |
| `TEXT_MESSAGE_CONTENT` | Append content to current message |
| `TEXT_MESSAGE_END` | Mark message complete (isStreaming: false) |
| `TOOL_CALL_START` | Set activity to "Calling {tool}..." |
| `TOOL_CALL_RESULT` | Clear activity, check for client tools |
| `ACTIVITY_SNAPSHOT` | Update activity display |
| `RUN_FINISHED` | Set status to finished |
| `RUN_ERROR` | Set status to error with message |

### Client Tool Calls

When the agent requests a client-side tool (e.g., file upload, camera), the frontend executes it locally and sends results back via a new run.

```dart
abstract class ClientToolHandler {
  String get toolName;
  Future<ToolResult> execute(Map<String, dynamic> args);
}

class ClientToolRegistry {
  void register(ClientToolHandler handler);
  bool canHandle(String toolName);
  Future<ToolResult> execute(String toolName, Map<String, dynamic> args);
}
```

Built-in handlers will be implemented as needed (file picker, camera, location).

## Thread Auto-Selection

When user enters a room, auto-select the thread they last interacted with.

### Flow

1. **User selects room** → `currentRoomProvider` updates
2. **`autoSelectedThreadProvider`** watches room changes, loads last thread ID from `LastThreadStorage`
3. **If found** → UI sets `currentThreadProvider` to that thread
4. **When user sends message** → update `LastThreadStorage` with current thread ID

### Storage

`LastThreadStorage` persists `Map<roomId, threadId>` in SharedPreferences. Implementation details:

- Store as JSON string in SharedPreferences
- Load on app start, cache in memory
- Update on each message send

### UI Integration

The history/thread list component should watch `autoSelectedThreadProvider` and set `currentThreadProvider` when a thread is auto-selected:

```dart
ref.listen(autoSelectedThreadProvider, (_, next) {
  final thread = next.valueOrNull;
  if (thread != null) {
    ref.read(currentThreadProvider.notifier).state = thread;
  }
});
```

## Error Handling

Map client exceptions to user-friendly messages:

| Exception | User Message | Action |
|-----------|--------------|--------|
| `AuthException` | "Please log in again" | Redirect to login |
| `NetworkException` | "Check your connection" | Show retry |
| `NotFoundException` | "Not found" | Go back |
| `ApiException` | "Something went wrong" | Show retry |

## Configuration

Settings screen provides:
- Backend URL input with validation
- Logout button
- App version

## Dependencies

```yaml
dependencies:
  flutter_riverpod: ^2.5.0
  go_router: ^14.0.0
  flutter_secure_storage: ^9.0.0
  shared_preferences: ^2.2.0
```

## Implementation Plan

### Phase 1: Foundation

**Goal:** App skeleton with auth working on web.

- Create Flutter project for all platforms
- Set up Riverpod, go_router, secure storage
- Configure `analysis_options.yaml` with strict linting
- Implement `TokenStorage` and `ConfigService`
- Implement `LastThreadStorage` for thread auto-selection persistence
- Implement web auth flow (redirect-based)
- Create login screen and auth guard
- Create placeholder screens for rooms/threads
- Write unit tests for `TokenStorage`, `ConfigService`, and `LastThreadStorage`

**Done when:** User can log in on web and see room list. `flutter analyze` passes, tests pass.

---

### Phase 2: Core Features

**Goal:** Full chat flow working.

- Implement `ActiveRunNotifier` with AG-UI event handling
- **Extend `ActiveRunState` with fields required by UI components:**
  - `rawEvents: List<RawAgUiEvent>` - All raw events (for Detail panel)
  - `stateItems: List<CanvasStateItem>` - From STATE_SNAPSHOT/DELTA (for CurrentCanvas)
  - `currentActivity: CanvasActivity?` - From ACTIVITY_SNAPSHOT/DELTA (for CurrentCanvas)
  - `latestState: Map<String, dynamic>?` - Latest STATE_SNAPSHOT data (for Detail State tab)
- Wire up room selection → thread list → chat
- Implement thread creation on first message (when room has no threads)
- Implement thread auto-selection when entering a room
- Update `LastThreadStorage` when user sends messages
- Implement message display with streaming
- Implement message sending with proper send button enable logic
- Add basic error handling (snackbars)
- Test on mobile (auth via webview)
- Write unit tests for `ActiveRunNotifier` and event processing
- Write widget tests for chat screen

**Done when:** User can have a conversation with the agent. Thread auto-selection works. All tests pass, `flutter analyze` clean.

---

### Phase 3: Polish

**Goal:** Production-ready quality.

- Add loading states throughout
- Implement settings screen
- Add offline indicator
- Test on all platforms
- Fix platform-specific issues
- Implement client tool handlers (if needed)
- Achieve test coverage >= 85%
- Run `flutter analyze` and fix all warnings
- Run `dart format` on all files

**Documentation:**
- Update CLAUDE.md with implemented file structure
- Document new providers and state management patterns
- Add troubleshooting section for common issues

**Done when:** App works reliably on web, iOS, Android. All tests pass, no lint warnings. CLAUDE.md updated.

---

## Future Enhancements (Not in v1)

- Offline caching (view rooms/threads offline)
- Token refresh (if backend supports refresh tokens)
- Desktop platform polish
- Push notifications

## References

- Client specification: `./client.md`
- Backend API: `./external_backend_service.md`
- UI components: `./ui/*.md`
