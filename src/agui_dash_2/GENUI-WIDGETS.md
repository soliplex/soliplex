# GenUI Widget System

Documentation for the native widget rendering system in the AG-UI dashboard app.

## Overview

The GenUI system allows AI agents to render native Flutter widgets in the chat and on the canvas. Instead of generating HTML/React components, the agent sends a `widget_name` and JSON `data`, which the client renders using pre-registered native widgets.

```
Agent → { widget_name: "SkillsCard", data: {...} } → Flutter App → Native Widget
```

## Architecture

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `WidgetRegistry` | `lib/core/services/widget_registry.dart` | Maps widget names to builder functions |
| `GenUiContent` | `lib/core/models/chat_models.dart` | Data model for widget content |
| `GenUiMessageWidget` | `lib/features/chat/widgets/genui_message_widget.dart` | Renders widgets in chat |
| `CanvasService` | `lib/core/services/canvas_service.dart` | Manages canvas state and deduplication |
| `LocalToolsService` | `lib/core/services/local_tools_service.dart` | Defines `genui_render` and `canvas_render` tools |
| Widget files | `lib/widgets/registry/*.dart` | Individual widget implementations |

### Flow: Agent → Widget

1. Agent calls `genui_render` tool with `widget_name` and `data`
2. `chat_content.dart` intercepts the tool call (not sent to server)
3. Creates `GenUiContent` with the widget info
4. Creates `ChatMessage` with `type: MessageType.genUi`
5. `ChatMessageBubble` routes to `GenUiMessageWidget`
6. `GenUiMessageWidget` looks up builder in `WidgetRegistry`
7. Builder calls `WidgetClass.fromData(data, onEvent)` to create widget

### Flow: Canvas Rendering

1. Agent calls `canvas_render` tool OR user clicks "Send to Canvas" button
2. `CanvasNotifier.addItem(widgetName, data)` is called
3. Semantic ID is generated for deduplication
4. Widget is rendered in the canvas area using same registry

---

## Widget Registry

### Registration Pattern

All widgets follow the factory pattern with `fromData`:

```dart
// In widget_registry.dart
registry.register('SkillsCard', (context, data, onEvent) {
  return SkillsCardWidget.fromData(data, onEvent);
});

// In skills_card_widget.dart
factory SkillsCardWidget.fromData(
  Map<String, dynamic> data,
  void Function(String, Map<String, dynamic>)? onEvent,
) {
  return SkillsCardWidget(
    personId: data['person_id'] as String? ?? '',
    name: data['name'] as String? ?? 'Unknown',
    // ... parse other fields
  );
}
```

### Type-Safe Parsing

Use utilities from `widget_utils.dart` for safe type coercion:

```dart
import 'widget_utils.dart';

// Safe parsing (handles String "123" → int 123)
final count = parseInt(data['count']);        // int?
final ratio = parseDouble(data['ratio']);     // double?
final color = parseColor(data['color']);      // Color?
final icon = parseIcon(data['icon']);         // IconData?
```

---

## Registered Widgets

### Display Widgets

| Widget | Purpose | Key Data Fields |
|--------|---------|-----------------|
| `InfoCard` | Title/subtitle card | `title`, `subtitle`, `icon`, `color` |
| `MetricDisplay` | Single metric | `label`, `value`, `unit`, `trend` |
| `DataList` | Key-value list | `items: [{title, value}]` |
| `ProgressCard` | Progress bar | `label`, `progress` (0-1), `color` |
| `LocationCard` | GPS coordinates | `latitude`, `longitude`, `accuracy`, `city` |
| `GISCard` | OpenStreetMap | `latitude`, `longitude`, `zoom`, `coordinates[]` |

### Domain Widgets

| Widget | Purpose | Key Data Fields |
|--------|---------|-----------------|
| `SkillsCard` | Person with skills | `person_id`, `name`, `title`, `skills[]` |
| `ProjectCard` | Project info | `id`, `title`, `description`, `required_skills[]`, `status` |

### Interactive Widgets

| Widget | Purpose | Key Data Fields |
|--------|---------|-----------------|
| `ActionButton` | Clickable button | `label`, `action`, `variant` |
| `SearchWidget` | Search with selection | `options[]`, `searchType` |

### Canvas Content Widgets

| Widget | Purpose | Key Data Fields |
|--------|---------|-----------------|
| `NoteCard` | Plain text note | `content`, `title`, `source_message_id` |
| `CodeCard` | Code snippet | `code`, `language` |
| `MarkdownCard` | Rich markdown | `content`, `title` |

### Utility Widgets

| Widget | Purpose | Key Data Fields |
|--------|---------|-----------------|
| `LoadingIndicator` | Spinner | `message` |
| `ErrorDisplay` | Error message | `message`, `code` |

---

## Semantic IDs (Deduplication)

Canvas uses semantic IDs to prevent duplicate items. IDs are generated based on widget type and data:

```dart
// In canvas_service.dart
static String semanticId(String widgetName, Map<String, dynamic> data) {
  switch (widgetName) {
    case 'SkillsCard':
      return 'staff-${data['person_id']}';    // staff-u1
    case 'ProjectCard':
      return 'project-${data['id']}';         // project-p1
    case 'NoteCard':
      return 'note-${contentHash}';           // note-12345678
    case 'CodeCard':
      return '${language}-${codeHash}';       // python-87654321
    default:
      return '${widgetName}-${timestamp}';    // fallback
  }
}
```

**Behavior**: If you add an item with the same semantic ID, it **updates** the existing item instead of creating a duplicate.

---

## Event Handling

Widgets can emit events back to the agent via the `onEvent` callback:

```dart
// Widget emits event
onEvent?.call('selection', {'selected_id': 'u1'});

// In chat_message_bubble.dart, events are passed to handler
GenUiMessageWidget(
  content: message.genUiContent!,
  onEvent: onGenUiEvent,  // Routes to chat service
)
```

### Event Flow

```
Widget → onEvent('click', {id: 'x'}) → ChatContent → ChatService → Server
```

**Current limitation**: Event handling is partially implemented. Events are captured but server-side handling may vary.

---

## Local Tools

### genui_render

Renders a widget inline in the chat conversation.

```json
{
  "widget_name": "InfoCard",
  "data": {
    "title": "Welcome",
    "subtitle": "Hello world"
  }
}
```

### canvas_render

Renders a widget on the canvas area.

```json
{
  "widget_name": "MetricDisplay",
  "data": {
    "label": "Score",
    "value": "95",
    "unit": "%"
  },
  "position": "append"  // append | replace | clear
}
```

**Position options**:
- `append` - Add to existing canvas items
- `replace` - Clear canvas, show only this widget
- `clear` - Remove all canvas items (widget_name ignored)

---

## Creating a New Widget

### 1. Create Widget File

```dart
// lib/widgets/registry/my_widget.dart
import 'package:flutter/material.dart';
import 'widget_utils.dart';

class MyWidget extends StatelessWidget {
  final String title;
  final int count;

  const MyWidget({super.key, required this.title, required this.count});

  factory MyWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    return MyWidget(
      title: data['title'] as String? ?? '',
      count: parseInt(data['count']) ?? 0,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Card(child: Text('$title: $count'));
  }
}
```

### 2. Register in Widget Registry

```dart
// lib/core/services/widget_registry.dart

import '../../widgets/registry/my_widget.dart';

void _registerDefaultWidgets(WidgetRegistry registry) {
  // ... existing widgets ...

  registry.register('MyWidget', (context, data, onEvent) {
    return MyWidget.fromData(data, onEvent);
  });
}
```

### 3. Add Semantic ID (for canvas)

```dart
// lib/core/services/canvas_service.dart

static String semanticId(String widgetName, Map<String, dynamic> data) {
  switch (widgetName) {
    // ... existing cases ...
    case 'MyWidget':
      final id = data['id'] as String?;
      if (id != null) return 'mywidget-$id';
      break;
  }
  // ...
}
```

### 4. Update Tool Description (optional)

If agents should use the widget, update the tool description in `local_tools_service.dart`.

---

## Limitations

### Current Limitations

1. **No streaming widget updates**
   - Widgets are rendered once with initial data
   - Cannot update widget data after render without re-creating the message
   - Workaround: Use canvas with semantic IDs for updateable content

2. **Limited event handling**
   - Events from widgets (button clicks, selections) are captured
   - Server-side handling depends on agent implementation
   - No built-in event acknowledgment mechanism

3. **No widget state persistence**
   - Widget state (expanded/collapsed, selections) is not persisted
   - Refreshing the app loses widget state
   - Canvas items are also in-memory only

4. **Fixed widget set**
   - Widgets must be pre-registered at compile time
   - Agent cannot define new widget types dynamically
   - Agent must use existing widget vocabulary

5. **No nested GenUI**
   - Widgets cannot contain other GenUI widgets
   - Composition must happen at the data level

6. **Canvas layout is simple**
   - Canvas items are displayed in a vertical list
   - No drag-and-drop positioning
   - No grid or dashboard layout options

7. **No widget sizing control**
   - Agent cannot specify widget dimensions
   - Widgets use their natural size or container constraints
   - Max height enforced in GenUiMessageWidget (400px default)

### Data Type Constraints

- **Colors**: Must be ARGB32 int (e.g., `4280391411`) or Material icon constant
- **Icons**: Must be IconData codePoint int (e.g., `58751` for `Icons.info`)
- **No complex objects**: Data must be JSON-serializable primitives

---

## File Reference

```
lib/
├── core/
│   ├── models/
│   │   └── chat_models.dart          # GenUiContent, ChatMessage
│   └── services/
│       ├── widget_registry.dart      # WidgetRegistry, registration
│       ├── canvas_service.dart       # CanvasNotifier, semantic IDs
│       ├── canvas_content_service.dart  # Content type detection
│       └── local_tools_service.dart  # genui_render, canvas_render tools
├── features/
│   └── chat/
│       └── widgets/
│           ├── chat_message_bubble.dart  # Message routing, canvas button
│           └── genui_message_widget.dart # Widget rendering in chat
└── widgets/
    └── registry/
        ├── widget_utils.dart         # Type parsing utilities
        ├── info_card_widget.dart
        ├── metric_display_widget.dart
        ├── data_list_widget.dart
        ├── skills_card_widget.dart
        ├── project_card_widget.dart
        ├── note_card_widget.dart
        ├── code_card_widget.dart
        ├── markdown_card_widget.dart
        ├── progress_card_widget.dart
        ├── location_card_widget.dart
        ├── gis_card_widget.dart
        ├── search_widget.dart
        ├── action_button_widget.dart
        ├── loading_indicator_widget.dart
        └── error_display_widget.dart
```

---

## Future Considerations

1. **Widget schema validation** - Validate data against JSON schema before rendering
2. **Widget versioning** - Support multiple versions of same widget
3. **Dynamic widget loading** - Load widget code at runtime
4. **Canvas persistence** - Save/restore canvas state
5. **Widget templates** - Agent-defined composite widgets
6. **Responsive widgets** - Size-aware widget variants
