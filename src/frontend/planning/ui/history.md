# History

The history component displays the list of threads in the current room and handles thread selection.

## Scope

- Displays threads for the **current room**
- When room changes, loads threads and handles auto-selection
- Allows user to select a thread to view in Chat
- Shows visual indicator for selected thread
- Provides "New Conversation" action to start fresh threads

## Provider Integration

The history component consumes these providers from core_frontend:

```dart
// Current context
final room = ref.watch(currentRoomProvider);
final currentThread = ref.watch(currentThreadProvider);

// Thread list for current room
final threadsAsync = ref.watch(threadsProvider);

// Auto-selected thread (when entering a room)
final autoSelectedThread = ref.watch(autoSelectedThreadProvider);
```

Note: `autoSelectedThreadProvider` is a `FutureProvider<Thread?>`, so watching it returns `AsyncValue<Thread?>`. Use `.valueOrNull` to access the thread.

### Auto-Selection Behavior

When the room changes, the history component should listen for auto-selection with fallback to most recent:

```dart
ref.listen(autoSelectedThreadProvider, (_, next) {
  if (next.isLoading) return;

  final thread = next.valueOrNull;
  if (thread != null) {
    // Found the last-used thread
    ref.read(currentThreadProvider.notifier).state = thread;
  } else {
    // Fallback: select most recent thread if stored one not found/deleted
    final threads = ref.read(threadsProvider).valueOrNull;
    if (threads != null && threads.isNotEmpty) {
      ref.read(currentThreadProvider.notifier).state = threads.first;
    }
  }
});
```

This ensures that when a user enters a room, their last-used thread is automatically selected, with graceful fallback.

## Thread Ordering

Threads are sorted by **last activity time** (most recent first). The backend returns threads in this order.

## UI States

### Loading

- Show loading indicator while `threadsAsync.isLoading`
- Disable thread selection

### Error

- Show error message: "Couldn't load conversations"
- Show retry button
- On tap: `ref.invalidate(threadsProvider)`

### Empty (No Threads)

- Show empty state message: "No conversations yet"
- Show prompt: "Start a new conversation below"
- User can start a new conversation from Chat (which creates a thread)

### Has Threads

- Show list of threads
- Highlight currently selected thread
- Allow clicking to select a different thread

### No Room Selected

- Hide the history panel entirely (recommended for responsive layouts)
- Alternative: Show disabled state with message "Select a room to see conversations"

## Thread List Item

Each thread item shows:

| Element | Description |
|---------|-------------|
| **Title** | Thread title from metadata, or first message snippet |
| **Timestamp** | Relative time ("2 min ago", "Yesterday", "Dec 10") |
| **Preview** | Last message excerpt, truncated to ~50 chars |
| **Active indicator** | Dot or subtle animation if a run is active on this thread |
| **Selection highlight** | Background color change for selected thread |

## New Thread Action

- Show "New Conversation" button in panel header or as floating action
- On tap:
  1. Clear current thread: `ref.read(currentThreadProvider.notifier).state = null`
  2. Chat input becomes enabled (room has threads but none selected = disabled, so this requires Chat to handle the "new thread" intent)
- Alternative: Navigate to a "new thread" state that Chat recognizes

```dart
void onNewThread() {
  ref.read(currentThreadProvider.notifier).state = null;
  // Signal to Chat that user wants a new thread (not just deselected)
  ref.read(newThreadIntentProvider.notifier).state = true;
}
```

Note: Coordinate with Chat component on how to handle this state.

## Thread Selection

```dart
void onSelectThread(Thread thread) {
  ref.read(currentThreadProvider.notifier).state = thread;
  // Clear any new thread intent
  ref.read(newThreadIntentProvider.notifier).state = false;
}
```

When a thread is selected:

1. Update `currentThreadProvider`
2. Chat component automatically loads messages for that thread

## Thread Deletion (Optional - Future)

If thread deletion is supported:

- Swipe-to-delete gesture on mobile
- Delete icon in hover menu on desktop
- Confirmation dialog: "Delete this conversation?"
- After deletion:
  1. Remove from local list
  2. If deleted thread was selected, select next thread or show empty state
  3. Invalidate `threadsProvider` to sync with backend

## Refresh

- **Mobile**: Pull-to-refresh gesture on the thread list
- **Desktop**: Refresh icon button in panel header
- Action: `ref.invalidate(threadsProvider)`

## Pagination (Future)

For rooms with many threads:

- Initial load: most recent 50 threads
- Infinite scroll: load more when approaching list end
- Show loading indicator at bottom while fetching
- Alternative: "Load more conversations" button

## Interaction with Chat

| User Action | History | Chat |
|-------------|---------|------|
| Selects room | Loads threads, auto-selects last (or most recent) | Shows selected thread's messages |
| Clicks thread | Updates selection | Loads new thread's messages |
| Clicks "New Conversation" | Clears selection, signals intent | Shows empty state, input enabled |
| Sends first message (new thread) | Refreshes list, shows new thread selected | Creates thread, shows messages |

## Implementation Plan

### File Structure

```
lib/
├── ui/
│   └── history/
│       ├── history_panel.dart       # Main panel widget
│       ├── thread_list.dart         # Thread list with states
│       ├── thread_list_item.dart    # Individual thread row
│       └── history_header.dart      # Header with "New" button
└── widgets/
    └── relative_timestamp.dart      # "2 min ago" helper widget
```

---

### Phase 1: Widget Scaffold

**Goal:** Establish file structure and basic widget hierarchy.

**Files to create:**
- `lib/ui/history/history_panel.dart`
- `test/ui/history/history_panel_test.dart`

**Steps:**
1. Create `HistoryPanel` as a `ConsumerWidget`
2. Watch `currentRoomProvider` - if null, return empty `SizedBox`
3. Watch `threadsProvider` for the thread list
4. Return placeholder `Container` with debug text showing thread count
5. Write widget tests for the component
6. Run linting and fix any issues

```dart
class HistoryPanel extends ConsumerWidget {
  const HistoryPanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final room = ref.watch(currentRoomProvider);
    if (room == null) return const SizedBox.shrink();

    final threadsAsync = ref.watch(threadsProvider);

    return Container(
      child: Text('Threads: ${threadsAsync.valueOrNull?.length ?? "loading"}'),
    );
  }
}
```

**Tests:**
- `test/ui/history/history_panel_test.dart`:
  - Widget test: renders when room selected
  - Widget test: returns SizedBox when no room

**Verification:**
```bash
# Run linting
flutter analyze

# Run tests
flutter test test/ui/history/

# Check coverage
flutter test --coverage test/ui/history/
```

**Acceptance criteria:**
- [ ] `HistoryPanel` renders without errors
- [ ] Shows "loading" when threads are loading
- [ ] Shows thread count when loaded
- [ ] Shows nothing when no room selected
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 2: Loading, Empty, and Error States

**Goal:** Handle all async states before showing actual content.

**Files to create:**
- `lib/ui/history/thread_list.dart`
- `test/ui/history/thread_list_test.dart`

**Steps:**
1. Create `ThreadList` widget that takes `AsyncValue<List<Thread>>`
2. Implement loading state with `CircularProgressIndicator`
3. Implement empty state with message and icon
4. Implement error state with message and retry button
5. Wire retry to `ref.invalidate(threadsProvider)`
6. Update `HistoryPanel` to use `ThreadList`
7. Write widget tests for all states
8. Run linting and fix any issues

```dart
class ThreadList extends ConsumerWidget {
  const ThreadList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final threadsAsync = ref.watch(threadsProvider);

    return threadsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => _ErrorState(
        message: 'Couldn\'t load conversations',
        onRetry: () => ref.invalidate(threadsProvider),
      ),
      data: (threads) => threads.isEmpty
          ? const _EmptyState()
          : _ThreadListView(threads: threads),
    );
  }
}

class _EmptyState extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey),
          SizedBox(height: 16),
          Text('No conversations yet'),
          Text('Start a new conversation below', style: TextStyle(color: Colors.grey)),
        ],
      ),
    );
  }
}
```

**Tests:**
- `test/ui/history/thread_list_test.dart`:
  - Widget test: loading state displays spinner
  - Widget test: empty state displays message and icon
  - Widget test: error state displays error message
  - Widget test: error state displays retry button
  - Widget test: retry button calls `ref.invalidate`

**Verification:**
```bash
flutter analyze
flutter test test/ui/history/
flutter test --coverage test/ui/history/
```

**Acceptance criteria:**
- [ ] Loading spinner shown while fetching
- [ ] Empty state shown when threads list is empty
- [ ] Error state shown on fetch failure
- [ ] Retry button triggers refetch
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 3: Thread List Display

**Goal:** Render the list of threads with basic info.

**Files to create:**
- `lib/ui/history/thread_list_item.dart`
- `lib/widgets/relative_timestamp.dart`
- `test/ui/history/thread_list_item_test.dart`
- `test/widgets/relative_timestamp_test.dart`

**Steps:**
1. Create `ThreadListItem` widget displaying:
   - Title (or "Untitled conversation")
   - Relative timestamp ("2 min ago")
2. Create `RelativeTimestamp` helper widget
3. Implement `_ThreadListView` using `ListView.builder`
4. Add basic styling (padding, dividers)
5. Write unit tests for `RelativeTimestamp` formatting logic
6. Write widget tests for `ThreadListItem`
7. Run linting and fix any issues

```dart
class ThreadListItem extends StatelessWidget {
  final Thread thread;
  final bool isSelected;
  final VoidCallback onTap;

  const ThreadListItem({
    required this.thread,
    required this.isSelected,
    required this.onTap,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(
        thread.title ?? 'Untitled conversation',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: RelativeTimestamp(thread.updatedAt),
      selected: isSelected,
      onTap: onTap,
    );
  }
}
```

**Tests:**
- `test/widgets/relative_timestamp_test.dart`:
  - Unit test: formats "just now" for < 1 minute
  - Unit test: formats "X min ago" for < 1 hour
  - Unit test: formats "X hours ago" for < 24 hours
  - Unit test: formats "Yesterday" for 1 day ago
  - Unit test: formats date for > 1 week ago
- `test/ui/history/thread_list_item_test.dart`:
  - Widget test: renders thread title
  - Widget test: renders "Untitled conversation" when title is null
  - Widget test: truncates long titles with ellipsis
  - Widget test: renders timestamp

**Verification:**
```bash
flutter analyze
flutter test test/ui/history/ test/widgets/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Threads render in a scrollable list
- [ ] Each thread shows title and timestamp
- [ ] Long titles are truncated with ellipsis
- [ ] Timestamps show relative time ("2 min ago", "Yesterday")
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 4: Thread Selection

**Goal:** User can select a thread, selection is visually indicated.

**Steps:**
1. Watch `currentThreadProvider` in `ThreadList`
2. Pass `isSelected` boolean to each `ThreadListItem`
3. Implement `onTap` to update `currentThreadProvider`
4. Add visual selection indicator (background color, leading icon)
5. Clear `newThreadIntentProvider` on selection
6. Write widget tests for selection behavior
7. Write integration test with Chat component
8. Run linting and fix any issues

```dart
// In _ThreadListView
final currentThread = ref.watch(currentThreadProvider);

ListView.builder(
  itemCount: threads.length,
  itemBuilder: (context, index) {
    final thread = threads[index];
    final isSelected = thread.id == currentThread?.id;

    return ThreadListItem(
      thread: thread,
      isSelected: isSelected,
      onTap: () {
        ref.read(currentThreadProvider.notifier).state = thread;
        ref.read(newThreadIntentProvider.notifier).state = false;
      },
    );
  },
)
```

**Tests:**
- `test/ui/history/thread_list_test.dart` (add to existing):
  - Widget test: tapping thread updates `currentThreadProvider`
  - Widget test: selected thread has highlighted background
  - Widget test: tapping thread clears `newThreadIntentProvider`
  - Widget test: only one thread can be selected at a time
- `test/integration/history_chat_test.dart`:
  - Integration test: selecting thread triggers Chat to load messages

**Verification:**
```bash
flutter analyze
flutter test test/ui/history/
flutter test test/integration/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Tapping thread updates `currentThreadProvider`
- [ ] Selected thread has visual highlight
- [ ] Selection clears `newThreadIntentProvider`
- [ ] Chat component receives selection (integration)
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 5: Auto-Selection

**Goal:** Automatically select appropriate thread when entering a room.

**Dependencies:** Requires `autoSelectedThreadProvider` from core_frontend.

**Files to create:**
- `test/ui/history/auto_selection_test.dart`

**Steps:**
1. Add `ref.listen` for `autoSelectedThreadProvider` in `HistoryPanel`
2. On value change, set `currentThreadProvider`
3. Implement fallback: if auto-selected is null but threads exist, select first
4. Handle edge case: don't override if user already selected a thread
5. Handle timing: wait for threads to load before fallback
6. Write unit tests for auto-selection logic
7. Write widget tests for auto-selection behavior
8. Run linting and fix any issues

```dart
@override
Widget build(BuildContext context, WidgetRef ref) {
  final room = ref.watch(currentRoomProvider);
  if (room == null) return const SizedBox.shrink();

  // Auto-selection listener
  ref.listen(autoSelectedThreadProvider, (previous, next) {
    if (next.isLoading) return;

    final autoThread = next.valueOrNull;
    final currentThread = ref.read(currentThreadProvider);

    // Don't override user's explicit selection
    if (currentThread != null) return;

    if (autoThread != null) {
      ref.read(currentThreadProvider.notifier).state = autoThread;
    } else {
      // Fallback to most recent
      final threads = ref.read(threadsProvider).valueOrNull;
      if (threads != null && threads.isNotEmpty) {
        ref.read(currentThreadProvider.notifier).state = threads.first;
      }
    }
  });

  // ... rest of build
}
```

**Tests:**
- `test/ui/history/auto_selection_test.dart`:
  - Unit test: `autoSelectedThreadProvider` returns stored thread when found
  - Unit test: `autoSelectedThreadProvider` returns null when stored thread deleted
  - Widget test: auto-selection sets `currentThreadProvider` on room change
  - Widget test: fallback selects first thread when stored thread not found
  - Widget test: empty room results in no selection (null)
  - Widget test: user's explicit selection is not overridden by auto-selection
  - Widget test: auto-selection waits for threads to load before fallback

**Verification:**
```bash
flutter analyze
flutter test test/ui/history/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Entering room with stored last-thread selects that thread
- [ ] Entering room first time selects most recent thread
- [ ] Entering room with deleted last-thread falls back to most recent
- [ ] Entering empty room selects nothing
- [ ] User selection is not overridden by auto-selection
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 6: New Conversation Button

**Goal:** User can start a new conversation from rooms that already have threads.

**Files to create:**
- `lib/ui/history/history_header.dart`
- `test/ui/history/history_header_test.dart`

**Steps:**
1. Create `HistoryHeader` with title and "New" button
2. On tap, clear `currentThreadProvider` and set `newThreadIntentProvider`
3. Update `HistoryPanel` to include header
4. Style button (icon button or text button)
5. Write widget tests for header and button behavior
6. Write integration test with Chat component
7. Run linting and fix any issues

```dart
class HistoryHeader extends ConsumerWidget {
  const HistoryHeader({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: Row(
        children: [
          Text('Conversations', style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'New conversation',
            onPressed: () {
              ref.read(currentThreadProvider.notifier).state = null;
              ref.read(newThreadIntentProvider.notifier).state = true;
            },
          ),
        ],
      ),
    );
  }
}
```

**Tests:**
- `test/ui/history/history_header_test.dart`:
  - Widget test: renders title "Conversations"
  - Widget test: renders "New" icon button
  - Widget test: tapping "New" button clears `currentThreadProvider`
  - Widget test: tapping "New" button sets `newThreadIntentProvider` to true
  - Widget test: button has correct tooltip
- `test/integration/history_chat_test.dart` (add to existing):
  - Integration test: tapping "New" enables Chat input
  - Integration test: sending message after "New" creates new thread

**Verification:**
```bash
flutter analyze
flutter test test/ui/history/
flutter test test/integration/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] "New" button visible in header
- [ ] Tapping clears thread selection
- [ ] Tapping sets newThreadIntentProvider to true
- [ ] Chat input becomes enabled (integration)
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 7: Refresh

**Goal:** User can manually refresh the thread list.

**Files to create:**
- `test/ui/history/refresh_test.dart`

**Steps:**
1. Wrap `ThreadList` in `RefreshIndicator` for pull-to-refresh (mobile)
2. Add refresh `IconButton` in `HistoryHeader` (desktop)
3. Both trigger `ref.invalidate(threadsProvider)`
4. Show loading indicator during refresh
5. Write widget tests for refresh behavior
6. Test on both mobile and desktop form factors
7. Run linting and fix any issues

```dart
// Mobile: wrap in RefreshIndicator
RefreshIndicator(
  onRefresh: () async {
    ref.invalidate(threadsProvider);
    // Wait for the new data
    await ref.read(threadsProvider.future);
  },
  child: _ThreadListView(threads: threads),
)

// Desktop: add to header
IconButton(
  icon: const Icon(Icons.refresh),
  tooltip: 'Refresh',
  onPressed: () => ref.invalidate(threadsProvider),
)
```

**Tests:**
- `test/ui/history/refresh_test.dart`:
  - Widget test: pull-to-refresh gesture triggers `ref.invalidate`
  - Widget test: refresh button triggers `ref.invalidate`
  - Widget test: loading indicator shown during refresh
  - Widget test: list updates after refresh completes
  - Widget test: refresh button has correct tooltip
- `test/ui/history/history_header_test.dart` (add to existing):
  - Widget test: refresh button renders on desktop

**Verification:**
```bash
flutter analyze
flutter test test/ui/history/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Pull-to-refresh works on mobile
- [ ] Refresh button works on desktop
- [ ] Loading indicator shown during refresh
- [ ] List updates after refresh completes
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 8: Polish

**Goal:** Production-ready visual quality and UX.

**Files to create:**
- `test/ui/history/accessibility_test.dart`
- `test/ui/history/responsive_test.dart`

**Steps:**
1. **Thread metadata:** Add message preview (last message truncated)
2. **Active indicator:** Show dot/animation on threads with active runs
3. **Selection animation:** Animate background color change
4. **Keyboard navigation:** Arrow keys to move selection, Enter to select
5. **Accessibility:** Add Semantics labels for screen readers
6. **Empty state refinement:** Add illustration or icon
7. **Responsive:** Adjust padding/sizing for different screen sizes
8. Write accessibility tests
9. Write responsive layout tests
10. Run full test suite and ensure coverage >= 85%
11. Run linting and fix all warnings

```dart
// Active run indicator
final activeRun = ref.watch(activeRunProvider);
final hasActiveRun = activeRun.threadId == thread.id &&
                     activeRun.status == RunStatus.running;

// In ThreadListItem
if (hasActiveRun)
  Container(
    width: 8,
    height: 8,
    decoration: BoxDecoration(
      color: Colors.blue,
      shape: BoxShape.circle,
    ),
  )
```

**Tests:**
- `test/ui/history/thread_list_item_test.dart` (add to existing):
  - Widget test: active run indicator appears when run is active
  - Widget test: active run indicator hidden when run is idle
  - Widget test: message preview displays truncated text
  - Widget test: selection animates smoothly
- `test/ui/history/accessibility_test.dart`:
  - Accessibility test: thread item has semantic label with title
  - Accessibility test: thread item has semantic label with timestamp
  - Accessibility test: selected state is announced
  - Accessibility test: "New" button has semantic label
  - Accessibility test: meets minimum tap target size (48x48)
- `test/ui/history/responsive_test.dart`:
  - Widget test: renders correctly on mobile (360px width)
  - Widget test: renders correctly on tablet (768px width)
  - Widget test: renders correctly on desktop (1200px width)
  - Widget test: text scales appropriately with system font size

**Verification:**
```bash
# Full lint check
flutter analyze
dart format --set-exit-if-changed lib/ test/

# Run all tests
flutter test

# Check coverage meets threshold
flutter test --coverage
lcov --summary coverage/lcov.info  # Should show >= 85%

# Run accessibility checks (if using accessibility_tools package)
flutter test test/ui/history/accessibility_test.dart
```

**Documentation:**
- Update CLAUDE.md with History component file structure
- Document thread auto-selection patterns

**Acceptance criteria:**
- [ ] Message preview shown for each thread
- [ ] Active runs show indicator
- [ ] Selection has smooth animation
- [ ] Keyboard navigation works (arrow keys + Enter)
- [ ] Screen reader announces thread info correctly
- [ ] Looks good on mobile, tablet, desktop
- [ ] `flutter analyze` passes with no errors or warnings
- [ ] `dart format` reports no changes needed
- [ ] All tests pass
- [ ] Overall test coverage >= 85%
- [ ] Accessibility tests pass
- [ ] CLAUDE.md updated

---

### Phase Summary

| Phase | Goal | Key Deliverable | Tests |
|-------|------|-----------------|-------|
| 1 | Scaffold | `HistoryPanel` renders | 2 widget tests |
| 2 | States | Loading, empty, error handled | 5 widget tests |
| 3 | Display | Thread list with titles | 5 unit + 4 widget tests |
| 4 | Selection | Tap to select thread | 4 widget + 1 integration test |
| 5 | Auto-select | Room entry selects thread | 2 unit + 5 widget tests |
| 6 | New thread | "New" button works | 5 widget + 2 integration tests |
| 7 | Refresh | Pull/button refresh | 6 widget tests |
| 8 | Polish | Production quality | 4 widget + 5 a11y + 4 responsive tests |

### Dependencies

```
Phase 1 ─┬─► Phase 2 ─► Phase 3 ─► Phase 4 ─┬─► Phase 8
         │                                   │
         │                                   ├─► Phase 5 ─► Phase 8
         │                                   │
         └───────────────────────────────────┴─► Phase 6 ─► Phase 8
                                             │
                                             └─► Phase 7 ─► Phase 8
```

- Phases 5, 6, 7 can be done in parallel after Phase 4
- Phase 8 requires all other phases complete

---

### Future Enhancements (Not in v1)

- Thread deletion with confirmation
- Pagination / infinite scroll for large thread counts
- Thread search/filter
- Thread renaming
- Drag-to-reorder threads
- Thread grouping by date

---

## Testing

### Test File Structure

```
test/
├── ui/
│   └── history/
│       ├── history_panel_test.dart      # Phase 1
│       ├── thread_list_test.dart        # Phase 2, 4
│       ├── thread_list_item_test.dart   # Phase 3, 8
│       ├── history_header_test.dart     # Phase 6, 7
│       ├── auto_selection_test.dart     # Phase 5
│       ├── refresh_test.dart            # Phase 7
│       ├── accessibility_test.dart      # Phase 8
│       └── responsive_test.dart         # Phase 8
├── widgets/
│   └── relative_timestamp_test.dart     # Phase 3
└── integration/
    └── history_chat_test.dart           # Phase 4, 6
```

### Unit Tests

| Test | File | Phase |
|------|------|-------|
| RelativeTimestamp formats "just now" | `relative_timestamp_test.dart` | 3 |
| RelativeTimestamp formats "X min ago" | `relative_timestamp_test.dart` | 3 |
| RelativeTimestamp formats "Yesterday" | `relative_timestamp_test.dart` | 3 |
| RelativeTimestamp formats dates | `relative_timestamp_test.dart` | 3 |
| Auto-selection returns stored thread | `auto_selection_test.dart` | 5 |
| Auto-selection returns null when deleted | `auto_selection_test.dart` | 5 |

### Widget Tests

| Test | File | Phase |
|------|------|-------|
| HistoryPanel renders when room selected | `history_panel_test.dart` | 1 |
| HistoryPanel returns SizedBox when no room | `history_panel_test.dart` | 1 |
| Loading state displays spinner | `thread_list_test.dart` | 2 |
| Empty state displays message | `thread_list_test.dart` | 2 |
| Error state displays retry button | `thread_list_test.dart` | 2 |
| Retry button calls invalidate | `thread_list_test.dart` | 2 |
| Thread list renders items | `thread_list_test.dart` | 3 |
| Thread item shows title | `thread_list_item_test.dart` | 3 |
| Thread item truncates long titles | `thread_list_item_test.dart` | 3 |
| Tapping thread updates provider | `thread_list_test.dart` | 4 |
| Selected thread has highlight | `thread_list_test.dart` | 4 |
| Auto-selection sets provider | `auto_selection_test.dart` | 5 |
| Fallback selects first thread | `auto_selection_test.dart` | 5 |
| "New" button clears selection | `history_header_test.dart` | 6 |
| "New" button sets intent | `history_header_test.dart` | 6 |
| Pull-to-refresh triggers invalidate | `refresh_test.dart` | 7 |
| Refresh button triggers invalidate | `refresh_test.dart` | 7 |
| Active run indicator appears | `thread_list_item_test.dart` | 8 |
| Message preview displays | `thread_list_item_test.dart` | 8 |

### Integration Tests

| Test | File | Phase |
|------|------|-------|
| Selecting thread loads Chat messages | `history_chat_test.dart` | 4 |
| "New" button enables Chat input | `history_chat_test.dart` | 6 |
| Sending after "New" creates thread | `history_chat_test.dart` | 6 |

### Accessibility Tests

| Test | File | Phase |
|------|------|-------|
| Thread item has semantic label | `accessibility_test.dart` | 8 |
| Selected state is announced | `accessibility_test.dart` | 8 |
| Meets minimum tap target size | `accessibility_test.dart` | 8 |

### Responsive Tests

| Test | File | Phase |
|------|------|-------|
| Renders on mobile (360px) | `responsive_test.dart` | 8 |
| Renders on tablet (768px) | `responsive_test.dart` | 8 |
| Renders on desktop (1200px) | `responsive_test.dart` | 8 |
| Text scales with font size | `responsive_test.dart` | 8 |

### Coverage Requirements

- **Per phase:** >= 90% coverage for new code
- **Overall (Phase 8):** >= 85% total coverage
- **CI gate:** Tests must pass before merge

### Verification Commands

```bash
# Lint (run after each phase)
flutter analyze
dart format --set-exit-if-changed lib/ test/

# Tests (run after each phase)
flutter test test/ui/history/

# Full test suite (run before PR)
flutter test

# Coverage report
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```
