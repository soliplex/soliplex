# History

Thread list for current room with selection and auto-selection.

## Scope

- Room-scoped (reloads on room change)
- Sorted by last activity (most recent first)

## Provider Integration

```dart
final room = ref.watch(currentRoomProvider);
final threads = ref.watch(threadsProvider);
final currentThread = ref.watch(currentThreadProvider);
```

## Auto-Selection

On room change: last-used thread → most recent → none

## UI States

| State | Display |
|-------|---------|
| Loading | Spinner |
| Error | Error + retry |
| Empty | "No conversations yet" |
| Has threads | List with selection highlight |

## Thread Item

Title, relative timestamp, preview, active indicator

## Actions

- **Select**: Update currentThreadProvider
- **New Conversation**: Clear selection, set newThreadIntentProvider
- **Refresh**: Pull-to-refresh

## Implementation Phases

| Phase | Goal |
|-------|------|
| 1 | Widget scaffold, loading/empty/error states |
| 2 | Thread list display, selection, highlight |
| 3 | Auto-selection, new conversation button |
| 4 | Pull-to-refresh, preview, active indicator |
