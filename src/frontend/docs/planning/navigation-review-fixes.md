# Navigation Refactor: Review Fixes

Follow-up fixes from code review of `refactor/navigation` branch.

## Issues to Address

### 1. Feature Envy in Thread Selection Persistence

**Severity:** Major
**Effort:** Small (1-2 hours)
**Files:** `room_screen.dart`, `chat_panel.dart`, `threads_provider.dart`

**Problem:** Both RoomScreen and ChatPanel know the full thread selection workflow
(state update + persistence + URL update). ChatPanel awaits persistence while
RoomScreen fires-and-forgets—an inconsistency that could cause subtle bugs.

**Fix:**
Create `selectThreadWithNavigation()` in `threads_provider.dart`:

```dart
void selectThreadWithNavigation({
  required WidgetRef ref,
  required String roomId,
  required String threadId,
  required void Function(String path) navigate,
}) {
  selectAndPersistThread(ref: ref, roomId: roomId, threadId: threadId);
  navigate('/rooms/$roomId?thread=$threadId');
}
```

Update call sites to use this helper. ChatPanel's thread creation still needs
special handling (it creates the thread first), but the selection workflow
after creation can use the shared function.

---

### 2. InitializingSelection Couples HistoryPanel to RoomScreen

**Severity:** Major
**Effort:** Medium (2-3 hours)
**Files:** `history_panel.dart`, `threads_provider.dart`, `room_screen.dart`

**Problem:** `InitializingSelection` exists solely to prevent HistoryPanel from
auto-selecting while RoomScreen initializes. HistoryPanel knows about
RoomScreen's internal lifecycle.

**Fix Options:**

**Option A (Recommended):** Remove auto-selection from HistoryPanel entirely.

- Delete the `NoThreadSelected` auto-selection logic in HistoryPanel
- Let RoomScreen be the single owner of initialization
- HistoryPanel only displays threads and handles user taps
- Remove `InitializingSelection` variant

**Option B:** Keep behavior but document the contract.

- Add doc comment to `InitializingSelection` explaining the protocol
- Less clean but lower effort

Going with Option A aligns with Single Responsibility and removes the coupling.

---

### 3. `_initialized` Flag State Management

**Severity:** Minor
**Effort:** Small (30 min - 1 hour)
**Files:** `room_screen.dart`

**Problem:** The `_initialized` boolean flag + `didUpdateWidget` + post-frame
callback is fragile. There's a window where `_initialized` is false but
re-initialization hasn't run yet.

**Fix:**
Track `_initializedForRoomId` instead of just `_initialized`:

```dart
String? _initializedForRoomId;

Future<void> _initializeThreadSelection() async {
  if (_initializedForRoomId == widget.roomId) return;
  _initializedForRoomId = widget.roomId;
  // ... rest of initialization
}
```

This guards against double-init for the same room and makes the intent clearer.

---

### 4. Result Type Scope

**Severity:** Minor
**Effort:** Trivial (15 min)
**Files:** `result.dart`, `chat_panel.dart`

**Problem:** `Result<T>` is only used in `ChatPanel._withErrorHandling`. Either
expand usage or make it local.

**Fix:**
Move `Result`, `Ok`, and `Err` into `chat_panel.dart` as private classes since
it's only used there. If we need it elsewhere later, we can extract it back.

Alternatively, keep it in `result.dart` but add a `// TODO: expand usage or
remove` comment.

---

### 5. Missing Async Cancellation in RoomScreen

**Severity:** Minor
**Effort:** Small (30 min)
**Files:** `room_screen.dart`

**Problem:** `_initializeThreadSelection()` could complete after widget unmount,
calling `ref.read()` on a disposed widget.

**Fix:**
Add mounted check after each async gap:

```dart
Future<void> _initializeThreadSelection() async {
  if (_initializedForRoomId == widget.roomId) return;
  _initializedForRoomId = widget.roomId;

  final threads = await ref.read(threadsProvider(widget.roomId).future);
  if (!mounted) return;  // <-- Add this

  // ... rest of method, add mounted checks after other awaits
}
```

---

### 6. Desktop Breakpoint Constant Duplication

**Severity:** Minor
**Effort:** Trivial (15 min)
**Files:** `room_screen.dart`, potentially a new constants file

**Problem:** 600px breakpoint is defined locally in RoomScreen and implicitly
used in tests.

**Fix:**
Export the constant or create `lib/core/constants/breakpoints.dart`:

```dart
const double kDesktopBreakpoint = 600;
```

Low priority—only matters if more screens need responsive layouts.

---

## Effort Summary

| Issue | Effort | Priority |
|-------|--------|----------|
| Feature Envy in thread selection | Small (1-2h) | High |
| InitializingSelection coupling | Medium (2-3h) | High |
| `_initialized` flag management | Small (30min-1h) | Medium |
| Result type scope | Trivial (15min) | Low |
| Missing async cancellation | Small (30min) | Medium |
| Breakpoint duplication | Trivial (15min) | Low |

**Total estimated effort:** 5-7 hours

## Recommended Order

1. **InitializingSelection coupling** - Largest impact on design cleanliness
2. **Feature Envy** - Consolidates scattered logic
3. **Async cancellation** - Prevents potential runtime errors
4. **`_initialized` flag** - Improves robustness
5. **Result type scope** - Cleanup
6. **Breakpoint constant** - Cleanup if time permits
