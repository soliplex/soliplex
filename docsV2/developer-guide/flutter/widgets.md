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

Display informational content with icon and optional subtitle.

```json
{
  "widget_name": "InfoCard",
  "data": {
    "title": "Important Notice",
    "subtitle": "Please review the following...",
    "icon": 58171,
    "color": 4280391411
  }
}
```

Note: `icon` is an IconData codePoint integer, `color` is ARGB32.

### MetricDisplay

Show numeric metrics with labels and trend indicators.

```json
{
  "widget_name": "MetricDisplay",
  "data": {
    "label": "Response Time",
    "value": "42",
    "unit": "ms",
    "trend": "up",
    "color": 4280391411
  }
}
```

Note: `trend` can be "up", "down", or "neutral".

### DataList

Render a list of key-value items.

```json
{
  "widget_name": "DataList",
  "data": {
    "items": [
      {"title": "Name", "value": "John Doe"},
      {"title": "Email", "value": "john@example.com"}
    ]
  }
}
```

Also supports `subtitle` instead of `value` for user lists.

### ProgressCard

Show progress indicators.

```json
{
  "widget_name": "ProgressCard",
  "data": {
    "label": "Upload Progress",
    "progress": 0.75,
    "color": 4280391411
  }
}
```

Note: `progress` is 0.0 to 1.0.

### LocationCard

Display GPS location data with coordinates and address.

```json
{
  "widget_name": "LocationCard",
  "data": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "accuracy": 10.0,
    "altitude": 15.0,
    "address": "123 Main St",
    "city": "San Francisco",
    "country": "USA",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### GISCard

OpenStreetMap visualization with one or more coordinates.

```json
{
  "widget_name": "GISCard",
  "data": {
    "coordinates": [
      {"latitude": 37.7749, "longitude": -122.4194, "label": "HQ"}
    ],
    "zoom": 15,
    "title": "Locations"
  }
}
```

Also supports single coordinate format with `latitude`/`longitude` at root.

### ActionButton

Interactive button that sends events back.

```json
{
  "widget_name": "ActionButton",
  "data": {
    "label": "Confirm",
    "color": 4280391411
  }
}
```

Fires `pressed` event with the original data when clicked.

### ErrorDisplay

Show error messages.

```json
{
  "widget_name": "ErrorDisplay",
  "data": {
    "message": "Something went wrong",
    "color": 4294198070
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

Interactive search with item selection.

```json
{
  "widget_name": "SearchWidget",
  "data": {
    "placeholder": "Search...",
    "multi_select": true,
    "min_chars": 1,
    "items": [
      {"id": "1", "title": "Document 1", "subtitle": "Description"}
    ]
  }
}
```

Emits `submit` event with `{"selected": [...]}` or `cancel` event.

### SkillsCard

Display person skills with proficiency levels.

```json
{
  "widget_name": "SkillsCard",
  "data": {
    "person_id": "u1",
    "name": "John Smith",
    "title": "Engineering Lead",
    "skills": [
      {"name": "Flutter", "level": 5},
      {"name": "Python", "level": 4}
    ],
    "avatar_url": "https://..."
  }
}
```

Skill levels: 1-5 (Beginner to Expert).

### ProjectCard

Project information with required skills.

```json
{
  "widget_name": "ProjectCard",
  "data": {
    "id": "p1",
    "title": "Mobile App Redesign",
    "description": "Complete overhaul of the mobile application",
    "required_skills": ["Flutter", "Dart", "Figma"],
    "status": "open",
    "matched_skills": ["Flutter", "Dart"]
  }
}
```

Status: "open", "in_progress", or "completed".

### NoteCard / CodeCard / MarkdownCard

Content display widgets for canvas.

```json
{
  "widget_name": "NoteCard",
  "data": {
    "content": "Remember to review the API docs",
    "title": "Optional title",
    "source_message_id": "uuid-of-source-message"
  }
}
```

CodeCard also accepts `language` for syntax highlighting.

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
  final Color? color;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      style: color != null
          ? ElevatedButton.styleFrom(backgroundColor: color)
          : null,
      onPressed: onPressed,
      child: Text(label),
    );
  }
}
```

The `onPressed` callback is wired to fire an event via `onEvent?.call('pressed', data)`.

## GenUI Message Rendering

GenUI widgets are rendered in the chat via `GenUiMessageWidget`:

```dart
class GenUiMessageWidget extends ConsumerWidget {
  final GenUiContent content;
  final void Function(String, Map<String, dynamic>)? onEvent;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final registry = ref.watch(widgetRegistryProvider);
    final widget = registry.build(
      context,
      content.widgetName,
      content.data,
      onEvent: onEvent,
    );

    if (widget != null) {
      return widget;
    }

    // Fallback shows available widgets
    return _buildUnknownWidget(context, registry);
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
