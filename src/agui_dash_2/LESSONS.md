# Lessons Learned - AG-UI Dashboard

## Widget Registry Pattern

### 1. Always Handle Flexible Data Types from Agents

**Problem**: Agents may send numeric values as strings instead of numbers.

```dart
// BAD - assumes data type
latitude: (data['latitude'] as num?)?.toDouble(),

// GOOD - handles both string and number
static double? _parseDouble(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}
```

**Lesson**: When parsing JSON data from agents, never assume the exact type. Create helper functions that handle multiple representations of the same data.

### 2. Add New Widgets Iteratively Based on Agent Usage

**Problem**: We created a set of widgets upfront (InfoCard, MetricDisplay, etc.) but the agent sent `LocationCard` which didn't exist.

**Lesson**: The widget registry will grow organically based on what agents actually send. Monitor logs for "Unknown widget" errors and add widgets as needed:

```
flutter: toDashChatMessage: GENUI widget=LocationCard
// Shows up as "Unknown widget: LocationCard" in UI
```

### 3. Widget Registration Checklist

When adding a new widget to the registry:

1. Create the widget file in `lib/widgets/registry/`
2. Implement `fromData` factory that handles flexible types
3. Add import to `lib/core/services/widget_registry.dart`
4. Register the widget in `_registerDefaultWidgets()`
5. Rebuild and test

### 4. Debug Logging is Essential

The debug prints helped identify:
- Which widget name the agent sent (`GENUI widget=LocationCard`)
- That the message was being processed correctly
- The exact point of failure (type cast error)

Keep debug logging in place during development:
```dart
debugPrint('AG-UI: GenUI render tool detected');
debugPrint('ChatNotifier: Adding GenUI message - widget: $widgetName');
```

---

## RFW Removal Lessons

### 5. Simplify Data Models When Removing Dependencies

**Before (with RFW)**:
```dart
class GenUiContent {
  final String toolCallId;
  final String widgetName;
  final String libraryName;      // RFW-specific
  final Uint8List? libraryBlob;  // RFW-specific
  final String? libraryText;     // RFW-specific
  final Map<String, dynamic> data;
}
```

**After (native widgets)**:
```dart
class GenUiContent {
  final String toolCallId;
  final String widgetName;
  final Map<String, dynamic> data;
}
```

**Lesson**: When removing a dependency, also remove all the fields and code paths that only existed to support it.

### 6. Delete Files Completely, Don't Leave Stubs

When removing RFW, we deleted entire files rather than leaving empty stubs:
- `rfw_service.dart` - deleted
- `rfw_decoder.dart` - deleted
- `rfw_message_widget.dart` - deleted
- `local_widget_library.dart` - deleted

**Lesson**: Dead code creates confusion. Remove it entirely.

---

## Build & Release Lessons

### 7. Dynamic IconData Requires Build Flag

When parsing IconData from JSON (e.g., `Icons.location_on.codePoint`), release builds fail because of tree shaking.

**Solution**: Use `--no-tree-shake-icons` flag for release builds:
```bash
flutter build macos --release --no-tree-shake-icons
```

### 8. Clean Builds After Major Refactors

After deleting many files, stale build artifacts can cause issues:
```bash
flutter clean
rm -rf build/
flutter pub get
flutter build macos --debug
```

---

## Architecture Lessons

### 9. Extract Shared Components for Multiple Layouts

The chat functionality needed to work in all three layouts (Standard, Canvas, Three-Column). Solution: Extract `ChatContent` as a reusable widget.

```
lib/features/chat/
├── chat_screen.dart      # App shell with layout switching
├── chat_content.dart     # Reusable chat widget
└── builders/
    └── message_builder.dart
```

### 10. Use Riverpod Providers for Cross-Component State

Services that need to be accessed from multiple places:
- `widgetRegistryProvider` - widget lookup
- `canvasProvider` - canvas state
- `contextPaneProvider` - context pane state
- `layoutModeProvider` - current layout mode

**Lesson**: Riverpod makes it easy to share state across the widget tree without prop drilling.

---

## Testing Lessons

### 11. Test Button is Invaluable

The test button (science icon) in the AppBar that adds a test GenUI message was essential for:
- Verifying widget rendering works
- Testing without needing the full agent flow
- Quick iteration on widget styling

```dart
void _addTestGenUiMessage() {
  chatNotifier.addGenUiMessage(
    GenUiContent(
      toolCallId: 'test-${DateTime.now().millisecondsSinceEpoch}',
      widgetName: 'InfoCard',
      data: {'title': 'Test', 'subtitle': 'Testing...'},
    ),
  );
}
```

### 12. Monitor Console Output During Development

Run with verbose logging to catch issues:
```bash
flutter run -d macos
```

Watch for:
- Widget name mismatches
- Type casting errors
- Missing registrations
- Event flow issues

---

## Summary of Registered Widgets

| Widget Name | Purpose | Key Fields |
|-------------|---------|------------|
| `InfoCard` | Display info with icon | title, subtitle, icon, color |
| `MetricDisplay` | Show metric with trend | label, value, unit, trend |
| `DataList` | List of key-value pairs | items: [{title, value}] |
| `ErrorDisplay` | Error message | message, color |
| `LoadingIndicator` | Loading spinner | message |
| `ActionButton` | Clickable button | label, color |
| `ProgressCard` | Progress bar | label, progress (0-1) |
| `LocationCard` | GPS location display | latitude, longitude, accuracy, altitude, city, country |

---

## Future Considerations

1. **Widget Schema Documentation**: Consider generating schema docs for agents so they know what fields each widget accepts.

2. **Fallback Rendering**: Instead of "Unknown widget", could render a generic JSON viewer as fallback.

3. **Widget Versioning**: If widget data formats change, may need versioning strategy.

4. **Type Coercion Utility**: Create a shared utility for flexible type parsing that all widgets can use.
