/// Interface for handling RoomSession events.
///
/// Implement this to receive canvas, context, and activity updates from
/// RoomSession event processing. Use [NoOpRoomEventHandler] for testing
/// or when events aren't needed.
///
/// Example:
/// ```dart
/// class MyEventHandler implements RoomEventHandler {
///   @override
///   void onCanvasUpdate(String op, String name, Map<String, dynamic> data) {
///     // Handle canvas operation
///   }
///   // ... other methods
/// }
/// ```
abstract class RoomEventHandler {
  /// Called when canvas should be updated.
  ///
  /// [operation] is the type of operation: 'add', 'clear', etc.
  /// [widgetName] is the semantic ID of the widget.
  /// [data] contains the widget data/configuration.
  void onCanvasUpdate(
    String operation,
    String widgetName,
    Map<String, dynamic> data,
  );

  /// Called when context pane should be updated.
  ///
  /// [eventType] indicates what kind of update: 'runStarted', 'textMessage',
  /// 'toolCall', 'stateSnapshot', etc.
  /// [summary] is optional human-readable summary.
  /// [data] is optional structured data for the context pane.
  void onContextUpdate(
    String eventType, {
    String? summary,
    Map<String, dynamic>? data,
  });

  /// Called when activity status changes.
  ///
  /// [isActive] indicates if the agent is currently processing.
  /// [eventType] is optional description of current activity.
  /// [toolName] is optional name of tool being executed.
  void onActivityUpdate(
    bool isActive, {
    String? eventType,
    String? toolName,
  });
}

/// No-op implementation for testing or when events aren't needed.
///
/// All methods are empty implementations that do nothing.
/// Use this as a default handler or in tests where events don't matter.
class NoOpRoomEventHandler implements RoomEventHandler {
  /// Creates a no-op event handler.
  const NoOpRoomEventHandler();

  @override
  void onCanvasUpdate(
    String operation,
    String widgetName,
    Map<String, dynamic> data,
  ) {}

  @override
  void onContextUpdate(
    String eventType, {
    String? summary,
    Map<String, dynamic>? data,
  }) {}

  @override
  void onActivityUpdate(
    bool isActive, {
    String? eventType,
    String? toolName,
  }) {}
}

/// Event handler that records all events for testing.
///
/// Use this in tests to verify that the correct events are emitted.
class RecordingRoomEventHandler implements RoomEventHandler {
  /// All canvas update calls recorded.
  final List<CanvasUpdateRecord> canvasUpdates = [];

  /// All context update calls recorded.
  final List<ContextUpdateRecord> contextUpdates = [];

  /// All activity update calls recorded.
  final List<ActivityUpdateRecord> activityUpdates = [];

  @override
  void onCanvasUpdate(
    String operation,
    String widgetName,
    Map<String, dynamic> data,
  ) {
    canvasUpdates.add(CanvasUpdateRecord(operation, widgetName, data));
  }

  @override
  void onContextUpdate(
    String eventType, {
    String? summary,
    Map<String, dynamic>? data,
  }) {
    contextUpdates.add(ContextUpdateRecord(eventType, summary, data));
  }

  @override
  void onActivityUpdate(
    bool isActive, {
    String? eventType,
    String? toolName,
  }) {
    activityUpdates.add(ActivityUpdateRecord(isActive, eventType, toolName));
  }

  /// Clear all recorded events.
  void clear() {
    canvasUpdates.clear();
    contextUpdates.clear();
    activityUpdates.clear();
  }
}

/// Record of a canvas update call.
class CanvasUpdateRecord {
  final String operation;
  final String widgetName;
  final Map<String, dynamic> data;

  CanvasUpdateRecord(this.operation, this.widgetName, this.data);
}

/// Record of a context update call.
class ContextUpdateRecord {
  final String eventType;
  final String? summary;
  final Map<String, dynamic>? data;

  ContextUpdateRecord(this.eventType, this.summary, this.data);
}

/// Record of an activity update call.
class ActivityUpdateRecord {
  final bool isActive;
  final String? eventType;
  final String? toolName;

  ActivityUpdateRecord(this.isActive, this.eventType, this.toolName);
}
