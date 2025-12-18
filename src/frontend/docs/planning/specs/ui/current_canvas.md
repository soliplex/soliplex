# CurrentCanvas

Ephemeral state from AG-UI snapshot events during active runs.

## Scope

- Thread-scoped (cleared on thread switch)
- Automatic from AG-UI events
- Real-time updates

## AG-UI Events

| Event | Action |
|-------|--------|
| `STATE_SNAPSHOT` | Replace all items |
| `STATE_DELTA` | Merge into items |
| `ACTIVITY_SNAPSHOT/DELTA` | Update activity |

## Provider Integration

```dart
// Derives from activeRunProvider.stateItems, currentActivity
final canvasState = ref.watch(currentCanvasProvider);
```

**Requires**: ActiveRunState extensions from core_frontend Phase 2.

## Item Types

searchResults, document, table, json, text, image, progress

## UI States

| State | Display |
|-------|---------|
| No thread | Hidden |
| Idle | Placeholder message |
| Running | Activity + items |
| Finished | Items remain |

## Actions

Pin to PermanentCanvas, copy, collapse

## Implementation Phases

| Phase | Goal |
|-------|------|
| 1 | Scaffold, activity display, basic renderers |
| 2 | All renderers, delta handling |
| 3 | Actions (copy, pin), polish |
