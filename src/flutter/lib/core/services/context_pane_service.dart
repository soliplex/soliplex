import 'package:soliplex/core/providers/server_scoped_notifier.dart';

/// Represents an item in the context pane.
class ContextItem {
  ContextItem({
    required this.id,
    required this.type,
    required this.title,
    this.summary,
    this.data = const {},
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
  final String id;
  final String type; // 'state', 'tool_result', 'event', 'agui_event'
  final String title;
  final String? summary; // Short description/fragment
  final Map<String, dynamic> data;
  final DateTime timestamp;
}

/// State for the context pane.
class ContextPaneState {
  const ContextPaneState({
    this.currentState = const {},
    this.items = const [],
    this.maxItems = 50,
  });
  final Map<String, dynamic> currentState;
  final List<ContextItem> items;
  final int maxItems;

  ContextPaneState copyWith({
    Map<String, dynamic>? currentState,
    List<ContextItem>? items,
  }) {
    return ContextPaneState(
      currentState: currentState ?? this.currentState,
      items: items ?? this.items,
      maxItems: maxItems,
    );
  }

  bool get isEmpty => items.isEmpty && currentState.isEmpty;
  bool get isNotEmpty => !isEmpty;
}

/// Notifier for managing context pane state.
///
/// Collects:
/// - STATE_SNAPSHOT events from the agent
/// - Tool call results
/// - Other relevant events
///
/// Extends ServerScopedNotifier to automatically reset when server changes.
/// When used with roomContextPaneProvider, also tracks roomId for per-room
/// state.
class ContextPaneNotifier extends ServerScopedNotifier<ContextPaneState> {
  ContextPaneNotifier({super.serverId, this.roomId})
    : super(const ContextPaneState());

  /// The room this context pane belongs to (null for server-scoped legacy
  /// usage).
  final String? roomId;

  /// Called when STATE_SNAPSHOT event is received.
  void updateState(Map<String, dynamic> newState) {
    state = state.copyWith(currentState: newState);
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'state',
        title: 'State Update',
        data: newState,
      ),
    );
  }

  /// Called when a state delta is received.
  void applyDelta(Map<String, dynamic> delta) {
    final updatedState = {...state.currentState, ...delta};
    state = state.copyWith(currentState: updatedState);
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'state',
        title: 'State Delta',
        data: delta,
      ),
    );
  }

  /// Called when tool execution completes.
  void addToolResult(String toolName, Map<String, dynamic> result) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'tool_result',
        title: toolName,
        data: result,
      ),
    );
  }

  /// Add a generic event to the context pane.
  void addEvent(String title, Map<String, dynamic> data) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'event',
        title: title,
        data: data,
      ),
    );
  }

  /// Add an AG-UI event with a concise summary.
  void addAgUiEvent(String eventType, {String? summary}) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'agui_event',
        title: eventType,
        summary: summary,
      ),
    );
  }

  /// Add a text message event with a fragment preview.
  void addTextMessage(String fragment, {bool isUser = false}) {
    final preview = fragment.length > 50
        ? '${fragment.substring(0, 50)}...'
        : fragment;
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'agui_event',
        title: isUser ? 'User Message' : 'Agent Message',
        summary: preview,
      ),
    );
  }

  /// Add a tool call event.
  void addToolCall(String toolName, {String? summary}) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'agui_event',
        title: 'Tool: $toolName',
        summary: summary,
      ),
    );
  }

  /// Add a GenUI render event.
  void addGenUiRender(String widgetName) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'agui_event',
        title: 'GenUI Render',
        summary: widgetName,
      ),
    );
  }

  /// Add a canvas render event.
  void addCanvasRender(String widgetName, String position) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'agui_event',
        title: 'Canvas Render',
        summary: '$widgetName ($position)',
      ),
    );
  }

  /// Add a tool execution state change event.
  ///
  /// isStarting true when tool starts executing, false when it ends.
  /// success indicates whether the tool completed successfully (only valid
  /// when !isStarting).
  /// error contains error message if the tool failed.
  void addToolExecution(
    String toolName, {
    required bool isStarting,
    bool? success,
    String? error,
  }) {
    String title;
    String? summary;

    if (isStarting) {
      title = 'Executing: $toolName';
      summary = 'started';
    } else if (success ?? false) {
      title = 'Completed: $toolName';
      summary = 'success';
    } else {
      title = 'Failed: $toolName';
      summary = error ?? 'unknown error';
    }

    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'tool_execution',
        title: title,
        summary: summary,
      ),
    );
  }

  /// Add a local tool execution event.
  void addLocalToolExecution(String toolName, {String status = 'executing'}) {
    _addItem(
      ContextItem(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'agui_event',
        title: 'Local Tool: $toolName',
        summary: status,
      ),
    );
  }

  void _addItem(ContextItem item) {
    final newItems = [item, ...state.items];
    // Keep only maxItems
    final trimmed = newItems.take(state.maxItems).toList();
    state = state.copyWith(items: trimmed);
  }

  /// Clear all context items but keep current state.
  void clearItems() {
    state = state.copyWith(items: []);
  }

  /// Clear everything including state.
  void clear() {
    state = const ContextPaneState();
  }
}

// Note: contextPaneProvider is declared in
// lib/core/providers/panel_providers.dart
