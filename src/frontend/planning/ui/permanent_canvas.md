# PermanentCanvas

User-pinned items that persist across sessions.

## Scope

- Global (all rooms/threads)
- Persistent (SharedPreferences)
- User-controlled

## vs CurrentCanvas

| Aspect | CurrentCanvas | PermanentCanvas |
|--------|---------------|-----------------|
| Scope | Thread | Global |
| Lifecycle | Ephemeral | Persistent |
| Population | Automatic | Manual |

## Provider Integration

```dart
final pinnedItems = ref.watch(pinnedItemsProvider);
// pin(), unpin(), updateTitle(), reorder()
```

## Pin Sources

Chat messages (text, code, image), CurrentCanvas snapshots

## UI States

| State | Display |
|-------|---------|
| Empty | Placeholder + hint |
| Has items | List with actions |

## Actions

Remove, copy, edit title, navigate to source, reorder

## Storage Limits

Max 100 items, 50KB each, 5MB total

## Implementation Phases

| Phase | Goal |
|-------|------|
| 1 | Storage, display, pin from Chat |
| 2 | Pin from CurrentCanvas, item actions |
| 3 | Reorder, polish, accessibility |
