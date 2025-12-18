# Detail

Inspector panel showing event log, thinking, tool calls, and state.

## Scope

- Thread-scoped
- Real-time updates during runs
- Consolidates related events

## Tabs

| Tab | Content |
|-----|---------|
| Events | Chronological AG-UI events (consolidated) |
| Thinking | Agent reasoning from step events |
| Tool Calls | Invocations with args/results |
| State | Current state as JSON tree |

## Event Consolidation

| Pattern | Consolidated As |
|---------|-----------------|
| TEXT_MESSAGE_START → CONTENT* → END | TEXT_MESSAGE |
| TOOL_CALL_START → ARGS → END → RESULT | TOOL_CALL |
| STEP_STARTED → STEP_FINISHED | STEP |

## Provider Integration

```dart
final detailState = ref.watch(detailPanelProvider);
// Derives from activeRunProvider.rawEvents, latestState
```

**Requires**: ActiveRunState.rawEvents from core_frontend Phase 2.

## UI States

| State | Display |
|-------|---------|
| No thread | "Select a thread" |
| No run | "No run data" |
| Running | Live updating |
| Finished | Static log |

## Actions

Copy, expand, filter, search, pin to PermanentCanvas

## Implementation Phases

| Phase | Goal |
|-------|------|
| 1 | Scaffold, raw events list, consolidation |
| 2 | Tool Calls tab, Thinking tab |
| 3 | State tab (JSON tree), filter/search |
| 4 | Copy, pin, accessibility |
