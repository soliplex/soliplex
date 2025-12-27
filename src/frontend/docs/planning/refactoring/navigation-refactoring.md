# Navigation Refactoring Plan

## Summary

Consolidate RoomScreen and ThreadScreen into a single RoomScreen with:

- Room dropdown in app bar (switch rooms)
- Collapsible thread list sidebar (toggle button)
- Chat view as main content
- HTTP inspector accessible from all screens via ShellRoute
- Last viewed thread per room persisted to SharedPreferences
- Thread selection via optional query parameter (bookmarkable)
- **No transition animations** (instant navigation)
- **Full accessibility** (Semantics, tooltips, labels on all interactive elements)

## UI Requirements

### No Transition Animations

All navigation and UI state changes must be instant with no animations:

- Route transitions: Use `GoRouter` with `pageBuilder` returning `NoTransitionPage`
- Drawer open/close: Disable animation or use instant transition
- Sidebar collapse: Instant width change, no animation

```dart
// In app_router.dart - disable all route transitions
GoRoute(
  path: '/rooms/:roomId',
  pageBuilder: (context, state) => NoTransitionPage(
    child: RoomScreen(...),
  ),
),
```

### Accessibility Requirements

**Interactive elements** (buttons, icons) must have:

1. **Semantics wrapper** with descriptive label
2. **Tooltip** explaining the action
3. **Sufficient contrast** (follows Material guidelines)

**Interactive elements** table:

| Element | Tooltip | Semantics Label |
|---------|---------|-----------------|
| Sidebar toggle | "Show threads" / "Hide threads" | "Toggle thread list sidebar" |
| Room dropdown | "Switch to another room" | "Room selector, current: {roomName}" |
| HTTP inspector icon | "Open HTTP traffic inspector" | — |
| Settings icon | "Open settings" | "Settings" |
| New conversation button | "Start a new conversation" | "Create new thread" |
| Thread list item | "{threadName}" | "Select thread: {threadName}" |
| Send button | "Send message" | "Send message" |

**Container regions** (drawers, panels) need only Semantics labels for screen
reader context — Tooltips don't apply since they're not directly tapped.

| Region | Semantics Label |
|--------|-----------------|
| Navigation drawer | "Navigation drawer" |
| HTTP inspector panel | "HTTP traffic inspector panel" |

## Findings (Resolved)

- [x] **FINDING-01**: Mobile drawer animation - **Decision: Keep animation.**
  Flutter's drawer slide animation (~300ms) is acceptable. The "no animations"
  rule applies to route transitions and sidebar collapse, not drawer interactions.

- [x] **FINDING-02**: Room dropdown accessibility - **Decision: Use DropdownMenu
  (Material 3)** instead of DropdownButton. Better built-in accessibility, less
  maintenance, modern Flutter direction.

- [x] **FINDING-03**: Chat message accessibility - **Decision: Defer to
  implementation.** Streaming accessibility is complex; test with real screen
  reader during ChatPanel work and fix issues found.

- [x] **FINDING-04**: Loading states - **Decision: Add note.** Implementers must
  wrap all CircularProgressIndicator widgets in Semantics with appropriate labels
  (e.g., "Loading rooms", "Loading threads").

## Route Structure

```text
/                              -> HomeScreen
/rooms                         -> RoomsScreen
/rooms/:roomId                 -> RoomScreen (last viewed or first thread)
/rooms/:roomId?thread=xyz      -> RoomScreen (specific thread selected)
/rooms/:roomId/thread/:tid     -> REDIRECT to /rooms/:roomId?thread=:tid
/settings                      -> SettingsScreen
```

**Key change**: Thread selection uses query parameter instead of path segment.
This keeps URLs bookmarkable while consolidating to a single screen.

**Migration**: Old `/rooms/:roomId/thread/:threadId` URLs redirect to the new
query param format to avoid breaking existing bookmarks.

## Design Decision: Query Parameter vs Path Segment

We chose query parameters (`/rooms/:roomId?thread=xyz`) over path segments
(`/rooms/:roomId/thread/:threadId`) for thread selection.

### Rationale

**Semantic fit:** The consolidation changes the conceptual model. Threads are
now *selected within* a room view (like sidebar tabs), not *navigated to* as
separate pages. Query parameters are semantically appropriate for "which view
of this resource am I looking at?" — similar to `/products?category=electronics`.

**Browser back button:** With path segments, back would cycle through thread
history. With query params, back leaves the room entirely. The latter matches
user expectations when thread selection feels like "filtering" rather than
"navigating."

**Route simplicity:** One route definition instead of two. The handler reads
an optional query param rather than managing two separate routes that both
render RoomScreen.

**Trade-off acknowledged:** Path segments feel more "RESTful" and would be
better if threads were truly independent resources for external linking or SEO.
But in this UI, threads are sidebar selections within a room — the URL should
reflect that mental model.

### Comparison

| Aspect | Path Segment | Query Parameter |
|--------|--------------|-----------------|
| Mental model | Navigate TO thread | Select WITHIN room |
| Back button | Cycles through threads | Leaves the room |
| Route complexity | Two routes + redirect | One route |
| Semantic fit | Thread as page | Thread as filter |

## Architecture

### Single Scaffold via AppShell

Each route wraps its content in AppShell, which owns the only Scaffold.
Screens provide body content only, not their own Scaffold.

```text
GoRoute
└── AppShell(config, body)
    └── Scaffold (single, owns AppBar + endDrawer)
        ├── appBar: Built from ShellConfig
        ├── endDrawer: HttpInspectorPanel
        ├── drawer: (mobile only) from ShellConfig
        └── body: Screen content
```

**Why single Scaffold?** Nested Scaffolds don't share drawers. If each screen
had its own Scaffold, `Scaffold.of(context).openEndDrawer()` would find the
inner Scaffold (which has no drawer) instead of AppShell's.

### Screen Types

**Static screens** (HomeScreen, RoomsScreen, SettingsScreen): Wrapped in
AppShell at the router level with static ShellConfig.

**Dynamic screens** (RoomScreen): Build their own AppShell internally to
provide dynamic ShellConfig (e.g., room dropdown, sidebar toggle).

### Design Decision: Dynamic Screen Wrapping

**Decision:** RoomScreen returns AppShell directly (Option A).

**Rationale:** RoomScreen's ShellConfig depends on:

1. Provider state (room dropdown needs roomsProvider)
2. Local widget state (sidebar toggle needs `_sidebarCollapsed`)

If the router wrapped RoomScreen, it couldn't access the sidebar collapse state
which lives inside RoomScreen's StatefulWidget. Lifting that state to a provider
feels like overkill for UI-only state.

Since RoomScreen is the only dynamic screen, the inconsistency with static
screens (which are router-wrapped) is acceptable.

**Migration path if needed later:**

If a second dynamic screen emerges and the pattern feels wrong:

1. Extract sidebar state to a provider:

   ```dart
   final sidebarCollapsedProvider = StateProvider<bool>((ref) => false);
   ```

2. Change RoomScreen to return body content only (not AppShell)
3. Move config building to router (reads from providers)
4. Update router to wrap RoomScreen in AppShell

This is a mechanical refactor. AppShell is already a separate widget and
ShellConfig is pure data, so no structural changes needed.

### RoomScreen Layout

**Desktop (>=600px):**

```text
+------------------------------------------+
|  AppBar: [=] [Room v]         [bug] [gear]|
+------------------------------------------+
| Thread    |                              |
| List      |      ChatPanel               |
| (toggle)  |                              |
+------------------------------------------+
```

**Mobile (<600px):**

```text
+------------------------------------------+
|  AppBar: [=] [Room v]         [bug] [gear]|
+------------------------------------------+
|                                          |
|           ChatPanel                      |
|                                          |
+------------------------------------------+
+ Drawer (leading): HistoryPanel
```

- Desktop: Sidebar toggle button collapses/expands thread list
- Mobile: Hamburger menu opens drawer with thread list

## Key Behaviors

### Thread Selection on Room Entry

Async flow with validation:

```dart
Future<void> initializeThreadSelection(String roomId, String? queryThread) async {
  final threads = await ref.read(threadsProvider(roomId).future);

  if (threads.isEmpty) {
    // Show welcome/empty state
    ref.read(threadSelectionProvider.notifier).clear();
    return;
  }

  // 1. Check query param first
  if (queryThread != null && threads.any((t) => t.id == queryThread)) {
    ref.read(threadSelectionProvider.notifier).select(queryThread);
    await _saveLastViewed(roomId, queryThread);
    return;
  }

  // 2. Try last viewed from SharedPreferences
  final lastViewed = await _getLastViewed(roomId);
  if (lastViewed != null && threads.any((t) => t.id == lastViewed)) {
    ref.read(threadSelectionProvider.notifier).select(lastViewed);
    return;
  }

  // 3. Fall back to first thread
  final firstThread = threads.first.id;
  ref.read(threadSelectionProvider.notifier).select(firstThread);
  await _saveLastViewed(roomId, firstThread);
}
```

**Key points:**

- Query param takes precedence (enables deep linking)
- Validates thread still exists before selecting
- Falls back gracefully through the chain

### Sidebar Toggle

- Toggle button in app bar (desktop only)
- Collapse state in local widget state (resets on navigation - intentional YAGNI)
- Accessibility: `Semantics(label: 'Toggle thread list sidebar')`

### Last Viewed Thread

- Stored per room in SharedPreferences
- Key: `lastViewedThread_{roomId}` -> `threadId`
- Updated on thread selection and thread creation

## Work In Progress

### Completed

- [x] Phase 1: AppShell Foundation
- [x] Phase 2: Last Viewed Thread Provider
- [x] Phase 3: Update Panels (HistoryPanel + ChatPanel persist last viewed)
- [x] Phase 4: Consolidate RoomScreen

### Current Status

**Phase 4 complete.** RoomScreen now consolidates the thread list and chat view:

- Responsive layout: Desktop sidebar + mobile drawer
- Async thread selection: query param → last viewed → first thread
- Sidebar toggle with accessibility (desktop only)
- Room dropdown with loading/error states
- Comprehensive test coverage (383 tests passing)

### Null Elimination (Post Phase 4)

Refactored to eliminate null returns/assignments where feasible:

**Fixed:**

| Issue | Solution |
|-------|----------|
| `_withErrorHandling` returned `null` on failure | Use `Result<T>` sealed class (`Ok`/`Err`) |
| `lastViewedThreadProvider` returned `String?` | Use `LastViewed` sealed class (`HasLastViewed`/`NoLastViewed`) |
| `thread!.id` force unwrap in ChatPanel | Restructured with `final effectiveThread` |
| `error: (_, __)` discarding error info | Added `debugPrint` logging |

**Unfixable (framework constraints):**

| Issue | Reason |
|-------|--------|
| `initialThreadId: String?` | GoRouter query params are inherently nullable |
| `ShellConfig` nullable fields | Flutter Scaffold API requires nullable drawer/FAB |
| `currentRoom?.name ?? 'none'` | Room can be null when no room selected |

**New types added:**

- `lib/core/models/result.dart` - `Result<T>` with `Ok`/`Err` variants
- `LastViewed` sealed class in `threads_provider.dart` with `HasLastViewed`/`NoLastViewed`

## Implementation Phases

### Phase 1: AppShell Foundation

1. Create `lib/shared/widgets/app_shell.dart`:
   - Scaffold with endDrawer (HttpInspectorPanel)
   - Inspector icon button in actions
   - Passes child through
2. Update `app_router.dart`:
   - Wrap all routes in ShellRoute using AppShell
   - Add redirect for `/rooms/:roomId/thread/:threadId` -> query param
3. Remove inspector code from ThreadScreen (will be deleted anyway)
4. Add tests for ShellRoute and redirect

### Phase 2: Last Viewed Thread Provider

1. Add to `threads_provider.dart`:

   ```dart
   // Read: FutureProvider for observable data
   final lastViewedThreadProvider = FutureProvider.family<String?, String>(...);

   // Write: Plain functions for imperative commands
   Future<void> setLastViewedThread(Ref ref, {required String roomId, required String threadId});
   Future<void> clearLastViewedThread(Ref ref, String roomId);
   ```

   **Design note:** Write operations are functions (not providers) because
   FutureProvider is for observable data, not imperative commands. Functions
   that take `Ref` can still invalidate providers for cache coherence.

1. Add tests for provider (including stale thread handling)

   **Testing note:** Functions that accept `Ref` require test helper providers
   to obtain a Ref in tests. This is a known limitation—the indirection is
   acceptable when localized to test files.

### Phase 3: Update Panels

1. `history_panel.dart`:
   - Call `setLastViewed` on thread selection
   - Update URL with query param on selection
1. `chat_panel.dart`:
   - Call `setLastViewed` when thread is created
   - Update URL with query param after creation

### Phase 4: Consolidate RoomScreen

1. Rewrite `room_screen.dart`:
   - Read `?thread=` query param on mount
   - Implement async thread selection flow (see above)
   - Desktop: Row with togglable HistoryPanel + ChatPanel
   - Mobile: ChatPanel + leading Drawer with HistoryPanel
   - Room dropdown with loading/error states
1. ~~Delete `thread_screen.dart` and its test~~ — ✅ Already deleted
1. Update all related tests

### Phase 5: Polish

1. Run `mcp__dart__analyze_files` (0 issues)
1. Run `mcp__dart__dart_format`
1. Run `mcp__dart__run_tests` (all pass)

## Files Summary

### Create

| File | Purpose |
|------|---------|
| `lib/shared/widgets/app_shell.dart` | Single Scaffold shell with inspector |
| `lib/shared/widgets/shell_config.dart` | Shell configuration for screens |

### Modify

| File | Change |
|------|--------|
| `lib/core/router/app_router.dart` | ShellRoute with AppShell, NoTransitionPage |
| `lib/core/providers/threads_provider.dart` | Add LastViewedThreadNotifier |
| `lib/features/room/room_screen.dart` | Complete rewrite, no Scaffold |
| `lib/features/history/history_panel.dart` | Track last viewed, update URL |
| `lib/features/chat/chat_panel.dart` | Track last viewed on create |
| `lib/features/home/home_screen.dart` | Remove Scaffold, return body + config |
| `lib/features/rooms/rooms_screen.dart` | Remove Scaffold, return body + config |
| `lib/features/settings/settings_screen.dart` | Remove Scaffold, return body + config |

### Delete

| File | Status |
|------|--------|
| ~~`lib/features/thread/thread_screen.dart`~~ | ✅ Deleted |
| ~~`test/features/thread/thread_screen_test.dart`~~ | ✅ Deleted |

## Code Snippets

### ShellConfig

```dart
/// Configuration for AppShell's Scaffold (AppBar, drawer, FAB).
@immutable
class ShellConfig {
  const ShellConfig({
    this.title,
    this.leading,
    this.actions = const [],
    this.drawer,
    this.floatingActionButton,
  });

  final Widget? title;
  final Widget? leading;
  final List<Widget> actions;
  final Widget? drawer; // For mobile drawer (e.g., thread list)
  final Widget? floatingActionButton;
}
```

### AppShell (Single Scaffold Architecture)

```dart
class AppShell extends StatelessWidget {
  const AppShell({
    required this.config,
    required this.body,
    super.key,
  });

  final ShellConfig config;
  final Widget body;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: config.leading,
        title: config.title,
        actions: [
          ...config.actions,
          const _InspectorButton(),
        ],
      ),
      drawer: config.drawer != null
          ? Semantics(
              label: 'Navigation drawer',
              child: config.drawer,
            )
          : null,
      endDrawer: Semantics(
        label: 'HTTP traffic inspector panel',
        child: const SizedBox(
          width: 400,
          child: Drawer(child: HttpInspectorPanel()),
        ),
      ),
      body: body,
    );
  }
}

/// Button that opens the HTTP inspector drawer.
///
/// Separate widget class ensures build() provides the correct context
/// for Scaffold.of() to find the Scaffold we just built.
@immutable
class _InspectorButton extends StatelessWidget {
  const _InspectorButton();

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: 'Open HTTP traffic inspector',
      child: IconButton(
        icon: const Icon(Icons.bug_report),
        onPressed: () => Scaffold.of(context).openEndDrawer(),
      ),
    );
  }
}
```

### Router Setup (No Transitions)

Each route wraps its screen in AppShell with appropriate config:

```dart
GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      pageBuilder: (_, __) => NoTransitionPage(
        child: AppShell(
          config: const ShellConfig(title: Text('Home')),
          body: const HomeScreen(),
        ),
      ),
    ),
    GoRoute(
      path: '/rooms',
      pageBuilder: (_, __) => NoTransitionPage(
        child: AppShell(
          config: const ShellConfig(title: Text('Rooms')),
          body: const RoomsScreen(),
        ),
      ),
    ),
    GoRoute(
      path: '/rooms/:roomId',
      pageBuilder: (context, state) {
        final roomId = state.pathParameters['roomId']!;
        final threadId = state.uri.queryParameters['thread'];
        return NoTransitionPage(
          child: RoomScreen(roomId: roomId, initialThreadId: threadId),
          // RoomScreen builds its own AppShell with dynamic config
        );
      },
    ),
    // Migration redirect
    GoRoute(
      path: '/rooms/:roomId/thread/:threadId',
      redirect: (context, state) {
        final roomId = state.pathParameters['roomId']!;
        final threadId = state.pathParameters['threadId']!;
        return '/rooms/$roomId?thread=$threadId';
      },
    ),
    GoRoute(
      path: '/settings',
      pageBuilder: (_, __) => NoTransitionPage(
        child: AppShell(
          config: const ShellConfig(title: Text('Settings')),
          body: const SettingsScreen(),
        ),
      ),
    ),
  ],
  errorBuilder: (context, state) => AppShell(
    config: const ShellConfig(title: Text('Error')),
    body: // ... error content
  ),
)
```

### Room Dropdown with Async Handling and Accessibility

Uses Material 3 `DropdownMenu` for better built-in accessibility.

```dart
Consumer(
  builder: (context, ref, _) {
    final roomsAsync = ref.watch(roomsProvider);
    final currentRoom = ref.watch(currentRoomProvider);
    return roomsAsync.when(
      data: (rooms) => Semantics(
        label: 'Room selector, current: ${currentRoom?.name ?? 'none'}',
        child: Tooltip(
          message: 'Switch to another room',
          child: DropdownMenu<String>(
            initialSelection: currentRoom?.id,
            dropdownMenuEntries: rooms
                .map((r) => DropdownMenuEntry(value: r.id, label: r.name))
                .toList(),
            onSelected: (id) {
              if (id != null) context.go('/rooms/$id');
            },
          ),
        ),
      ),
      loading: () => Semantics(
        label: 'Loading rooms',
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      error: (_, __) => Semantics(
        label: 'Error loading rooms',
        child: Tooltip(
          message: 'Failed to load rooms',
          child: const Icon(Icons.error_outline),
        ),
      ),
    );
  },
),
```

### Sidebar Toggle with Accessibility

```dart
// Desktop only - check screen width first
if (isDesktop)
  Semantics(
    label: _sidebarCollapsed
        ? 'Show thread list sidebar'
        : 'Hide thread list sidebar',
    child: IconButton(
      icon: Icon(_sidebarCollapsed ? Icons.menu : Icons.menu_open),
      tooltip: _sidebarCollapsed ? 'Show threads' : 'Hide threads',
      onPressed: () => setState(() => _sidebarCollapsed = !_sidebarCollapsed),
    ),
  ),
```

## Test Cases

### Thread Restoration Tests

```dart
group('Thread selection on room entry', () {
  test('selects thread from query param when valid', ...);
  test('ignores query param when thread does not exist', ...);
  test('falls back to last viewed when no query param', ...);
  test('ignores last viewed when thread no longer exists', ...);
  test('selects first thread when no query param and no last viewed', ...);
  test('shows empty state when room has no threads', ...);
});

group('URL migration', () {
  test('redirects /rooms/abc/thread/xyz to /rooms/abc?thread=xyz', ...);
});

group('ShellRoute inspector', () {
  test('inspector drawer accessible from all screens', ...);
  test('inspector icon visible in app bar', ...);
});
```
