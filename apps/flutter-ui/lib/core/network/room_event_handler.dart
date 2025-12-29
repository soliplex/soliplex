/// Interface for handling RoomSession events.
///
/// Implement this to receive canvas, context, and activity updates from
/// RoomSession event processing. Use NoOpRoomEventHandler for testing
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
  /// operation is the type of operation: 'add', 'clear', etc.
  /// widgetName is the semantic ID of the widget.
  /// data contains the widget data/configuration.
  void onCanvasUpdate(
    String operation,
    String widgetName,
    Map<String, dynamic> data,
  );

  /// Called when context pane should be updated.
  ///
  /// eventType indicates what kind of update: 'runStarted', 'textMessage',
  /// 'toolCall', 'stateSnapshot', etc.
  /// summary is optional human-readable summary.
  /// data is optional structured data for the context pane.
  void onContextUpdate(
    String eventType, {
    String? summary,
    Map<String, dynamic>? data,
  });

  /// Called when activity status changes.
  ///
  /// isActive indicates if the agent is currently processing.
  /// eventType is optional description of current activity.
  /// toolName is optional name of tool being executed.
  void onActivityUpdate({
    bool isActive = false,
    String? eventType,
    String? toolName,
  });

  /// Called when a tool execution starts, completes, or fails.
  ///
  /// toolCallId is the unique identifier for this tool call.
  /// toolName is the name of the tool being executed.
  /// status is one of: 'executing', 'completed', 'error'.
  /// errorMessage is provided when status is 'error'.
  void onToolExecution(
    String toolCallId,
    String toolName,
    String status, {
    String? errorMessage,
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
  void onActivityUpdate({
    bool isActive = false,
    String? eventType,
    String? toolName,
  }) {}

  @override
  void onToolExecution(
    String toolCallId,
    String toolName,
    String status, {
    String? errorMessage,
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

  /// All tool execution calls recorded.
  final List<ToolExecutionRecord> toolExecutions = [];

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
  void onActivityUpdate({
    bool isActive = false,
    String? eventType,
    String? toolName,
  }) {
    activityUpdates.add(
      ActivityUpdateRecord(
        isActive: isActive,
        eventType: eventType,
        toolName: toolName,
      ),
    );
  }

  @override
  void onToolExecution(
    String toolCallId,
    String toolName,
    String status, {
    String? errorMessage,
  }) {
    toolExecutions.add(
      ToolExecutionRecord(toolCallId, toolName, status, errorMessage),
    );
  }

  /// Clear all recorded events.
  void clear() {
    canvasUpdates.clear();
    contextUpdates.clear();
    activityUpdates.clear();
    toolExecutions.clear();
  }
}

/// Record of a canvas update call.
class CanvasUpdateRecord {
  CanvasUpdateRecord(this.operation, this.widgetName, this.data);
  final String operation;
  final String widgetName;
  final Map<String, dynamic> data;
}

/// Record of a context update call.
class ContextUpdateRecord {
  ContextUpdateRecord(this.eventType, this.summary, this.data);
  final String eventType;
  final String? summary;
  final Map<String, dynamic>? data;
}

/// Record of an activity update call.
class ActivityUpdateRecord {
  ActivityUpdateRecord({
    required this.isActive,
    this.eventType,
    this.toolName,
  });
  final bool isActive;
  final String? eventType;
  final String? toolName;
}

/// Record of a tool execution call.
class ToolExecutionRecord {
  ToolExecutionRecord(
    this.toolCallId,
    this.toolName,
    this.status,
    this.errorMessage,
  );
  final String toolCallId;
  final String toolName;
  final String status;
  final String? errorMessage;
}
