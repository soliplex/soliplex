# PermanentCanvas

The permanent canvas holds items explicitly pinned by the user. Items persist across app restarts and are accessible from any room or thread.

## Scope

- **Global**: Items are visible regardless of current room/thread
- **Persistent**: Items survive app shutdown and restart
- **User-controlled**: Only user-pinned items appear here (not automatic)
- **Removable**: Users can unpin/remove items at any time

## Comparison with CurrentCanvas

| Aspect | CurrentCanvas | PermanentCanvas |
|--------|---------------|-----------------|
| **Scope** | Thread | Global (all rooms/threads) |
| **Lifecycle** | Ephemeral (cleared on thread switch) | Persistent (survives app restart) |
| **Population** | Automatic (AG-UI events) | Manual (user pins items) |
| **Content** | ActivitySnapshot, StateSnapshot | Pinned messages, code, images |
| **Removal** | Automatic | User-initiated |

## Pinnable Item Types

| Source | Item Type | Icon | Example |
|--------|-----------|------|---------|
| Chat message | Text snippet | `📝` | "The API endpoint is /api/v2/users" |
| Chat message | Code block | `💻` | ```python def foo(): ...``` |
| Chat message | Full message | `💬` | Entire assistant response |
| Chat message | Image | `🖼️` | Generated diagram or chart |
| CurrentCanvas | Snapshot | `📊` | Pinned state/activity snapshot |

## Data Model

```dart
enum PinnedItemType { text, code, message, image, snapshot }

class PinnedItem {
  final String id;
  final PinnedItemType type;
  final String content;
  final String? title;              // User-editable label
  final String? language;           // For code blocks (e.g., "python", "dart")
  final PinSource source;
  final DateTime pinnedAt;
}

class PinSource {
  final String? roomId;
  final String? roomName;
  final String? threadId;
  final String? messageId;
  final DateTime? originalTimestamp;
}
```

## Provider Integration

```dart
// Storage for pinned items (persists to SharedPreferences/Hive)
final pinnedItemsStorageProvider = Provider<PinnedItemsStorage>((ref) =>
  PinnedItemsStorage(),
);

// Pinned items state with actions
final pinnedItemsProvider = StateNotifierProvider<PinnedItemsNotifier, AsyncValue<List<PinnedItem>>>(
  (ref) => PinnedItemsNotifier(ref.watch(pinnedItemsStorageProvider)),
);

class PinnedItemsNotifier extends StateNotifier<AsyncValue<List<PinnedItem>>> {
  /// Load all pinned items from storage
  Future<void> load();

  /// Pin a new item
  Future<void> pin(PinnedItem item);

  /// Remove/unpin an item
  Future<void> unpin(String itemId);

  /// Update item title
  Future<void> updateTitle(String itemId, String title);

  /// Reorder items
  Future<void> reorder(int oldIndex, int newIndex);

  /// Remove all pinned items
  Future<void> clearAll();
}
```

## Pinning Interactions

### From Chat (Message Actions)

On hover (desktop) or long-press (mobile), show pin options:

```
┌─────────────────────────────────────┐
│ Here's the code you requested:      │
│ ```python                           │
│ def calculate():                    │
│     return 42                       │
│ ```                                 │
├─────────────────────────────────────┤
│ [📋 Copy] [📌 Pin Message]          │
│ [📌 Pin Code Block]                 │  ← Only shown when message has code
└─────────────────────────────────────┘
```

**Pin actions:**
- **Pin Message**: Pins the entire message content
- **Pin Code Block**: Pins only the code block (when message contains code)

```dart
void onPinMessage(Message message) {
  final item = PinnedItem(
    id: const Uuid().v4(),
    type: PinnedItemType.message,
    content: message.content,
    title: null,  // User can edit later
    source: PinSource(
      roomId: currentRoom.id,
      roomName: currentRoom.name,
      threadId: currentThread.id,
      messageId: message.id,
      originalTimestamp: message.timestamp,
    ),
    pinnedAt: DateTime.now(),
  );
  ref.read(pinnedItemsProvider.notifier).pin(item);
}
```

### From CurrentCanvas

Ephemeral snapshots can be promoted to permanent:

```
┌─────────────────────────────────────┐
│ StateSnapshot: Search Results       │
│ ┌─────────────────────────────────┐ │
│ │ • Document A (0.95)             │ │
│ │ • Document B (0.87)             │ │
│ └─────────────────────────────────┘ │
│                          [📌 Pin]   │
└─────────────────────────────────────┘
```

## UI Layout

```
┌─────────────────────────────────────────────┐
│ 📌 Pinned Items (3)            [⋮ Menu] [−] │  ← Header: count, menu, collapse
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ 📝 API Endpoint                    [×]  │ │  ← Title + remove button
│ │ The endpoint is /api/v2/users           │ │  ← Content
│ │ ─────────────────────────────────────── │ │
│ │ 💬 General Room • 2 days ago       [📋] │ │  ← Source + copy button
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 💻 Calculate Function              [×]  │ │
│ │ def calculate():                        │ │
│ │     return 42                           │ │
│ │ ─────────────────────────────────────── │ │
│ │ 💬 Code Room • 5 min ago           [📋] │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│         [ + Pin from Chat ]                 │  ← Hint when few items
└─────────────────────────────────────────────┘
```

### Collapsed State

```
┌─────────────────────────────────────────────┐
│ 📌 Pinned Items (3)                     [+] │  ← Expand button
└─────────────────────────────────────────────┘
```

## UI States

### Empty

```
┌─────────────────────────────────────────────┐
│ 📌 Pinned Items                             │
├─────────────────────────────────────────────┤
│                                             │
│            📌                               │
│                                             │
│     No pinned items yet                     │
│                                             │
│   Pin messages from chat to save            │
│   them here for quick reference.            │
│                                             │
└─────────────────────────────────────────────┘
```

### Loading

- Show loading spinner on initial load from storage
- Individual items show inline loading during removal

### Error

- Show error message if storage fails to load
- Retry button to attempt reload

## Item Actions

### Desktop (Hover)

| Action | Trigger | Description |
|--------|---------|-------------|
| **Remove** | Click `×` button | Unpin item with confirmation |
| **Copy** | Click `📋` button | Copy content to clipboard |
| **Edit title** | Click title text | Inline edit the item label |
| **Navigate** | Click source link | Jump to original message (if still exists) |
| **Reorder** | Drag handle | Change item order in list |

### Mobile (Long-Press)

Long-press on a pinned item shows an action menu:

```
┌─────────────────────────────────────┐
│ 📝 API Endpoint                     │
├─────────────────────────────────────┤
│ 📋  Copy                            │
│ ✏️  Edit title                      │
│ 🔗  Go to source                    │
│ 🗑️  Remove                          │
└─────────────────────────────────────┘
```

### Remove Confirmation

When "Remove" is selected (desktop or mobile), show confirmation dialog:

```
┌─────────────────────────────────────┐
│ Remove pinned item?                 │
│                                     │
│ "API Endpoint" will be removed      │
│ from your pinned items.             │
│                                     │
│          [Cancel]  [Remove]         │
└─────────────────────────────────────┘
```

## Header Menu Actions

| Action | Description |
|--------|-------------|
| Clear all | Remove all pinned items (with confirmation) |
| Export | Copy all items as markdown (future) |

## Storage

```dart
class PinnedItemsStorage {
  static const _key = 'pinned_items_v1';

  final SharedPreferences _prefs;

  Future<List<PinnedItem>> loadAll() async {
    final json = _prefs.getString(_key);
    if (json == null) return [];
    return (jsonDecode(json) as List)
        .map((e) => PinnedItem.fromJson(e))
        .toList();
  }

  Future<void> saveAll(List<PinnedItem> items) async {
    final json = jsonEncode(items.map((e) => e.toJson()).toList());
    await _prefs.setString(_key, json);
  }

  Future<void> clear() async {
    await _prefs.remove(_key);
  }
}
```

### Storage Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max items | 100 | Prevent unbounded growth |
| Max content size | 50KB per item | Large code blocks / messages |
| Total storage | 5MB | SharedPreferences practical limit |

When max items reached, show warning before pinning:
> "You've reached the maximum of 100 pinned items. Remove some items to pin more."

## Interaction with Other Components

| Component | Interaction |
|-----------|-------------|
| **Chat** | "Pin" action in message menu adds to PermanentCanvas |
| **CurrentCanvas** | "Pin" button promotes ephemeral snapshot to permanent |
| **core_frontend** | Provides `pinnedItemsProvider` and `pinnedItemsStorageProvider` |

## Dependencies

```yaml
dependencies:
  shared_preferences: ^2.2.0  # Or hive for better performance
  uuid: ^4.0.0                # Generate unique IDs
```

---

## Implementation Plan

### File Structure

```
lib/
├── ui/
│   └── permanent_canvas/
│       ├── permanent_canvas_panel.dart   # Main panel widget
│       ├── pinned_item_card.dart         # Individual item display
│       ├── pinned_item_editor.dart       # Title editing
│       └── empty_canvas_state.dart       # Empty state widget
├── models/
│   └── pinned_item.dart                  # Data model
├── providers/
│   └── pinned_items_provider.dart        # State management
└── services/
    └── pinned_items_storage.dart         # Persistence
```

---

### Phase 1: Basic Display & Storage

**Goal:** Pinned items persist and display correctly.

**Files to create:**
- `lib/models/pinned_item.dart`
- `lib/services/pinned_items_storage.dart`
- `lib/providers/pinned_items_provider.dart`
- `lib/ui/permanent_canvas/permanent_canvas_panel.dart`
- `lib/ui/permanent_canvas/pinned_item_card.dart`
- `test/services/pinned_items_storage_test.dart`
- `test/providers/pinned_items_provider_test.dart`
- `test/ui/permanent_canvas/permanent_canvas_panel_test.dart`

**Steps:**
1. Create `PinnedItem` and `PinSource` data models with JSON serialization
2. Implement `PinnedItemsStorage` with SharedPreferences
3. Create `PinnedItemsNotifier` with `load()`, `pin()`, `unpin()` methods
4. Create `PermanentCanvasPanel` widget that watches `pinnedItemsProvider`
5. Create `PinnedItemCard` to display individual items
6. Implement remove button with confirmation dialog
7. Show empty state when no items
8. Write unit tests for storage and provider
9. Write widget tests for panel
10. Run linting and fix issues

**Tests:**
- `test/services/pinned_items_storage_test.dart`:
  - Unit test: saves and loads items correctly
  - Unit test: handles empty storage
  - Unit test: handles corrupted JSON gracefully
  - Unit test: clear removes all items
- `test/providers/pinned_items_provider_test.dart`:
  - Unit test: pin adds item to list
  - Unit test: unpin removes item from list
  - Unit test: load populates state from storage
- `test/ui/permanent_canvas/permanent_canvas_panel_test.dart`:
  - Widget test: renders empty state when no items
  - Widget test: renders list of pinned items
  - Widget test: remove button triggers unpin

**Verification:**
```bash
flutter analyze
flutter test test/services/ test/providers/ test/ui/permanent_canvas/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] `PinnedItem` model serializes to/from JSON
- [ ] Items persist across app restart
- [ ] Panel displays list of pinned items
- [ ] Empty state shown when no items
- [ ] Remove button unpins item with confirmation
- [ ] `flutter analyze` passes with no errors
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 2: Pinning from Chat

**Goal:** User can pin messages from Chat.

**Files to create:**
- `test/ui/permanent_canvas/pin_from_chat_test.dart`
- `test/integration/chat_canvas_test.dart`

**Steps:**
1. Add "Pin Message" action to Chat message menu
2. Add "Pin Code Block" action (when message contains code)
3. Extract code blocks from markdown content
4. Create `PinnedItem` with correct source metadata
5. Show toast/snackbar confirmation when item pinned
6. Handle pinning when at max items limit
7. Write integration tests for pin flow
8. Run linting and fix issues

**Tests:**
- `test/ui/permanent_canvas/pin_from_chat_test.dart`:
  - Widget test: "Pin Message" action visible in menu
  - Widget test: "Pin Code Block" visible when message has code
  - Widget test: pinning creates item with correct content
  - Widget test: pinning creates item with correct source metadata
  - Widget test: shows confirmation snackbar after pin
  - Widget test: shows warning when at max items
- `test/integration/chat_canvas_test.dart`:
  - Integration test: pinning message adds to PermanentCanvas
  - Integration test: pinned item displays in canvas panel

**Verification:**
```bash
flutter analyze
flutter test test/ui/permanent_canvas/ test/integration/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] "Pin Message" appears in Chat message menu
- [ ] "Pin Code Block" appears when message has code
- [ ] Pinned items appear in PermanentCanvas
- [ ] Source metadata (room, thread) is captured
- [ ] Confirmation shown after pinning
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 3: Item Actions

**Goal:** Full item management capabilities.

**Files to create:**
- `lib/ui/permanent_canvas/pinned_item_editor.dart`
- `test/ui/permanent_canvas/pinned_item_card_test.dart`

**Steps:**
1. Implement copy to clipboard action
2. Implement inline title editing
3. Add syntax highlighting for code blocks
4. Implement "Navigate to source" (deep link to original message)
5. Handle case where source message no longer exists
6. Write widget tests for all actions
7. Run linting and fix issues

**Tests:**
- `test/ui/permanent_canvas/pinned_item_card_test.dart`:
  - Widget test: copy button copies content to clipboard
  - Widget test: clicking title enables edit mode
  - Widget test: saving title updates item
  - Widget test: code blocks have syntax highlighting
  - Widget test: source link triggers navigation
  - Widget test: shows "Source unavailable" when message deleted

**Verification:**
```bash
flutter analyze
flutter test test/ui/permanent_canvas/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Copy button copies content to clipboard
- [ ] Title can be edited inline
- [ ] Code blocks have syntax highlighting
- [ ] Clicking source navigates to original message
- [ ] Graceful handling when source unavailable
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 4: Pinning from CurrentCanvas

**Goal:** Ephemeral snapshots can be promoted to permanent.

**Files to create:**
- `test/integration/current_permanent_canvas_test.dart`

**Steps:**
1. Add "Pin" button to CurrentCanvas snapshot items
2. Convert snapshot to PinnedItem format
3. Handle different snapshot types (Activity, State)
4. Show confirmation when pinned
5. Write integration tests
6. Run linting and fix issues

**Tests:**
- `test/integration/current_permanent_canvas_test.dart`:
  - Integration test: ActivitySnapshot can be pinned
  - Integration test: StateSnapshot can be pinned
  - Integration test: pinned snapshot appears in PermanentCanvas
  - Integration test: snapshot content preserved correctly

**Verification:**
```bash
flutter analyze
flutter test test/integration/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] "Pin" button visible on CurrentCanvas items
- [ ] Snapshots convert to PinnedItem correctly
- [ ] Pinned snapshots display in PermanentCanvas
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 5: Polish

**Goal:** Production-ready quality and UX.

**Files to create:**
- `lib/ui/permanent_canvas/empty_canvas_state.dart`
- `lib/ui/permanent_canvas/item_action_menu.dart`
- `test/ui/permanent_canvas/accessibility_test.dart`
- `test/ui/permanent_canvas/responsive_test.dart`

**Steps:**
1. Implement drag-to-reorder items
2. Implement long-press action menu for mobile
3. Add collapse/expand panel toggle
4. Add header menu with "Clear all" action
5. Refine empty state with illustration
6. Add loading and error states
7. Implement accessibility (semantic labels, focus)
8. Test responsive layout
9. Run full test suite
10. Run linting and fix all warnings

**Tests:**
- `test/ui/permanent_canvas/permanent_canvas_panel_test.dart` (add):
  - Widget test: drag-to-reorder changes item order
  - Widget test: long-press shows action menu on mobile
  - Widget test: action menu contains Copy, Edit, Go to source, Remove
  - Widget test: selecting Remove from menu shows confirmation
  - Widget test: collapse button hides content
  - Widget test: expand button shows content
  - Widget test: "Clear all" removes all items with confirmation
  - Widget test: loading state shows spinner
  - Widget test: error state shows retry button
- `test/ui/permanent_canvas/accessibility_test.dart`:
  - Accessibility test: items have semantic labels
  - Accessibility test: remove button has label
  - Accessibility test: action menu items have labels
  - Accessibility test: meets minimum tap target size
- `test/ui/permanent_canvas/responsive_test.dart`:
  - Widget test: renders on mobile (360px)
  - Widget test: renders on tablet (768px)
  - Widget test: renders on desktop (1200px)
  - Widget test: hover actions visible on desktop
  - Widget test: hover actions hidden on mobile (use long-press instead)

**Verification:**
```bash
flutter analyze
dart format --set-exit-if-changed lib/ test/
flutter test
flutter test --coverage
```

**Documentation:**
- Update CLAUDE.md with PermanentCanvas component file structure
- Document pinning patterns and storage implementation

**Acceptance criteria:**
- [ ] Items can be reordered via drag
- [ ] Long-press shows action menu on mobile
- [ ] Hover shows action buttons on desktop
- [ ] Panel can collapse/expand
- [ ] "Clear all" works with confirmation
- [ ] Empty state looks polished
- [ ] Loading and error states implemented
- [ ] Accessibility tests pass
- [ ] Responsive on all screen sizes
- [ ] `flutter analyze` passes with no warnings
- [ ] `dart format` reports no changes
- [ ] All tests pass
- [ ] Overall test coverage >= 85%
- [ ] CLAUDE.md updated

---

### Phase Summary

| Phase | Goal | Key Deliverable | Tests |
|-------|------|-----------------|-------|
| 1 | Storage & Display | Items persist, panel renders | 3 unit + 3 widget |
| 2 | Pin from Chat | Message pinning works | 6 widget + 2 integration |
| 3 | Item Actions | Copy, edit, navigate | 6 widget |
| 4 | Pin from Canvas | Snapshot pinning works | 4 integration |
| 5 | Polish | Production quality | 9 widget + 4 a11y + 5 responsive |

### Dependencies

```
Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 5
              │
              └─► Phase 4 ─► Phase 5
```

- Phase 2 requires Chat component (for pin action)
- Phase 4 requires CurrentCanvas component
- Phase 5 requires all other phases complete

---

### Future Enhancements (Not in v1)

- Search/filter pinned items
- Export as markdown
- Folders/categories for organization
- Cloud sync (backend persistence)
- Share pinned items
- Pinning from Detail panel (tool results, thinking)

---

## Testing

### Test File Structure

```
test/
├── models/
│   └── pinned_item_test.dart
├── services/
│   └── pinned_items_storage_test.dart
├── providers/
│   └── pinned_items_provider_test.dart
├── ui/
│   └── permanent_canvas/
│       ├── permanent_canvas_panel_test.dart
│       ├── pinned_item_card_test.dart
│       ├── pin_from_chat_test.dart
│       ├── accessibility_test.dart
│       └── responsive_test.dart
└── integration/
    ├── chat_canvas_test.dart
    └── current_permanent_canvas_test.dart
```

### Coverage Requirements

- **Per phase:** >= 90% coverage for new code
- **Overall (Phase 5):** >= 85% total coverage
- **CI gate:** Tests must pass before merge

### Verification Commands

```bash
# Lint (run after each phase)
flutter analyze
dart format --set-exit-if-changed lib/ test/

# Tests (run after each phase)
flutter test test/ui/permanent_canvas/ test/services/ test/providers/

# Full test suite (run before PR)
flutter test

# Coverage report
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```
