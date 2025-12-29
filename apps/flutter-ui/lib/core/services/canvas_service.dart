import 'package:soliplex/core/providers/server_scoped_notifier.dart';

/// Represents an item displayed on the canvas.
class CanvasItem {
  CanvasItem({
    required this.id,
    required this.widgetName,
    required this.data,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();
  final String id;
  final String widgetName;
  final Map<String, dynamic> data;
  final DateTime createdAt;

  CanvasItem copyWith({
    String? id,
    String? widgetName,
    Map<String, dynamic>? data,
    DateTime? createdAt,
  }) {
    return CanvasItem(
      id: id ?? this.id,
      widgetName: widgetName ?? this.widgetName,
      data: data ?? this.data,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  /// Convert to JSON for state serialization.
  Map<String, dynamic> toJson() {
    return {'id': id, 'widget': widgetName, 'data': data};
  }

  /// Generate a semantic ID from widget data.
  ///
  /// Returns IDs like "staff-u1", "project-p2" based on widget type and data.
  static String semanticId(String widgetName, Map<String, dynamic> data) {
    switch (widgetName) {
      case 'SkillsCard':
        final personId = data['person_id'] as String?;
        if (personId != null) return 'staff-$personId';
      case 'ProjectCard':
        final projectId = data['id'] as String?;
        if (projectId != null) return 'project-$projectId';
      case 'InfoCard':
        final title = data['title'] as String?;
        if (title != null) {
          // ignore: lines_longer_than_80_chars (auto-documented)
          return 'info-${title.toLowerCase().replaceAll(RegExp(r'\s+'), '-').substring(0, title.length.clamp(0, 20))}';
        }
      // Canvas content widgets (send-to-canvas feature)
      case 'NoteCard':
        final content = data['content'] as String? ?? '';
        final hash = content.hashCode.abs().toString();
        return 'note-${hash.length > 8 ? hash.substring(0, 8) : hash}';
      case 'CodeCard':
        final code = data['code'] as String? ?? '';
        final lang = data['language'] as String? ?? 'code';
        final hash = code.hashCode.abs().toString();
        return '$lang-${hash.length > 8 ? hash.substring(0, 8) : hash}';
      case 'MarkdownCard':
        final content = data['content'] as String? ?? '';
        final hash = content.hashCode.abs().toString();
        return 'markdown-${hash.length > 8 ? hash.substring(0, 8) : hash}';
    }
    // Fallback to timestamp-based ID
    // ignore: lines_longer_than_80_chars
    return '${widgetName.toLowerCase()}-${DateTime.now().millisecondsSinceEpoch}';
  }

  /// Human-readable summary for LLM context.
  String get summary {
    switch (widgetName) {
      case 'SkillsCard':
        final name = data['name'] as String? ?? 'Unknown';
        final title = data['title'] as String? ?? '';
        return '$name ($title)';
      case 'ProjectCard':
        final title = data['title'] as String? ?? 'Untitled';
        return title;
      case 'InfoCard':
        return data['title'] as String? ?? 'Info';
      case 'NoteCard':
        final content = data['content'] as String? ?? '';
        final preview = content.length > 50
            ? '${content.substring(0, 50)}...'
            : content;
        return 'Note: $preview';
      case 'CodeCard':
        final lang = data['language'] as String? ?? 'code';
        return 'Code ($lang)';
      case 'MarkdownCard':
        final content = data['content'] as String? ?? '';
        final preview = content.length > 50
            ? '${content.substring(0, 50)}...'
            : content;
        return 'Markdown: $preview';
      default:
        return widgetName;
    }
  }
}

/// State for the canvas.
class CanvasState {
  const CanvasState({this.items = const []});
  final List<CanvasItem> items;

  CanvasState copyWith({List<CanvasItem>? items}) {
    return CanvasState(items: items ?? this.items);
  }

  bool get isEmpty => items.isEmpty;
  bool get isNotEmpty => items.isNotEmpty;

  /// Convert to JSON for AG-UI state field.
  Map<String, dynamic> toJson() {
    return {'canvas': items.map((item) => item.toJson()).toList()};
  }

  /// Human-readable summary for LLM context.
  String toSummary() {
    if (items.isEmpty) return 'Canvas is empty.';

    final grouped = <String, List<CanvasItem>>{};
    for (final item in items) {
      grouped.putIfAbsent(item.widgetName, () => []).add(item);
    }

    final parts = <String>[];
    for (final entry in grouped.entries) {
      final widgetType = entry.key;
      final widgetItems = entry.value;
      final summaries = widgetItems
          .map((i) => '  - ${i.summary} [${i.id}]')
          .join('\n');
      parts.add('$widgetType (${widgetItems.length}):\n$summaries');
    }
    return 'Canvas contents:\n${parts.join('\n')}';
  }
}

/// Notifier for managing canvas state.
///
/// Supports adding, replacing, and clearing canvas items.
/// Agent can push widgets to canvas via the `canvas_render` tool.
///
/// Extends ServerScopedNotifier to automatically reset when server changes.
/// When used with roomCanvasProvider, also tracks roomId for per-room state.
class CanvasNotifier extends ServerScopedNotifier<CanvasState> {
  CanvasNotifier({super.serverId, this.roomId}) : super(const CanvasState());

  /// The room this canvas belongs to (null for server-scoped legacy usage).
  final String? roomId;

  /// Add a new item to the canvas.
  ///
  /// Uses semantic IDs to prevent duplicates. If an item with the same
  /// semantic ID already exists, the existing item is updated instead.
  void addItem(String widgetName, Map<String, dynamic> data) {
    final id = CanvasItem.semanticId(widgetName, data);

    // Check if item with this ID already exists
    final existingIndex = state.items.indexWhere((item) => item.id == id);
    if (existingIndex >= 0) {
      // Update existing item
      final updatedItems = [...state.items];
      updatedItems[existingIndex] = CanvasItem(
        id: id,
        widgetName: widgetName,
        data: data,
      );
      state = state.copyWith(items: updatedItems);
      return;
    }

    // Add new item
    final item = CanvasItem(id: id, widgetName: widgetName, data: data);
    state = state.copyWith(items: [...state.items, item]);
  }

  /// Replace all items with a single new item.
  void replaceAll(String widgetName, Map<String, dynamic> data) {
    final id = CanvasItem.semanticId(widgetName, data);
    final item = CanvasItem(id: id, widgetName: widgetName, data: data);
    state = state.copyWith(items: [item]);
  }

  /// Clear all items from the canvas.
  void clear() {
    state = const CanvasState();
  }

  /// Remove a specific item by ID.
  void removeItem(String id) {
    state = state.copyWith(
      items: state.items.where((item) => item.id != id).toList(),
    );
  }

  /// Update an existing item's data.
  void updateItem(String id, Map<String, dynamic> newData) {
    state = state.copyWith(
      items: state.items.map((item) {
        if (item.id == id) {
          return item.copyWith(data: {...item.data, ...newData});
        }
        return item;
      }).toList(),
    );
  }

  /// Check if an item with the given semantic ID exists.
  bool hasItem(String widgetName, Map<String, dynamic> data) {
    final id = CanvasItem.semanticId(widgetName, data);
    return state.items.any((item) => item.id == id);
  }
}

// Note: canvasProvider is declared in lib/core/providers/panel_providers.dart
