# Claude Code Notes

Project-specific instructions for Claude Code when working on this codebase.

## Reference Documentation

- **SOLIPLEX.md** - Backend API documentation for AG-UI integration (endpoints, request/response schemas, state sync)
- **QUICK_AGUI.md** - Notes on the quick_agui Flutter library (issues, workarounds, architecture)
- **APP_FEATURES.md** - Planned, in-progress, and completed app features (feedback chips, notes pad, etc.)
- **GENUI-WIDGETS.md** - Widget system documentation (registry, creating widgets, semantic IDs, limitations)

## Documentation Requirements

- Any newly discovered information about `quick_agui` - especially design shortcomings, bugs, or architectural issues - should be documented in `QUICK_AGUI.md`
- This includes issues like:
  - Concurrency problems (e.g., shared state causing duplicate processing)
  - Event streaming edge cases
  - Tool registration/execution quirks
  - Any workarounds implemented in the app layer to compensate for library limitations
- Backend API discoveries should be documented in `SOLIPLEX.md`
- **Widget system**: When adding new GenUI widgets, update `GENUI-WIDGETS.md`:
  - Add to the registered widgets table
  - Document data schema
  - Add semantic ID logic if widget supports canvas
- **Feature tracking**: When working on new features, update `APP_FEATURES.md`:
  - Move features from "Planned" to "In Progress" when starting work
  - Move features from "In Progress" to "Completed" when done
  - Add implementation notes, files modified, and any gotchas discovered

## Platform-Specific Code (dart:io)

SOLIPLEX must work on **Web**, **Mobile**, and **Desktop**. The `dart:io` package is NOT supported on web.

### Current Platform-Specific Features

| Feature | Approach | Files |
|---------|----------|-------|
| Room Notes | Hidden on web (`kIsWeb` check) | `notes_service*.dart`, `chat_screen.dart` |
| Feedback Storage | Conditional imports (localStorage on web) | `feedback_service*.dart` |

### Naming Convention

- `*_io.dart` - Native implementation using `dart:io`
- `*_web.dart` - Web implementation using `dart:html` or stubs

### Pattern for New Platform-Specific Code

Use conditional imports to provide platform-specific implementations:

```dart
import 'my_service_io.dart' if (dart.library.html) 'my_service_web.dart'
    as platform;

// Call platform functions
final data = await platform.loadData();
await platform.saveData(data);
```

Both `_io.dart` and `_web.dart` files must export the same function signatures.

### When to Use Each Approach

1. **Conditional imports** (like FeedbackService): When the feature should work on web with a different storage mechanism (e.g., localStorage).

2. **Hide UI on web** (like Notes): When the feature fundamentally depends on local file system and doesn't make sense on web. Use `kIsWeb` to hide the UI:
   ```dart
   if (!kIsWeb)
     IconButton(...)
   ```

### Adding New dart:io Features

1. Never import `dart:io` directly in files that could be compiled for web
2. Create `*_io.dart` and `*_web.dart` companion files
3. Use conditional imports in the main service file
4. If UI should be hidden on web, add `kIsWeb` checks in the UI layer
5. Document the feature in this table above
