# Widget Registry

Soliplex includes a widget registry system for rendering native Flutter widgets from agent responses (GenUI).

## Overview

Agents can send structured widget data instead of plain text. The widget registry maps widget names to native Flutter implementations.

```
Agent Response
    ↓
{widget_name: "InfoCard", data: {...}}
    ↓
WidgetRegistry.build()
    ↓
Native Flutter Widget
```

## Registry Implementation

```dart
class WidgetRegistry {
  final Map<String, WidgetBuilder> _builders = {};

  /// Register a widget builder
  void register(String widgetName, WidgetBuilder builder) {
    _builders[widgetName.toLowerCase()] = builder;
  }

  /// Build a widget by name
  Widget? build(
    BuildContext context,
    String widgetName,
    Map<String, dynamic> data, {
    void Function(String eventName, Map<String, dynamic> args)? onEvent,
  }) {
    final builder = _builders[widgetName.toLowerCase()];
    if (builder == null) return null;
    return builder(context, data, onEvent);
  }
}

// Provider
final widgetRegistryProvider = Provider<WidgetRegistry>((ref) {
  return WidgetRegistry();
});
```

## Built-in Widgets

### InfoCard

Display informational content with icon and actions.

```json
{
  "widget_name": "InfoCard",
  "data": {
    "title": "Important Notice",
    "content": "Please review the following...",
    "icon": "info",
    "variant": "primary"
  }
}
```

### MetricDisplay

Show numeric metrics with labels.

```json
{
  "widget_name": "MetricDisplay",
  "data": {
    "label": "Response Time",
    "value": 42,
    "unit": "ms",
    "trend": "up"
  }
}
```

### DataList

Render a list of items.

```json
{
  "widget_name": "DataList",
  "data": {
    "title": "Search Results",
    "items": [
      {"title": "Item 1", "subtitle": "Description"},
      {"title": "Item 2", "subtitle": "Description"}
    ]
  }
}
```

### ProgressCard

Show progress indicators.

```json
{
  "widget_name": "ProgressCard",
  "data": {
    "title": "Processing",
    "progress": 0.75,
    "status": "Analyzing documents..."
  }
}
```

### LocationCard

Display location information with optional map.

```json
{
  "widget_name": "LocationCard",
  "data": {
    "name": "Anthropic HQ",
    "address": "San Francisco, CA",
    "latitude": 37.7749,
    "longitude": -122.4194
  }
}
```

### GISCard

Geographic information system visualization.

```json
{
  "widget_name": "GISCard",
  "data": {
    "layers": [...],
    "center": [37.7749, -122.4194],
    "zoom": 12
  }
}
```

### ActionButton

Interactive button that sends events back.

```json
{
  "widget_name": "ActionButton",
  "data": {
    "label": "Confirm",
    "action": "confirm_action",
    "variant": "primary"
  }
}
```

### ErrorDisplay

Show error messages.

```json
{
  "widget_name": "ErrorDisplay",
  "data": {
    "title": "Error",
    "message": "Something went wrong",
    "code": "ERR_500"
  }
}
```

### LoadingIndicator

Show loading state.

```json
{
  "widget_name": "LoadingIndicator",
  "data": {
    "message": "Loading data..."
  }
}
```

### SearchWidget

Search input with suggestions.

```json
{
  "widget_name": "SearchWidget",
  "data": {
    "placeholder": "Search documents...",
    "suggestions": ["RAG", "Vector", "Embedding"]
  }
}
```

### SkillsCard

Display skill/capability chips.

```json
{
  "widget_name": "SkillsCard",
  "data": {
    "title": "Available Skills",
    "skills": ["Python", "RAG", "LLM"]
  }
}
```

### ProjectCard

Project information display.

```json
{
  "widget_name": "ProjectCard",
  "data": {
    "name": "Soliplex",
    "description": "AI chat platform",
    "status": "active"
  }
}
```

### NoteCard / CodeCard / MarkdownCard

Content display widgets for canvas.

```json
{
  "widget_name": "NoteCard",
  "data": {
    "content": "Remember to review the API docs"
  }
}
```

## Widget Builder Signature

```dart
typedef WidgetBuilder = Widget Function(
  BuildContext context,
  Map<String, dynamic> data,
  void Function(String eventName, Map<String, dynamic> args)? onEvent,
);
```

- `context` - Flutter build context
- `data` - Widget data from agent
- `onEvent` - Callback for interactive widgets

## Adding Custom Widgets

### 1. Create Widget Class

```dart
// lib/widgets/registry/my_widget.dart
class MyWidget extends StatelessWidget {
  final String title;
  final List<String> items;

  const MyWidget({required this.title, required this.items});

  factory MyWidget.fromData(Map<String, dynamic> data) {
    return MyWidget(
      title: data['title'] as String? ?? '',
      items: List<String>.from(data['items'] ?? []),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          ...items.map((item) => ListTile(title: Text(item))),
        ],
      ),
    );
  }
}
```

### 2. Register in Widget Registry

```dart
// lib/core/services/widget_registry.dart
void _registerDefaultWidgets() {
  // ... existing widgets ...

  register('MyWidget', (context, data, onEvent) {
    return MyWidget.fromData(data);
  });
}
```

### 3. Use from Agent

The agent can now return:

```json
{
  "widget_name": "MyWidget",
  "data": {
    "title": "My Custom Widget",
    "items": ["Item 1", "Item 2", "Item 3"]
  }
}
```

## Interactive Widgets

Widgets can send events back to the agent:

```dart
class ActionButtonWidget extends StatelessWidget {
  final String label;
  final String action;
  final void Function(String, Map<String, dynamic>)? onEvent;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: () {
        onEvent?.call(action, {'timestamp': DateTime.now().toIso8601String()});
      },
      child: Text(label),
    );
  }
}
```

The event is sent to the agent as part of the next run input.

## GenUI Message Rendering

GenUI widgets are rendered in the chat via `GenUiMessageWidget`:

```dart
class GenUiMessageWidget extends StatelessWidget {
  final String widgetName;
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final registry = context.read(widgetRegistryProvider);
    final widget = registry.build(context, widgetName, data);

    if (widget != null) {
      return widget;
    }

    // Fallback for unknown widgets
    return Card(
      child: Text('Unknown widget: $widgetName'),
    );
  }
}
```

## Best Practices

1. **Validate data** - Always handle missing or malformed data gracefully
2. **Use fromData factories** - Centralize parsing logic
3. **Handle null onEvent** - Not all contexts support events
4. **Keep widgets focused** - One widget, one purpose
5. **Test thoroughly** - Widget rendering with various data shapes

## Source Code

- Widget registry: `lib/core/services/widget_registry.dart`
- Widget implementations: `lib/widgets/registry/`
- GenUI rendering: `lib/features/chat/widgets/genui_message_widget.dart`
