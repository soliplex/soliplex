# Detail

The Detail panel is an inspector view showing the technical details of an agent run - the raw event log, thinking process, tool calls, and state. It provides deeper visibility into what the agent is doing, useful for debugging and power users.

## Scope

- **Thread-scoped**: Shows details for the current thread's run
- **Inspector view**: More technical than Chat or CurrentCanvas
- **Real-time**: Updates live as events stream in
- **Consolidated**: Groups related events to reduce noise

## Comparison with Other Components

| Component | Purpose | Content |
|-----------|---------|---------|
| **Chat** | Conversation | User/assistant messages |
| **CurrentCanvas** | Visual state | State snapshots rendered visually |
| **Detail** | Inspector/debug | Raw events, thinking, tool calls, state JSON |

## Tab Structure

The Detail panel has four tabs:

| Tab | Content |
|-----|---------|
| **Events** | Chronological log of all AG-UI events (consolidated) |
| **Thinking** | Agent's reasoning process extracted from steps |
| **Tool Calls** | List of tool invocations with arguments and results |
| **State** | Current state as JSON tree |

## UI Layout

### Panel Structure

```
┌─────────────────────────────────────────────────┐
│ 🔍 Detail                                  [−]  │  ← Header with collapse
├────────┬──────────┬────────────┬────────────────┤
│ Events │ Thinking │ Tool Calls │ State          │  ← Tab bar
├────────┴──────────┴────────────┴────────────────┤
│                                                 │
│  [Selected tab content]                         │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Events Tab

```
┌─────────────────────────────────────────────────┐
│ Events (23)                      [Filter ▼] [🔍]│  ← Count, filter, search
├─────────────────────────────────────────────────┤
│ ┌ 10:23:45.123 ──────────────────────────────┐  │
│ │ ▶ RUN_STARTED                         [📋] │  │  ← Expand + copy
│ │   runId: "run_abc123"                      │  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌ 10:23:45.456 ──────────────────────────────┐  │
│ │ ▶ STEP_STARTED                        [📋] │  │
│ │   stepId: "step_1", name: "analyze"        │  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌ 10:23:46.789 ──────────────────────────────┐  │
│ │ ▼ TEXT_MESSAGE (47 events)            [📋] │  │  ← Consolidated
│ │   role: "assistant"                        │  │
│ │   content: "Based on my analysis..."       │  │
│ │   ─────────────────────────────────────    │  │
│ │   [Show 47 raw events]                     │  │  ← Expand raw
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌ 10:23:48.012 ──────────────────────────────┐  │
│ │ ▶ TOOL_CALL                           [📋] │  │
│ │   tool: "search_documents" → ✓ success     │  │
│ │   duration: 245ms                          │  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌ 10:23:52.345 ──────────────────────────────┐  │
│ │ ▶ RUN_FINISHED                        [📋] │  │
│ │   status: "completed"                      │  │
│ └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Thinking Tab

```
┌─────────────────────────────────────────────────┐
│ Thinking (3 steps)                              │
├─────────────────────────────────────────────────┤
│ ┌ Step 1: Analyze Query ─────────────────────┐  │
│ │ The user is asking about API endpoints.    │  │
│ │ I need to:                                 │  │
│ │ 1. Search the documentation                │  │
│ │ 2. Find relevant endpoints                 │  │
│ │ 3. Provide examples                        │  │
│ │                              10:23:45.500  │  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌ Step 2: Search Documents ──────────────────┐  │
│ │ Searching for "API authentication"...      │  │
│ │ Found 3 relevant documents with scores:    │  │
│ │ - Auth Guide (0.95)                        │  │
│ │ - API Reference (0.87)                     │  │
│ │ - Examples (0.72)                          │  │
│ │                              10:23:47.200  │  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌ Step 3: Generate Response ─────────────────┐  │
│ │ Based on the search results, I'll explain  │  │
│ │ the /api/v1/auth endpoint with examples... │  │
│ │                              10:23:51.800  │  │
│ └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Tool Calls Tab

```
┌─────────────────────────────────────────────────┐
│ Tool Calls (2)                                  │
├─────────────────────────────────────────────────┤
│ ┌ 🔧 search_documents ─────────── ✓ Success ──┐ │
│ │ ▼ Arguments                            [📋] │ │
│ │   {                                         │ │
│ │     "query": "API authentication",          │ │
│ │     "limit": 5                              │ │
│ │   }                                         │ │
│ │ ▼ Result                               [📋] │ │
│ │   {                                         │ │
│ │     "documents": [                          │ │
│ │       {"title": "Auth Guide", "score": 0.95}│ │
│ │     ],                                      │ │
│ │     "total": 3                              │ │
│ │   }                                         │ │
│ │ ──────────────────────────────────────────  │ │
│ │ Started: 10:23:48.012  Duration: 245ms      │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌ 🔧 get_document ─────────────── ✓ Success ──┐ │
│ │ ▶ Arguments (click to expand)               │ │
│ │ ▶ Result (click to expand)                  │ │
│ │ Started: 10:23:49.100  Duration: 89ms       │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌ 🔧 invalid_tool ─────────────── ✗ Error ────┐ │
│ │ ▶ Arguments                                 │ │
│ │ ▼ Error                                [📋] │ │
│ │   "Tool 'invalid_tool' not found"           │ │
│ │ Started: 10:23:50.500  Duration: 12ms       │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### State Tab

```
┌─────────────────────────────────────────────────┐
│ State                    [📋 Copy] [📌 Pin]     │
├─────────────────────────────────────────────────┤
│ ▼ {                                             │
│     ▼ "searchResults": [                        │
│         ▼ {                                     │
│             "title": "Authentication Guide",    │
│             "score": 0.95,                      │
│             "excerpt": "The auth endpoint..."   │
│           },                                    │
│         ▶ { ... },                              │
│         ▶ { ... }                               │
│       ],                                        │
│     ▼ "context": {                              │
│         "roomId": "general",                    │
│         "threadId": "thread_123",               │
│         "runId": "run_abc"                      │
│       },                                        │
│     "timestamp": "2024-01-15T10:23:52Z"         │
│   }                                             │
└─────────────────────────────────────────────────┘
```

## Event Consolidation

To reduce noise, related events are consolidated into single entries:

| Event Pattern | Consolidated As | Shows |
|---------------|-----------------|-------|
| TEXT_MESSAGE_START → N × TEXT_MESSAGE_CONTENT → TEXT_MESSAGE_END | `TEXT_MESSAGE` | Final content, event count |
| Multiple TEXT_MESSAGE_CHUNK | `TEXT_MESSAGE` | Accumulated text |
| TOOL_CALL_START → TOOL_CALL_ARGS → TOOL_CALL_END → TOOL_CALL_RESULT | `TOOL_CALL` | Tool name, args, result, duration |
| Multiple STATE_DELTA after STATE_SNAPSHOT | Keep separate or show latest | Delta count badge |
| Multiple ACTIVITY_DELTA | Show latest | - |
| STEP_STARTED → STEP_FINISHED | `STEP` | Step name, duration |

### Consolidation Logic

```dart
List<ConsolidatedEvent> consolidateEvents(List<RawAgUiEvent> raw) {
  final result = <ConsolidatedEvent>[];
  final buffer = EventConsolidationBuffer();

  for (final event in raw) {
    switch (event.type) {
      case 'TEXT_MESSAGE_START':
        buffer.startTextMessage(event);
        break;
      case 'TEXT_MESSAGE_CONTENT':
      case 'TEXT_MESSAGE_CHUNK':
        buffer.appendTextContent(event);
        break;
      case 'TEXT_MESSAGE_END':
        result.add(buffer.finishTextMessage(event));
        break;
      case 'TOOL_CALL_START':
        buffer.startToolCall(event);
        break;
      case 'TOOL_CALL_ARGS':
        buffer.setToolArgs(event);
        break;
      case 'TOOL_CALL_END':
        buffer.endToolCall(event);
        break;
      case 'TOOL_CALL_RESULT':
        result.add(buffer.finishToolCall(event));
        break;
      default:
        // Non-consolidatable events pass through
        result.add(ConsolidatedEvent.single(event));
    }
  }

  // Flush any incomplete buffers
  result.addAll(buffer.flush());

  return result;
}
```

## Data Model

```dart
/// Raw AG-UI event as received from stream
class RawAgUiEvent {
  final String type;
  final String? id;
  final DateTime timestamp;
  final Map<String, dynamic> data;
}

/// Consolidated event for display in Events tab
class ConsolidatedEvent {
  final String type;              // Display type (e.g., "TEXT_MESSAGE", "TOOL_CALL")
  final String? id;
  final DateTime startTime;
  final DateTime? endTime;
  final Duration? duration;
  final Map<String, dynamic> displayData;  // Type-specific summary
  final int rawEventCount;
  final List<RawAgUiEvent>? rawEvents;     // For "show raw events" expansion

  factory ConsolidatedEvent.single(RawAgUiEvent event) => ...;
}

/// Tool call with full lifecycle for Tool Calls tab
class ToolCallDetail {
  final String id;
  final String toolName;
  final Map<String, dynamic>? arguments;
  final dynamic result;
  final ToolCallStatus status;
  final DateTime startTime;
  final DateTime? endTime;
  final Duration? duration;
  final String? error;
}

enum ToolCallStatus { pending, success, error }

/// Thinking step for Thinking tab
class ThinkingStep {
  final String id;
  final String? name;
  final String content;
  final DateTime timestamp;
  final bool isComplete;
}

/// Detail panel state
class DetailPanelState {
  final String? threadId;
  final List<ConsolidatedEvent> events;
  final List<ThinkingStep> thinkingSteps;
  final List<ToolCallDetail> toolCalls;
  final Map<String, dynamic>? currentState;
  final bool isRunning;
  final String? error;

  static DetailPanelState empty() => DetailPanelState(
    threadId: null,
    events: [],
    thinkingSteps: [],
    toolCalls: [],
    currentState: null,
    isRunning: false,
    error: null,
  );
}
```

## Provider Integration

```dart
// Detail panel state - processes raw events from activeRunProvider
final detailPanelProvider = Provider<DetailPanelState>((ref) {
  final runState = ref.watch(activeRunProvider);
  final currentThread = ref.watch(currentThreadProvider);

  // Return empty if no thread or thread mismatch
  if (currentThread == null || runState.threadId != currentThread.id) {
    return DetailPanelState.empty();
  }

  return DetailPanelState(
    threadId: currentThread.id,
    events: consolidateEvents(runState.rawEvents),
    thinkingSteps: extractThinkingSteps(runState.rawEvents),
    toolCalls: extractToolCalls(runState.rawEvents),
    currentState: runState.latestState,
    isRunning: runState.status == RunStatus.running,
    error: runState.error,
  );
});

// Selected tab state
final detailTabProvider = StateProvider<DetailTab>((ref) => DetailTab.events);

enum DetailTab { events, thinking, toolCalls, state }
```

### Required Updates to ActiveRunNotifier

The `ActiveRunNotifier` in core_frontend needs to store raw events:

```dart
class ActiveRunState {
  // ... existing fields ...
  final List<RawAgUiEvent> rawEvents;      // All raw events for Detail panel
  final Map<String, dynamic>? latestState; // Latest STATE_SNAPSHOT
}

// In event handling - store all raw events:
void _handleEvent(AgUiEvent event) {
  // Store raw event for Detail panel
  state = state.copyWith(
    rawEvents: [...state.rawEvents, RawAgUiEvent.fromAgUi(event)],
  );

  // ... existing event handling for Chat, Canvas, etc. ...
}
```

## UI States

| State | Display |
|-------|---------|
| **No thread selected** | "Select a thread to view details" |
| **Thread selected, no run history** | "No run data available for this thread" |
| **Run active** | Live updating, activity indicator in header |
| **Run finished** | Static log, shows duration in header |
| **Run error** | Error tab highlighted, error details shown |
| **Collapsed** | Just header bar |

## Event Filtering

### Filter Options

| Filter | Description |
|--------|-------------|
| **All** | Show all events |
| **Messages** | TEXT_MESSAGE_* events only |
| **Tool Calls** | TOOL_CALL_* events only |
| **State** | STATE_SNAPSHOT, STATE_DELTA only |
| **Steps** | STEP_STARTED, STEP_FINISHED only |
| **Errors** | RUN_ERROR, failed tool calls only |
| **Lifecycle** | RUN_STARTED, RUN_FINISHED, RUN_ERROR |

### Search

- Text search across event content
- Highlights matching text in results
- Search scope: current tab only

## Item Actions

### Desktop (Hover)

| Action | Trigger | Description |
|--------|---------|-------------|
| **Copy** | Click 📋 button | Copy event/item JSON to clipboard |
| **Expand** | Click event row | Toggle details visibility |
| **Show raw** | Click "Show N raw events" | Expand consolidated events |
| **Pin** | Click 📌 button (State tab) | Pin state to PermanentCanvas |

### Mobile (Long-Press)

Long-press on an event or item shows action menu:

```
┌─────────────────────────────────────┐
│ TEXT_MESSAGE                        │
├─────────────────────────────────────┤
│ 📋  Copy as JSON                    │
│ 📋  Copy content only               │
│ 📌  Pin to Saved Items              │
└─────────────────────────────────────┘
```

## Thread Switch Behavior

When `currentThreadProvider` changes:

1. Detail panel clears (provider returns empty state)
2. If new thread has run history, loads that data
3. Tab selection resets to Events

```dart
// The provider handles this automatically
final detailPanelProvider = Provider<DetailPanelState>((ref) {
  final currentThread = ref.watch(currentThreadProvider);

  // Thread mismatch = empty detail
  if (currentThread == null || runState.threadId != currentThread.id) {
    return DetailPanelState.empty();
  }
  // ...
});
```

## Interaction with Other Components

| Component | Interaction |
|-----------|-------------|
| **Chat** | Chat shows messages; Detail shows raw TEXT_MESSAGE events |
| **CurrentCanvas** | Canvas shows visual state; Detail shows state JSON |
| **PermanentCanvas** | Can pin state or tool results from Detail |
| **core_frontend** | `activeRunProvider` supplies raw events |
| **History** | Thread selection updates Detail panel |

## Dependencies

```yaml
dependencies:
  flutter_riverpod: ^2.5.0
  flutter_json_view: ^1.0.0    # JSON tree viewer for State tab
```

---

## Implementation Plan

### File Structure

```
lib/
├── ui/
│   └── detail/
│       ├── detail_panel.dart           # Main panel with tabs
│       ├── detail_header.dart          # Header with collapse
│       ├── tabs/
│       │   ├── events_tab.dart         # Events list
│       │   ├── thinking_tab.dart       # Thinking steps
│       │   ├── tool_calls_tab.dart     # Tool call list
│       │   └── state_tab.dart          # JSON state viewer
│       ├── widgets/
│       │   ├── event_row.dart          # Single event display
│       │   ├── consolidated_event.dart # Consolidated event with expand
│       │   ├── tool_call_card.dart     # Tool call with args/result
│       │   ├── thinking_step_card.dart # Thinking step display
│       │   └── event_filter.dart       # Filter dropdown
│       └── detail_actions.dart         # Action menu for mobile
├── models/
│   ├── raw_agui_event.dart
│   ├── consolidated_event.dart
│   ├── tool_call_detail.dart
│   └── thinking_step.dart
├── providers/
│   └── detail_panel_provider.dart
└── utils/
    ├── event_consolidation.dart        # Consolidation logic
    ├── thinking_extraction.dart        # Extract thinking from events
    └── tool_call_extraction.dart       # Extract tool calls from events
```

---

### Phase 1: Basic Scaffold & Events List

**Goal:** Detail panel shows raw events (no consolidation yet).

**Files to create:**
- `lib/models/raw_agui_event.dart`
- `lib/providers/detail_panel_provider.dart`
- `lib/ui/detail/detail_panel.dart`
- `lib/ui/detail/detail_header.dart`
- `lib/ui/detail/tabs/events_tab.dart`
- `lib/ui/detail/widgets/event_row.dart`
- `test/models/raw_agui_event_test.dart`
- `test/ui/detail/detail_panel_test.dart`
- `test/ui/detail/tabs/events_tab_test.dart`

**Steps:**
1. Create `RawAgUiEvent` model with JSON serialization
2. Create `DetailPanelState` model
3. Create `detailPanelProvider` that derives from `activeRunProvider`
4. Create `DetailPanel` widget with tab bar (Events tab only initially)
5. Create `EventsTab` with simple list of raw events
6. Create `EventRow` widget to display single event
7. Implement collapse/expand for panel
8. Show empty states
9. Write unit tests for models
10. Write widget tests for panel and events tab
11. Run linting and fix issues

**Tests:**
- `test/models/raw_agui_event_test.dart`:
  - Unit test: fromJson parsing for each event type
  - Unit test: timestamp parsing
- `test/ui/detail/detail_panel_test.dart`:
  - Widget test: shows empty state when no thread
  - Widget test: shows events tab by default
  - Widget test: collapse button hides content
  - Widget test: tab bar switches content
- `test/ui/detail/tabs/events_tab_test.dart`:
  - Widget test: renders list of events
  - Widget test: shows event type and timestamp
  - Widget test: event row expands on tap

**Verification:**
```bash
flutter analyze
flutter test test/models/ test/ui/detail/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Detail panel renders with tabs
- [ ] Events tab shows raw events
- [ ] Events can expand to show details
- [ ] Empty states display correctly
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 2: Event Consolidation

**Goal:** Related events are consolidated into single entries.

**Files to create:**
- `lib/models/consolidated_event.dart`
- `lib/utils/event_consolidation.dart`
- `lib/ui/detail/widgets/consolidated_event.dart`
- `test/utils/event_consolidation_test.dart`
- `test/ui/detail/widgets/consolidated_event_test.dart`

**Steps:**
1. Create `ConsolidatedEvent` model
2. Implement `EventConsolidationBuffer` for tracking in-progress consolidations
3. Implement `consolidateEvents()` function
4. Handle TEXT_MESSAGE consolidation (START → CONTENT* → END)
5. Handle TOOL_CALL consolidation (START → ARGS → END → RESULT)
6. Handle STEP consolidation (STARTED → FINISHED)
7. Create `ConsolidatedEventWidget` with "Show N raw events" expansion
8. Update `EventsTab` to use consolidated events
9. Write unit tests for consolidation logic
10. Write widget tests for consolidated display
11. Run linting and fix issues

**Tests:**
- `test/utils/event_consolidation_test.dart`:
  - Unit test: consolidates TEXT_MESSAGE events
  - Unit test: consolidates TOOL_CALL events
  - Unit test: consolidates STEP events
  - Unit test: passes through non-consolidatable events
  - Unit test: handles incomplete sequences (e.g., START without END)
  - Unit test: calculates duration correctly
  - Unit test: counts raw events correctly
- `test/ui/detail/widgets/consolidated_event_test.dart`:
  - Widget test: shows consolidated event summary
  - Widget test: shows raw event count
  - Widget test: "Show raw events" expands list
  - Widget test: expanded list shows individual events

**Verification:**
```bash
flutter analyze
flutter test test/utils/ test/ui/detail/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] TEXT_MESSAGE events consolidate correctly
- [ ] TOOL_CALL events consolidate correctly
- [ ] STEP events consolidate correctly
- [ ] "Show raw events" expands to show individual events
- [ ] Duration calculated correctly
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 3: Tool Calls Tab

**Goal:** Dedicated tab showing tool calls with arguments and results.

**Files to create:**
- `lib/models/tool_call_detail.dart`
- `lib/utils/tool_call_extraction.dart`
- `lib/ui/detail/tabs/tool_calls_tab.dart`
- `lib/ui/detail/widgets/tool_call_card.dart`
- `test/models/tool_call_detail_test.dart`
- `test/utils/tool_call_extraction_test.dart`
- `test/ui/detail/tabs/tool_calls_tab_test.dart`

**Steps:**
1. Create `ToolCallDetail` model with status enum
2. Implement `extractToolCalls()` function
3. Create `ToolCallsTab` widget
4. Create `ToolCallCard` with expandable arguments/result sections
5. Show tool status (pending, success, error) with icons
6. Show duration for completed calls
7. Handle error display for failed tool calls
8. Write unit tests for extraction logic
9. Write widget tests for tab and card
10. Run linting and fix issues

**Tests:**
- `test/models/tool_call_detail_test.dart`:
  - Unit test: fromEvents creates correct model
  - Unit test: status enum mapping
- `test/utils/tool_call_extraction_test.dart`:
  - Unit test: extracts tool calls from events
  - Unit test: handles successful tool calls
  - Unit test: handles failed tool calls
  - Unit test: handles pending tool calls (no result yet)
  - Unit test: calculates duration
- `test/ui/detail/tabs/tool_calls_tab_test.dart`:
  - Widget test: renders list of tool calls
  - Widget test: shows tool name and status
  - Widget test: success status shows green checkmark
  - Widget test: error status shows red X
  - Widget test: arguments section expands
  - Widget test: result section expands
  - Widget test: error message displays for failed calls

**Verification:**
```bash
flutter analyze
flutter test test/models/ test/utils/ test/ui/detail/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Tool Calls tab shows all tool invocations
- [ ] Arguments and results are expandable
- [ ] Status icons indicate success/error
- [ ] Duration shown for completed calls
- [ ] Error messages shown for failed calls
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 4: Thinking Tab

**Goal:** Dedicated tab showing agent's reasoning process.

**Files to create:**
- `lib/models/thinking_step.dart`
- `lib/utils/thinking_extraction.dart`
- `lib/ui/detail/tabs/thinking_tab.dart`
- `lib/ui/detail/widgets/thinking_step_card.dart`
- `test/models/thinking_step_test.dart`
- `test/utils/thinking_extraction_test.dart`
- `test/ui/detail/tabs/thinking_tab_test.dart`

**Steps:**
1. Create `ThinkingStep` model
2. Implement `extractThinkingSteps()` function (from STEP events or specific thinking events)
3. Create `ThinkingTab` widget
4. Create `ThinkingStepCard` with step name and content
5. Show timestamps for each step
6. Handle streaming thinking (in-progress steps)
7. Write unit tests for extraction logic
8. Write widget tests for tab and card
9. Run linting and fix issues

**Tests:**
- `test/models/thinking_step_test.dart`:
  - Unit test: fromEvents creates correct model
  - Unit test: handles complete and incomplete steps
- `test/utils/thinking_extraction_test.dart`:
  - Unit test: extracts thinking from STEP events
  - Unit test: extracts content from step data
  - Unit test: handles steps without names
  - Unit test: preserves order
- `test/ui/detail/tabs/thinking_tab_test.dart`:
  - Widget test: renders list of thinking steps
  - Widget test: shows step name as header
  - Widget test: shows step content
  - Widget test: shows timestamp
  - Widget test: shows "thinking..." for in-progress steps
  - Widget test: empty state when no thinking steps

**Verification:**
```bash
flutter analyze
flutter test test/models/ test/utils/ test/ui/detail/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Thinking tab shows agent reasoning
- [ ] Steps show name, content, timestamp
- [ ] In-progress steps show indicator
- [ ] Empty state when no thinking data
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 5: State Tab

**Goal:** Dedicated tab showing current state as JSON tree.

**Files to create:**
- `lib/ui/detail/tabs/state_tab.dart`
- `test/ui/detail/tabs/state_tab_test.dart`

**Steps:**
1. Create `StateTab` widget with JSON tree viewer
2. Use `flutter_json_view` or similar package for tree display
3. Add copy button to copy entire state
4. Add pin button to pin state to PermanentCanvas
5. Handle empty state (no state data)
6. Handle large state (virtualization if needed)
7. Write widget tests for state tab
8. Run linting and fix issues

**Tests:**
- `test/ui/detail/tabs/state_tab_test.dart`:
  - Widget test: renders JSON tree
  - Widget test: nodes can expand/collapse
  - Widget test: copy button copies JSON to clipboard
  - Widget test: pin button pins to PermanentCanvas
  - Widget test: empty state when no state data
  - Widget test: handles nested objects
  - Widget test: handles arrays

**Verification:**
```bash
flutter analyze
flutter test test/ui/detail/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] State tab shows JSON tree
- [ ] Tree nodes can expand/collapse
- [ ] Copy button works
- [ ] Pin button works
- [ ] Empty state displays correctly
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 6: Filtering & Search

**Goal:** Users can filter and search events.

**Files to create:**
- `lib/ui/detail/widgets/event_filter.dart`
- `lib/ui/detail/widgets/event_search.dart`
- `lib/providers/detail_filter_provider.dart`
- `test/ui/detail/widgets/event_filter_test.dart`
- `test/ui/detail/widgets/event_search_test.dart`

**Steps:**
1. Create `DetailFilterProvider` to track filter state
2. Create `EventFilter` dropdown widget
3. Implement filter logic (by event type)
4. Create `EventSearch` widget with text field
5. Implement search logic (text match in event content)
6. Highlight search matches in results
7. Add filter/search to Events tab header
8. Write widget tests for filter and search
9. Run linting and fix issues

**Tests:**
- `test/ui/detail/widgets/event_filter_test.dart`:
  - Widget test: filter dropdown shows options
  - Widget test: selecting filter updates list
  - Widget test: "All" shows all events
  - Widget test: "Messages" shows only TEXT_MESSAGE
  - Widget test: "Tool Calls" shows only TOOL_CALL
  - Widget test: "Errors" shows only errors
- `test/ui/detail/widgets/event_search_test.dart`:
  - Widget test: search field accepts input
  - Widget test: search filters events by content
  - Widget test: search highlights matches
  - Widget test: clearing search shows all events

**Verification:**
```bash
flutter analyze
flutter test test/ui/detail/
flutter test --coverage
```

**Acceptance criteria:**
- [ ] Filter dropdown filters events by type
- [ ] Search filters events by content
- [ ] Search highlights matches
- [ ] Filter and search can be combined
- [ ] `flutter analyze` passes
- [ ] All tests pass
- [ ] Test coverage >= 90% for new code

---

### Phase 7: Polish

**Goal:** Production-ready quality and UX.

**Files to create:**
- `lib/ui/detail/detail_actions.dart`
- `test/ui/detail/accessibility_test.dart`
- `test/ui/detail/responsive_test.dart`

**Steps:**
1. Add copy buttons to all copyable items
2. Implement long-press action menu for mobile
3. Add pin action for tool results and state
4. Implement accessibility (semantic labels)
5. Test responsive layout
6. Handle edge cases (very long content, many events)
7. Add loading indicator for live updates
8. Run full test suite
9. Run linting and fix all warnings

**Tests:**
- `test/ui/detail/detail_actions_test.dart`:
  - Widget test: copy button copies to clipboard
  - Widget test: long-press shows action menu (mobile)
  - Widget test: pin action works
  - Widget test: confirmation snackbar shown
- `test/ui/detail/accessibility_test.dart`:
  - Accessibility test: tabs have semantic labels
  - Accessibility test: events have semantic labels
  - Accessibility test: action buttons have labels
  - Accessibility test: meets minimum tap target size
- `test/ui/detail/responsive_test.dart`:
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
- Update CLAUDE.md with Detail component file structure
- Document event consolidation patterns and data models

**Acceptance criteria:**
- [ ] Copy works for all copyable items
- [ ] Long-press menu works on mobile
- [ ] Pin works for tool results and state
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
| 1 | Scaffold & Events | Raw event list | 2 unit + 5 widget |
| 2 | Consolidation | Events consolidated | 7 unit + 4 widget |
| 3 | Tool Calls Tab | Tool call display | 2 unit + 3 unit + 7 widget |
| 4 | Thinking Tab | Thinking display | 2 unit + 4 unit + 6 widget |
| 5 | State Tab | JSON viewer | 7 widget |
| 6 | Filter & Search | Event filtering | 6 + 4 widget |
| 7 | Polish | Production quality | 4 actions + 4 a11y + 4 responsive |

### Dependencies

```
Phase 1 ─► Phase 2 ─► Phase 6 ─► Phase 7
    │
    ├─► Phase 3 ─► Phase 7
    │
    ├─► Phase 4 ─► Phase 7
    │
    └─► Phase 5 ─► Phase 7
```

- Phases 3, 4, 5 can be done in parallel after Phase 1
- Phase 6 depends on Phase 2 (needs consolidated events)
- Phase 7 requires all other phases complete

---

### Future Enhancements (Not in v1)

- Event export (download as JSON)
- Event comparison (diff between runs)
- Time-based visualization (timeline chart)
- Performance metrics (token counts, latencies)
- Event replay (step through events)
- Link to Chat message from event

---

## Testing

### Test File Structure

```
test/
├── models/
│   ├── raw_agui_event_test.dart
│   ├── consolidated_event_test.dart
│   ├── tool_call_detail_test.dart
│   └── thinking_step_test.dart
├── utils/
│   ├── event_consolidation_test.dart
│   ├── tool_call_extraction_test.dart
│   └── thinking_extraction_test.dart
├── ui/
│   └── detail/
│       ├── detail_panel_test.dart
│       ├── tabs/
│       │   ├── events_tab_test.dart
│       │   ├── thinking_tab_test.dart
│       │   ├── tool_calls_tab_test.dart
│       │   └── state_tab_test.dart
│       ├── widgets/
│       │   ├── event_row_test.dart
│       │   ├── consolidated_event_test.dart
│       │   ├── tool_call_card_test.dart
│       │   ├── thinking_step_card_test.dart
│       │   ├── event_filter_test.dart
│       │   └── event_search_test.dart
│       ├── detail_actions_test.dart
│       ├── accessibility_test.dart
│       └── responsive_test.dart
└── integration/
    └── detail_pin_test.dart
```

### Coverage Requirements

- **Per phase:** >= 90% coverage for new code
- **Overall (Phase 7):** >= 85% total coverage
- **CI gate:** Tests must pass before merge

### Verification Commands

```bash
# Lint (run after each phase)
flutter analyze
dart format --set-exit-if-changed lib/ test/

# Tests (run after each phase)
flutter test test/ui/detail/ test/models/ test/utils/

# Full test suite (run before PR)
flutter test

# Coverage report
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```
