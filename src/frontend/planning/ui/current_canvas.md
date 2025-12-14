# CurrentCanvas

The current canvas displays the shared state between the frontend and backend during an active agent run. It automatically receives and renders AG-UI snapshot events in real-time.

## Scope

- **Thread-scoped**: Shows state for the current thread only
- **Ephemeral**: Cleared when thread changes or new run starts
- **Automatic**: Populated by AG-UI events (not user-initiated)
- **Real-time**: Updates live as events stream in

## Comparison with PermanentCanvas

| Aspect | CurrentCanvas | PermanentCanvas |
|--------|---------------|-----------------|
| **Scope** | Thread | Global (all rooms/threads) |
| **Lifecycle** | Ephemeral (cleared on thread switch) | Persistent (survives app restart) |
| **Population** | Automatic (AG-UI events) | Manual (user pins items) |
| **Content** | StateSnapshot, ActivitySnapshot | Pinned messages, code, images |
| **Removal** | Automatic | User-initiated |
| **Storage** | In-memory only | SharedPreferences |

## AG-UI Events Handled

| Event | Description | Action |
|-------|-------------|--------|
| `STATE_SNAPSHOT` | Full state replacement | Replace all state items |
| `STATE_DELTA` | Incremental state update | Merge/patch existing state |
| `ACTIVITY_SNAPSHOT` | Full activity status | Replace activity display |
| `ACTIVITY_DELTA` | Incremental activity update | Merge/patch activity |

### Event Flow

```
Backend (AG-UI SSE)
       │
       ▼
┌─────────────────┐
│ ActiveRunNotifier │ ← Parses events, updates state
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ currentCanvasProvider │ ← Derives canvas state from run
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ CurrentCanvasPanel │ ← Renders state items and activity
└─────────────────┘
```

## Data Model

```dart
/// Represents a state item displayed on the canvas
class CanvasStateItem {
  final String id;
  final CanvasItemType type;
  final String title;
  final dynamic content;       // Structured data (varies by type)
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;
}

enum CanvasItemType {
  searchResults,    // List of documents with relevance scores
  document,         // Single document with content
  table,            // Tabular data
  json,             // Arbitrary JSON structure
  text,             // Plain text
  image,            // Image URL
  progress,         // Step list with completion status
  custom,           // Custom renderer based on metadata
}

/// Represents current activity status
class CanvasActivity {
  final String id;
  final ActivityStatus status;
  final String? description;   // e.g., "Searching documents..."
  final double? progress;      // 0.0 - 1.0 for progress bar (optional)
  final DateTime timestamp;
}

enum ActivityStatus {
  idle,
  thinking,
  searching,
  generating,
  toolCall,
  custom,
}

/// Canvas state for a thread
class CurrentCanvasState {
  final String? threadId;
  final List<CanvasStateItem> items;
  final CanvasActivity? activity;
  final bool isRunning;

  static CurrentCanvasState empty() => CurrentCanvasState(
    threadId: null,
    items: [],
    activity: null,
    isRunning: false,
  );
}
```

## Provider Integration

```dart
// Current canvas state - derived from activeRunProvider
final currentCanvasProvider = Provider<CurrentCanvasState>((ref) {
  final runState = ref.watch(activeRunProvider);
  final currentThread = ref.watch(currentThreadProvider);

  // Return empty if no thread or thread mismatch
  if (currentThread == null || runState.threadId != currentThread.id) {
    return CurrentCanvasState.empty();
  }

  return CurrentCanvasState(
    threadId: currentThread.id,
    items: runState.stateItems,
    activity: runState.currentActivity,
    isRunning: runState.status == RunStatus.running,
  );
});
```

### Required Updates to ActiveRunNotifier

The `ActiveRunNotifier` in core_frontend needs to handle snapshot events:

```dart
class ActiveRunState {
  // ... existing fields ...
  final List<CanvasStateItem> stateItems;      // From STATE_SNAPSHOT/DELTA
  final CanvasActivity? currentActivity;        // From ACTIVITY_SNAPSHOT/DELTA
}

// In event handling:
case 'STATE_SNAPSHOT':
  state = state.copyWith(stateItems: parseStateItems(event.data));
  break;
case 'STATE_DELTA':
  state = state.copyWith(stateItems: mergeStateDelta(state.stateItems, event.data));
  break;
case 'ACTIVITY_SNAPSHOT':
  state = state.copyWith(currentActivity: parseActivity(event.data));
  break;
case 'ACTIVITY_DELTA':
  state = state.copyWith(currentActivity: mergeActivityDelta(state.currentActivity, event.data));
  break;
```

## State Item Types

| Type | Content Structure | Renderer |
|------|-------------------|----------|
| `searchResults` | `{results: [{title, score, excerpt}]}` | Ranked list with relevance bars |
| `document` | `{title, content, source?}` | Card with collapsible content |
| `table` | `{columns: [], rows: [[]]}` | DataTable widget |
| `json` | Any valid JSON | Collapsible JSON tree viewer |
| `text` | `{text: "..."}` | Selectable text widget |
| `image` | `{url, alt?, width?, height?}` | Image with optional caption |
| `progress` | `{steps: [{name, status}]}` | Stepper/checklist |
| `custom` | Varies | Based on `metadata.renderer` |

## UI Layout

### Full State (Running with Items)

```
┌─────────────────────────────────────────────┐
│ 📊 Canvas                              [−]  │  ← Header with collapse
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ 🔄 Searching documents...               │ │  ← Activity indicator
│ │ ████████████░░░░░░░░  60%               │ │  ← Progress bar (if provided)
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 🔍 Search Results              [📋][📌] │ │  ← Item header with actions
│ │ ┌─────────────────────────────────────┐ │ │
│ │ │ 1. Document A          ████░ 0.95   │ │ │  ← Relevance score bar
│ │ │ 2. Document B          ███░░ 0.87   │ │ │
│ │ │ 3. Document C          ██░░░ 0.72   │ │ │
│ │ └─────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 📄 Retrieved Context           [📋][📌] │ │
│ │ "The API endpoint for user auth is     │ │
│ │ located at /api/v1/auth..."            │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Collapsed State

```
┌─────────────────────────────────────────────┐
│ 📊 Canvas (2 items)                     [+] │  ← Item count shown
└─────────────────────────────────────────────┘
```

### Activity Only (No State Items Yet)

```
┌─────────────────────────────────────────────┐
│ 📊 Canvas                              [−]  │
├─────────────────────────────────────────────┤
│                                             │
│           🔄 Thinking...                    │
│                                             │
└─────────────────────────────────────────────┘
```

## UI States

| State | Display |
|-------|---------|
| **No thread selected** | Hide panel or show disabled state |
| **Thread selected, idle** | "Start a conversation to see agent activity" |
| **Run active, no snapshots** | Activity indicator centered |
| **Run active, has snapshots** | Activity indicator + state items list |
| **Run finished, has items** | State items remain visible (activity clears) |
| **Run finished, no items** | "No state information from last run" |
| **Collapsed** | Just header bar with item count |

## Item Actions

### Desktop (Hover)

| Action | Trigger | Description |
|--------|---------|-------------|
| **Pin** | Click 📌 button | Copy item to PermanentCanvas |
| **Copy** | Click 📋 button | Copy content to clipboard |
| **Collapse** | Click item header | Toggle item content visibility |

### Mobile (Long-Press)

Long-press on a state item shows an action menu:

```
┌─────────────────────────────────────┐
│ 🔍 Search Results                   │
├─────────────────────────────────────┤
│ 📋  Copy                            │
│ 📌  Pin to Saved Items              │
└─────────────────────────────────────┘
```

## Thread Switch Behavior

When `currentThreadProvider` changes:

1. Canvas automatically clears (provider returns empty state)
2. No explicit cleanup needed in the widget
3. If new thread has an active run, canvas populates from that run's state

```dart
// The provider handles this automatically:
final currentCanvasProvider = Provider<CurrentCanvasState>((ref) {
  final runState = ref.watch(activeRunProvider);
  final currentThread = ref.watch(currentThreadProvider);

  // Thread mismatch = empty canvas
  if (currentThread == null || runState.threadId != currentThread.id) {
    return CurrentCanvasState.empty();
  }
  // ...
});
```

## Run Lifecycle

| Run Event | Canvas Action |
|-----------|---------------|
| `RUN_STARTED` | Clear previous items, show activity |
| `STATE_SNAPSHOT` | Replace all items |
| `STATE_DELTA` | Merge delta into existing items |
| `ACTIVITY_SNAPSHOT` | Update activity display |
| `ACTIVITY_DELTA` | Merge delta into activity |
| `RUN_FINISHED` | Clear activity, keep items visible |
| `RUN_ERROR` | Clear activity, show error indicator |

## Delta Merging Logic

### State Delta

```dart
List<CanvasStateItem> mergeStateDelta(
  List<CanvasStateItem> current,
  Map<String, dynamic> delta,
) {
  final result = List<CanvasStateItem>.from(current);

  // Handle additions
  if (delta['add'] != null) {
    for (final item in delta['add']) {
      result.add(CanvasStateItem.fromJson(item));
    }
  }

  // Handle updates
  if (delta['update'] != null) {
    for (final update in delta['update']) {
      final index = result.indexWhere((i) => i.id == update['id']);
      if (index >= 0) {
        result[index] = result[index].merge(update);
      }
    }
  }

  // Handle removals
  if (delta['remove'] != null) {
    final removeIds = Set<String>.from(delta['remove']);
    result.removeWhere((i) => removeIds.contains(i.id));
  }

  return result;
}
```

### Activity Delta

```dart
CanvasActivity mergeActivityDelta(
  CanvasActivity? current,
  Map<String, dynamic> delta,
) {
  if (current == null) {
    return CanvasActivity.fromJson(delta);
  }
  return current.copyWith(
    status: delta['status'] ?? current.status,
    description: delta['description'] ?? current.description,
    progress: delta['progress'] ?? current.progress,
  );
}
```

## Animations

| Transition | Animation |
|------------|-----------|
| New item appears | Fade in (200ms) + slide down (200ms) |
| Item updates | Brief highlight flash (yellow → transparent, 300ms) |
| Item removed | Fade out (150ms) |
| Activity changes | Cross-fade text (150ms) |
| Progress bar | Smooth width transition (100ms) |
| Collapse/expand | Height animation (200ms) with clip |

## Interaction with Other Components

| Component | Interaction |
|-----------|-------------|
| **Chat** | Sending message triggers run → canvas updates |
| **PermanentCanvas** | "Pin" action copies item to permanent storage |
| **Detail** | Shows full event log; Canvas shows summary |
| **core_frontend** | `activeRunProvider` supplies snapshot data |
| **History** | Thread selection clears/updates canvas |

## Dependencies

```yaml
dependencies:
  flutter_riverpod: ^2.5.0
  # For JSON tree viewer (optional)
  flutter_json_view: ^1.0.0
```

---

## Implementation Plan

### File Structure

```
lib/
├── ui/
│   └── current_canvas/
│       ├── current_canvas_panel.dart     # Main panel widget
│       ├── canvas_activity.dart          # Activity indicator widget
│       ├── canvas_state_item.dart        # Base state item widget
│       ├── item_renderers/
│       │   ├── search_results_renderer.dart
│       │   ├── document_renderer.dart
│       │   ├── table_renderer.dart
│       │   ├── json_renderer.dart
│       │   ├── text_renderer.dart
│       │   ├── image_renderer.dart
│       │   └── progress_renderer.dart
│       └── canvas_item_actions.dart      # Action menu for mobile
├── models/
│   ├── canvas_state_item.dart
│   └── canvas_activity.dart
└── utils/
    └── delta_merge.dart                  # Delta merging logic
```

---

### Phase 1: Basic Scaffold & Activity Display

**Goal:** Canvas shows activity indicator during runs.

**Files to create:**
- `lib/models/canvas_activity.dart`
- `lib/models/canvas_state_item.dart`
- `lib/ui/current_canvas/current_canvas_panel.dart`
- `lib/ui/current_canvas/canvas_activity.dart`
- `test/models/canvas_activity_test.dart`
- `test/ui/current_canvas/current_canvas_panel_test.dart`
- `test/ui/current_canvas/canvas_activity_test.dart`

**Steps:**
1. Create `CanvasActivity` and `CanvasStateItem` data models
2. Create `CurrentCanvasState` class with empty factory
3. Create `currentCanvasProvider` that derives from `activeRunProvider`
4. Create `CurrentCanvasPanel` widget with header and collapse
5. Create `CanvasActivityWidget` to display activity status
6. Show empty states (no thread, idle, etc.)
7. Write unit tests for models
8. Write widget tests for panel and activity
9. Run linting and fix issues

**Tests:**
- `test/models/canvas_activity_test.dart`:
  - Unit test: CanvasActivity fromJson parsing
  - Unit test: CanvasActivity copyWith works correctly
  - Unit test: ActivityStatus enum mapping
- `test/ui/current_canvas/current_canvas_panel_test.dart`:
  - Widget test: shows empty state when no thread
  - Widget test: shows idle message when thread selected but no run
  - Widget test: shows activity when run is active
  - Widget test: collapse button hides content
  - Widget test: expand button shows content
- `test/ui/current_canvas/canvas_activity_test.dart`:
  - Widget test: displays activity description
  - Widget test: displays progress bar when progress provided
  - Widget test: hides progress bar when progress is null

**Verification:**
```bash
flutter analyze
flutter test test/models/ test/ui/current_canvas/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Activity indicator shows during runs
- [ ] Empty states display correctly
- [ ] Panel can collapse/expand
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 2: State Snapshot Rendering

**Goal:** Canvas displays state items from snapshots.

**Files to create:**
- `lib/ui/current_canvas/canvas_state_item.dart`
- `lib/ui/current_canvas/item_renderers/text_renderer.dart`
- `lib/ui/current_canvas/item_renderers/search_results_renderer.dart`
- `lib/ui/current_canvas/item_renderers/document_renderer.dart`
- `test/ui/current_canvas/canvas_state_item_test.dart`
- `test/ui/current_canvas/item_renderers/text_renderer_test.dart`
- `test/ui/current_canvas/item_renderers/search_results_renderer_test.dart`

**Steps:**
1. Create `CanvasStateItemWidget` that dispatches to type-specific renderers
2. Implement `TextRenderer` for simple text items
3. Implement `SearchResultsRenderer` with relevance score bars
4. Implement `DocumentRenderer` with collapsible content
5. Update `CurrentCanvasPanel` to display list of items
6. Add item collapse/expand functionality
7. Write widget tests for each renderer
8. Run linting and fix issues

**Tests:**
- `test/ui/current_canvas/canvas_state_item_test.dart`:
  - Widget test: dispatches to correct renderer based on type
  - Widget test: shows item title in header
  - Widget test: item can collapse/expand
- `test/ui/current_canvas/item_renderers/text_renderer_test.dart`:
  - Widget test: renders text content
  - Widget test: text is selectable
- `test/ui/current_canvas/item_renderers/search_results_renderer_test.dart`:
  - Widget test: renders list of results
  - Widget test: shows relevance score bars
  - Widget test: orders by score descending

**Verification:**
```bash
flutter analyze
flutter test test/ui/current_canvas/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Text items render correctly
- [ ] Search results show with relevance bars
- [ ] Document items show with collapsible content
- [ ] Items can collapse/expand individually
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 3: Additional Renderers & Delta Handling

**Goal:** Support all item types and handle delta updates.

**Files to create:**
- `lib/utils/delta_merge.dart`
- `lib/ui/current_canvas/item_renderers/table_renderer.dart`
- `lib/ui/current_canvas/item_renderers/json_renderer.dart`
- `lib/ui/current_canvas/item_renderers/image_renderer.dart`
- `lib/ui/current_canvas/item_renderers/progress_renderer.dart`
- `test/utils/delta_merge_test.dart`
- `test/ui/current_canvas/item_renderers/table_renderer_test.dart`
- `test/ui/current_canvas/item_renderers/json_renderer_test.dart`

**Steps:**
1. Implement `mergeStateDelta()` function for state updates
2. Implement `mergeActivityDelta()` function for activity updates
3. Implement `TableRenderer` with DataTable
4. Implement `JsonRenderer` with collapsible tree view
5. Implement `ImageRenderer` with loading state
6. Implement `ProgressRenderer` with stepper/checklist
7. Write unit tests for delta merging
8. Write widget tests for each renderer
9. Run linting and fix issues

**Tests:**
- `test/utils/delta_merge_test.dart`:
  - Unit test: mergeStateDelta handles additions
  - Unit test: mergeStateDelta handles updates
  - Unit test: mergeStateDelta handles removals
  - Unit test: mergeStateDelta handles mixed operations
  - Unit test: mergeActivityDelta updates fields
  - Unit test: mergeActivityDelta preserves unset fields
- `test/ui/current_canvas/item_renderers/table_renderer_test.dart`:
  - Widget test: renders table with headers
  - Widget test: renders table rows
  - Widget test: handles empty table
- `test/ui/current_canvas/item_renderers/json_renderer_test.dart`:
  - Widget test: renders JSON tree
  - Widget test: nodes can expand/collapse

**Verification:**
```bash
flutter analyze
flutter test test/utils/ test/ui/current_canvas/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Delta merging works correctly for state
- [ ] Delta merging works correctly for activity
- [ ] Table renderer displays tabular data
- [ ] JSON renderer shows collapsible tree
- [ ] Image renderer shows images with loading
- [ ] Progress renderer shows step completion
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 4: Item Actions & Pin to PermanentCanvas

**Goal:** Users can copy and pin canvas items.

**Files to create:**
- `lib/ui/current_canvas/canvas_item_actions.dart`
- `test/ui/current_canvas/canvas_item_actions_test.dart`
- `test/integration/canvas_pin_test.dart`

**Steps:**
1. Add copy button to item header (desktop hover)
2. Add pin button to item header (desktop hover)
3. Implement long-press action menu for mobile
4. Implement copy to clipboard functionality
5. Implement pin to PermanentCanvas functionality
6. Convert CanvasStateItem to PinnedItem for pinning
7. Show confirmation snackbar after actions
8. Write widget tests for actions
9. Write integration test for pin flow
10. Run linting and fix issues

**Tests:**
- `test/ui/current_canvas/canvas_item_actions_test.dart`:
  - Widget test: copy button visible on hover (desktop)
  - Widget test: pin button visible on hover (desktop)
  - Widget test: long-press shows action menu (mobile)
  - Widget test: copy action copies to clipboard
  - Widget test: pin action calls pinnedItemsProvider
  - Widget test: shows confirmation snackbar
- `test/integration/canvas_pin_test.dart`:
  - Integration test: pinning item adds to PermanentCanvas
  - Integration test: pinned item has correct source metadata

**Verification:**
```bash
flutter analyze
flutter test test/ui/current_canvas/ test/integration/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Copy button works on desktop
- [ ] Pin button works on desktop
- [ ] Long-press menu works on mobile
- [ ] Pinned items appear in PermanentCanvas
- [ ] Confirmation snackbar shown
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 5: Polish

**Goal:** Production-ready quality and UX.

**Files to create:**
- `test/ui/current_canvas/animations_test.dart`
- `test/ui/current_canvas/accessibility_test.dart`
- `test/ui/current_canvas/responsive_test.dart`

**Steps:**
1. Add fade-in animation for new items
2. Add highlight animation for item updates
3. Add fade-out animation for removed items
4. Add smooth transitions for activity changes
5. Add smooth progress bar animation
6. Implement accessibility (semantic labels)
7. Test responsive layout
8. Handle edge cases (very long content, many items)
9. Run full test suite
10. Run linting and fix all warnings

**Tests:**
- `test/ui/current_canvas/animations_test.dart`:
  - Widget test: new item fades in
  - Widget test: updated item highlights
  - Widget test: activity text cross-fades
  - Widget test: progress bar animates smoothly
- `test/ui/current_canvas/accessibility_test.dart`:
  - Accessibility test: items have semantic labels
  - Accessibility test: activity has semantic label
  - Accessibility test: action buttons have labels
  - Accessibility test: meets minimum tap target size
- `test/ui/current_canvas/responsive_test.dart`:
  - Widget test: renders on mobile (360px)
  - Widget test: renders on tablet (768px)
  - Widget test: renders on desktop (1200px)
  - Widget test: long content truncates with "show more"

**Verification:**
```bash
flutter analyze
dart format --set-exit-if-changed lib/ test/
flutter test
flutter test --coverage
```

**Documentation:**
- Update CLAUDE.md with CurrentCanvas component file structure
- Document state item rendering patterns and delta merging

**Acceptance criteria:**
- [ ] Animations are smooth and not jarring
- [ ] Accessibility tests pass
- [ ] Responsive on all screen sizes
- [ ] Long content handled gracefully
- [ ] `flutter analyze` passes with no warnings
- [ ] `dart format` reports no changes
- [ ] All tests pass
- [ ] Overall test coverage >= 85%
- [ ] CLAUDE.md updated

---

### Phase Summary

| Phase | Goal | Key Deliverable | Tests |
|-------|------|-----------------|-------|
| 1 | Scaffold & Activity | Activity indicator works | 3 unit + 8 widget |
| 2 | State Rendering | Items display correctly | 7 widget |
| 3 | Deltas & Renderers | All item types + updates | 6 unit + 5 widget |
| 4 | Item Actions | Copy & pin work | 6 widget + 2 integration |
| 5 | Polish | Production quality | 4 animation + 4 a11y + 4 responsive |

### Dependencies

```
Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 4 ─► Phase 5
```

- Each phase depends on the previous
- Phase 4 requires PermanentCanvas Phase 1 (for pin target)

---

### Future Enhancements (Not in v1)

- Custom renderers via metadata
- Item drag-to-reorder
- Full-screen item view
- Export canvas as image/PDF
- Canvas history (view previous run states)

---

## Testing

### Test File Structure

```
test/
├── models/
│   ├── canvas_activity_test.dart
│   └── canvas_state_item_test.dart
├── utils/
│   └── delta_merge_test.dart
├── ui/
│   └── current_canvas/
│       ├── current_canvas_panel_test.dart
│       ├── canvas_activity_test.dart
│       ├── canvas_state_item_test.dart
│       ├── canvas_item_actions_test.dart
│       ├── animations_test.dart
│       ├── accessibility_test.dart
│       ├── responsive_test.dart
│       └── item_renderers/
│           ├── text_renderer_test.dart
│           ├── search_results_renderer_test.dart
│           ├── document_renderer_test.dart
│           ├── table_renderer_test.dart
│           └── json_renderer_test.dart
└── integration/
    └── canvas_pin_test.dart
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
flutter test test/ui/current_canvas/ test/models/ test/utils/

# Full test suite (run before PR)
flutter test

# Coverage report
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```
