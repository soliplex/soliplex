import 'package:meta/meta.dart';

/// AG-UI event types from the backend SSE stream.
enum AgUiEventType {
  /// Emitted when a run starts.
  runStarted,

  /// Emitted when a run finishes successfully.
  runFinished,

  /// Emitted when a run encounters an error.
  runError,

  /// Emitted when a step starts.
  stepStarted,

  /// Emitted when a step finishes.
  stepFinished,

  /// Emitted when a text message starts streaming.
  textMessageStart,

  /// Emitted for each chunk of text message content.
  textMessageContent,

  /// Emitted when a text message finishes streaming.
  textMessageEnd,

  /// Emitted when a tool call starts.
  toolCallStart,

  /// Emitted for each chunk of tool call arguments.
  toolCallArgs,

  /// Emitted when a tool call finishes.
  toolCallEnd,

  /// Emitted when a tool call result is available.
  toolCallResult,

  /// Emitted with a full state snapshot.
  stateSnapshot,

  /// Emitted with a state delta (JSON Patch operations).
  stateDelta,

  /// Emitted with a full activity snapshot.
  activitySnapshot,

  /// Emitted with an activity delta.
  activityDelta,

  /// Emitted with a full messages snapshot.
  messagesSnapshot,

  /// Emitted for custom application-specific events.
  custom,

  /// Represents an unrecognized event type.
  unknown;

  /// Parses an event type from a string (e.g., "RUN_STARTED" -> runStarted).
  static AgUiEventType fromString(String value) {
    // Convert SCREAMING_SNAKE_CASE to camelCase
    final normalized = value
        .toLowerCase()
        .split('_')
        .asMap()
        .entries
        .map((e) {
          if (e.key == 0) return e.value;
          return e.value.isEmpty
              ? ''
              : '${e.value[0].toUpperCase()}${e.value.substring(1)}';
        })
        .join();

    return AgUiEventType.values.firstWhere(
      (e) => e.name == normalized,
      orElse: () => AgUiEventType.unknown,
    );
  }

  /// Converts to SCREAMING_SNAKE_CASE string for JSON serialization.
  String toJsonString() {
    return name
        .replaceAllMapped(
          RegExp('([A-Z])'),
          (m) => '_${m.group(1)!.toLowerCase()}',
        )
        .toUpperCase();
  }
}

/// Base class for all AG-UI events.
///
/// Use [AgUiEvent.fromJson] to parse events from the SSE stream.
@immutable
sealed class AgUiEvent {
  const AgUiEvent({required this.type});

  /// The type of this event.
  final AgUiEventType type;

  /// Parses an AG-UI event from JSON.
  ///
  /// The JSON structure is expected to be:
  /// ```json
  /// {"type": "EVENT_TYPE", ...event-specific fields}
  /// ```
  static AgUiEvent fromJson(Map<String, dynamic> json) {
    final typeString = json['type'] as String? ?? '';
    final eventType = AgUiEventType.fromString(typeString);

    return switch (eventType) {
      AgUiEventType.runStarted => RunStartedEvent.fromJson(json),
      AgUiEventType.runFinished => RunFinishedEvent.fromJson(json),
      AgUiEventType.runError => RunErrorEvent.fromJson(json),
      AgUiEventType.stepStarted => StepStartedEvent.fromJson(json),
      AgUiEventType.stepFinished => StepFinishedEvent.fromJson(json),
      AgUiEventType.textMessageStart => TextMessageStartEvent.fromJson(json),
      AgUiEventType.textMessageContent =>
        TextMessageContentEvent.fromJson(json),
      AgUiEventType.textMessageEnd => TextMessageEndEvent.fromJson(json),
      AgUiEventType.toolCallStart => ToolCallStartEvent.fromJson(json),
      AgUiEventType.toolCallArgs => ToolCallArgsEvent.fromJson(json),
      AgUiEventType.toolCallEnd => ToolCallEndEvent.fromJson(json),
      AgUiEventType.toolCallResult => ToolCallResultEvent.fromJson(json),
      AgUiEventType.stateSnapshot => StateSnapshotEvent.fromJson(json),
      AgUiEventType.stateDelta => StateDeltaEvent.fromJson(json),
      AgUiEventType.activitySnapshot => ActivitySnapshotEvent.fromJson(json),
      AgUiEventType.activityDelta => ActivityDeltaEvent.fromJson(json),
      AgUiEventType.messagesSnapshot => MessagesSnapshotEvent.fromJson(json),
      AgUiEventType.custom => CustomEvent.fromJson(json),
      AgUiEventType.unknown => UnknownEvent.fromJson(json),
    };
  }
}

// =============================================================================
// Run Lifecycle Events
// =============================================================================

/// Event emitted when a run starts.
@immutable
final class RunStartedEvent extends AgUiEvent {
  /// Creates a new [RunStartedEvent].
  const RunStartedEvent({
    required this.threadId,
    required this.runId,
  }) : super(type: AgUiEventType.runStarted);

  /// Creates a [RunStartedEvent] from JSON.
  factory RunStartedEvent.fromJson(Map<String, dynamic> json) {
    return RunStartedEvent(
      threadId: json['thread_id'] as String? ?? '',
      runId: json['run_id'] as String? ?? '',
    );
  }

  /// The ID of the thread this run belongs to.
  final String threadId;

  /// The ID of this run.
  final String runId;

  @override
  String toString() => 'RunStartedEvent(threadId: $threadId, runId: $runId)';
}

/// Event emitted when a run finishes successfully.
@immutable
final class RunFinishedEvent extends AgUiEvent {
  /// Creates a new [RunFinishedEvent].
  const RunFinishedEvent({
    required this.threadId,
    required this.runId,
    this.result,
  }) : super(type: AgUiEventType.runFinished);

  /// Creates a [RunFinishedEvent] from JSON.
  factory RunFinishedEvent.fromJson(Map<String, dynamic> json) {
    return RunFinishedEvent(
      threadId: json['thread_id'] as String? ?? '',
      runId: json['run_id'] as String? ?? '',
      result: json['result'],
    );
  }

  /// The ID of the thread this run belongs to.
  final String threadId;

  /// The ID of this run.
  final String runId;

  /// Optional result data from the run.
  final Object? result;

  @override
  String toString() => 'RunFinishedEvent(threadId: $threadId, runId: $runId)';
}

/// Event emitted when a run encounters an error.
@immutable
final class RunErrorEvent extends AgUiEvent {
  /// Creates a new [RunErrorEvent].
  const RunErrorEvent({
    required this.threadId,
    required this.runId,
    required this.message,
    this.code,
  }) : super(type: AgUiEventType.runError);

  /// Creates a [RunErrorEvent] from JSON.
  factory RunErrorEvent.fromJson(Map<String, dynamic> json) {
    return RunErrorEvent(
      threadId: json['thread_id'] as String? ?? '',
      runId: json['run_id'] as String? ?? '',
      message: json['message'] as String? ?? 'Unknown error',
      code: json['code'] as String?,
    );
  }

  /// The ID of the thread this run belongs to.
  final String threadId;

  /// The ID of this run.
  final String runId;

  /// The error message.
  final String message;

  /// Optional error code.
  final String? code;

  @override
  String toString() =>
      'RunErrorEvent(threadId: $threadId, runId: $runId, message: $message)';
}

// =============================================================================
// Step Events
// =============================================================================

/// Event emitted when a step starts.
@immutable
final class StepStartedEvent extends AgUiEvent {
  /// Creates a new [StepStartedEvent].
  const StepStartedEvent({
    required this.stepName,
  }) : super(type: AgUiEventType.stepStarted);

  /// Creates a [StepStartedEvent] from JSON.
  factory StepStartedEvent.fromJson(Map<String, dynamic> json) {
    return StepStartedEvent(
      stepName: json['step_name'] as String? ?? '',
    );
  }

  /// The name of the step that started.
  final String stepName;

  @override
  String toString() => 'StepStartedEvent(stepName: $stepName)';
}

/// Event emitted when a step finishes.
@immutable
final class StepFinishedEvent extends AgUiEvent {
  /// Creates a new [StepFinishedEvent].
  const StepFinishedEvent({
    required this.stepName,
  }) : super(type: AgUiEventType.stepFinished);

  /// Creates a [StepFinishedEvent] from JSON.
  factory StepFinishedEvent.fromJson(Map<String, dynamic> json) {
    return StepFinishedEvent(
      stepName: json['step_name'] as String? ?? '',
    );
  }

  /// The name of the step that finished.
  final String stepName;

  @override
  String toString() => 'StepFinishedEvent(stepName: $stepName)';
}

// =============================================================================
// Text Message Events
// =============================================================================

/// Event emitted when a text message starts streaming.
@immutable
final class TextMessageStartEvent extends AgUiEvent {
  /// Creates a new [TextMessageStartEvent].
  const TextMessageStartEvent({
    required this.messageId,
  }) : super(type: AgUiEventType.textMessageStart);

  /// Creates a [TextMessageStartEvent] from JSON.
  factory TextMessageStartEvent.fromJson(Map<String, dynamic> json) {
    return TextMessageStartEvent(
      messageId: json['message_id'] as String? ?? '',
    );
  }

  /// The ID of the message being streamed.
  final String messageId;

  @override
  String toString() => 'TextMessageStartEvent(messageId: $messageId)';
}

/// Event emitted when text content is added to a streaming message.
@immutable
final class TextMessageContentEvent extends AgUiEvent {
  /// Creates a new [TextMessageContentEvent].
  const TextMessageContentEvent({
    required this.messageId,
    required this.delta,
  }) : super(type: AgUiEventType.textMessageContent);

  /// Creates a [TextMessageContentEvent] from JSON.
  factory TextMessageContentEvent.fromJson(Map<String, dynamic> json) {
    return TextMessageContentEvent(
      messageId: json['message_id'] as String? ?? '',
      delta: json['delta'] as String? ?? '',
    );
  }

  /// The ID of the message being streamed.
  final String messageId;

  /// The text content delta to append.
  final String delta;

  @override
  String toString() =>
      'TextMessageContentEvent(messageId: $messageId, delta: $delta)';
}

/// Event emitted when a text message finishes streaming.
@immutable
final class TextMessageEndEvent extends AgUiEvent {
  /// Creates a new [TextMessageEndEvent].
  const TextMessageEndEvent({
    required this.messageId,
  }) : super(type: AgUiEventType.textMessageEnd);

  /// Creates a [TextMessageEndEvent] from JSON.
  factory TextMessageEndEvent.fromJson(Map<String, dynamic> json) {
    return TextMessageEndEvent(
      messageId: json['message_id'] as String? ?? '',
    );
  }

  /// The ID of the message that finished streaming.
  final String messageId;

  @override
  String toString() => 'TextMessageEndEvent(messageId: $messageId)';
}

// =============================================================================
// Tool Call Events
// =============================================================================

/// Event emitted when a tool call starts.
@immutable
final class ToolCallStartEvent extends AgUiEvent {
  /// Creates a new [ToolCallStartEvent].
  const ToolCallStartEvent({
    required this.toolCallId,
    required this.toolCallName,
    this.parentMessageId,
  }) : super(type: AgUiEventType.toolCallStart);

  /// Creates a [ToolCallStartEvent] from JSON.
  factory ToolCallStartEvent.fromJson(Map<String, dynamic> json) {
    return ToolCallStartEvent(
      toolCallId: json['tool_call_id'] as String? ?? '',
      toolCallName: json['tool_call_name'] as String? ?? '',
      parentMessageId: json['parent_message_id'] as String?,
    );
  }

  /// The ID of this tool call.
  final String toolCallId;

  /// The name of the tool being called.
  final String toolCallName;

  /// Optional ID of the parent message.
  final String? parentMessageId;

  @override
  String toString() =>
      'ToolCallStartEvent(toolCallId: $toolCallId, name: $toolCallName)';
}

/// Event emitted when tool call arguments are streamed.
@immutable
final class ToolCallArgsEvent extends AgUiEvent {
  /// Creates a new [ToolCallArgsEvent].
  const ToolCallArgsEvent({
    required this.toolCallId,
    required this.delta,
  }) : super(type: AgUiEventType.toolCallArgs);

  /// Creates a [ToolCallArgsEvent] from JSON.
  factory ToolCallArgsEvent.fromJson(Map<String, dynamic> json) {
    return ToolCallArgsEvent(
      toolCallId: json['tool_call_id'] as String? ?? '',
      delta: json['delta'] as String? ?? '',
    );
  }

  /// The ID of the tool call.
  final String toolCallId;

  /// The arguments delta to append.
  final String delta;

  @override
  String toString() =>
      'ToolCallArgsEvent(toolCallId: $toolCallId, delta: $delta)';
}

/// Event emitted when a tool call's arguments are complete.
@immutable
final class ToolCallEndEvent extends AgUiEvent {
  /// Creates a new [ToolCallEndEvent].
  const ToolCallEndEvent({
    required this.toolCallId,
  }) : super(type: AgUiEventType.toolCallEnd);

  /// Creates a [ToolCallEndEvent] from JSON.
  factory ToolCallEndEvent.fromJson(Map<String, dynamic> json) {
    return ToolCallEndEvent(
      toolCallId: json['tool_call_id'] as String? ?? '',
    );
  }

  /// The ID of the tool call that ended.
  final String toolCallId;

  @override
  String toString() => 'ToolCallEndEvent(toolCallId: $toolCallId)';
}

/// Event emitted when a tool call result is available.
@immutable
final class ToolCallResultEvent extends AgUiEvent {
  /// Creates a new [ToolCallResultEvent].
  const ToolCallResultEvent({
    required this.messageId,
    required this.toolCallId,
    required this.content,
  }) : super(type: AgUiEventType.toolCallResult);

  /// Creates a [ToolCallResultEvent] from JSON.
  factory ToolCallResultEvent.fromJson(Map<String, dynamic> json) {
    return ToolCallResultEvent(
      messageId: json['message_id'] as String? ?? '',
      toolCallId: json['tool_call_id'] as String? ?? '',
      content: json['content'] as String? ?? '',
    );
  }

  /// The ID of the tool result message.
  final String messageId;

  /// The ID of the tool call this result is for.
  final String toolCallId;

  /// The result content.
  final String content;

  @override
  String toString() =>
      'ToolCallResultEvent(toolCallId: $toolCallId, messageId: $messageId)';
}

// =============================================================================
// State Events
// =============================================================================

/// Event emitted with a complete state snapshot.
@immutable
final class StateSnapshotEvent extends AgUiEvent {
  /// Creates a new [StateSnapshotEvent].
  const StateSnapshotEvent({
    required this.snapshot,
  }) : super(type: AgUiEventType.stateSnapshot);

  /// Creates a [StateSnapshotEvent] from JSON.
  factory StateSnapshotEvent.fromJson(Map<String, dynamic> json) {
    return StateSnapshotEvent(
      snapshot: json['snapshot'] as Map<String, dynamic>? ?? {},
    );
  }

  /// The complete state snapshot.
  final Map<String, dynamic> snapshot;

  @override
  String toString() => 'StateSnapshotEvent(keys: ${snapshot.keys})';
}

/// Event emitted with a JSON Patch delta for state updates.
@immutable
final class StateDeltaEvent extends AgUiEvent {
  /// Creates a new [StateDeltaEvent].
  const StateDeltaEvent({
    required this.delta,
  }) : super(type: AgUiEventType.stateDelta);

  /// Creates a [StateDeltaEvent] from JSON.
  factory StateDeltaEvent.fromJson(Map<String, dynamic> json) {
    final deltaList = json['delta'] as List<dynamic>?;
    return StateDeltaEvent(
      delta: deltaList
              ?.map((e) => e as Map<String, dynamic>)
              .toList(growable: false) ??
          const [],
    );
  }

  /// The JSON Patch operations to apply.
  /// Each operation is a map with "op", "path", and optionally "value" keys.
  final List<Map<String, dynamic>> delta;

  @override
  String toString() => 'StateDeltaEvent(operations: ${delta.length})';
}

// =============================================================================
// Activity Events
// =============================================================================

/// Event emitted with a complete activity snapshot.
@immutable
final class ActivitySnapshotEvent extends AgUiEvent {
  /// Creates a new [ActivitySnapshotEvent].
  const ActivitySnapshotEvent({
    required this.messageId,
    required this.activityType,
    required this.content,
  }) : super(type: AgUiEventType.activitySnapshot);

  /// Creates an [ActivitySnapshotEvent] from JSON.
  factory ActivitySnapshotEvent.fromJson(Map<String, dynamic> json) {
    return ActivitySnapshotEvent(
      messageId: json['message_id'] as String? ?? '',
      activityType: json['activity_type'] as String? ?? '',
      content: json['content'] as Map<String, dynamic>? ?? {},
    );
  }

  /// The ID of the activity message.
  final String messageId;

  /// The type of activity.
  final String activityType;

  /// The activity content.
  final Map<String, dynamic> content;

  @override
  String toString() =>
      'ActivitySnapshotEvent(messageId: $messageId, type: $activityType)';
}

/// Event emitted with a JSON Patch delta for activity updates.
@immutable
final class ActivityDeltaEvent extends AgUiEvent {
  /// Creates a new [ActivityDeltaEvent].
  const ActivityDeltaEvent({
    required this.messageId,
    required this.activityType,
    required this.patch,
  }) : super(type: AgUiEventType.activityDelta);

  /// Creates an [ActivityDeltaEvent] from JSON.
  factory ActivityDeltaEvent.fromJson(Map<String, dynamic> json) {
    final patchList = json['patch'] as List<dynamic>?;
    return ActivityDeltaEvent(
      messageId: json['message_id'] as String? ?? '',
      activityType: json['activity_type'] as String? ?? '',
      patch: patchList
              ?.map((e) => e as Map<String, dynamic>)
              .toList(growable: false) ??
          const [],
    );
  }

  /// The ID of the activity message.
  final String messageId;

  /// The type of activity.
  final String activityType;

  /// The JSON Patch operations to apply.
  final List<Map<String, dynamic>> patch;

  @override
  String toString() =>
      'ActivityDeltaEvent(messageId: $messageId, operations: ${patch.length})';
}

// =============================================================================
// Messages Snapshot Event
// =============================================================================

/// Event emitted with a complete messages snapshot.
@immutable
final class MessagesSnapshotEvent extends AgUiEvent {
  /// Creates a new [MessagesSnapshotEvent].
  const MessagesSnapshotEvent({
    required this.messages,
  }) : super(type: AgUiEventType.messagesSnapshot);

  /// Creates a [MessagesSnapshotEvent] from JSON.
  factory MessagesSnapshotEvent.fromJson(Map<String, dynamic> json) {
    final messagesList = json['messages'] as List<dynamic>?;
    return MessagesSnapshotEvent(
      messages: messagesList
              ?.map((e) => e as Map<String, dynamic>)
              .toList(growable: false) ??
          const [],
    );
  }

  /// The complete list of messages.
  final List<Map<String, dynamic>> messages;

  @override
  String toString() => 'MessagesSnapshotEvent(count: ${messages.length})';
}

// =============================================================================
// Custom Event
// =============================================================================

/// Event for custom event types.
@immutable
final class CustomEvent extends AgUiEvent {
  /// Creates a new [CustomEvent].
  const CustomEvent({
    required this.name,
    required this.data,
  }) : super(type: AgUiEventType.custom);

  /// Creates a [CustomEvent] from JSON.
  factory CustomEvent.fromJson(Map<String, dynamic> json) {
    return CustomEvent(
      name: json['name'] as String? ?? '',
      data: json['data'] as Map<String, dynamic>? ?? {},
    );
  }

  /// The name of the custom event.
  final String name;

  /// The custom event data.
  final Map<String, dynamic> data;

  @override
  String toString() => 'CustomEvent(name: $name)';
}

// =============================================================================
// Unknown Event
// =============================================================================

/// Event for unrecognized event types.
@immutable
final class UnknownEvent extends AgUiEvent {
  /// Creates a new [UnknownEvent].
  const UnknownEvent({
    required this.rawType,
    required this.rawJson,
  }) : super(type: AgUiEventType.unknown);

  /// Creates an [UnknownEvent] from JSON.
  factory UnknownEvent.fromJson(Map<String, dynamic> json) {
    return UnknownEvent(
      rawType: json['type'] as String? ?? '',
      rawJson: json,
    );
  }

  /// The raw type string from the event.
  final String rawType;

  /// The raw JSON data.
  final Map<String, dynamic> rawJson;

  @override
  String toString() => 'UnknownEvent(rawType: $rawType)';
}
