import 'dart:typed_data';

import 'package:equatable/equatable.dart';

/// AG-UI Event Types as defined by the protocol.
enum AgUiEventType {
  // Text message events
  textMessageStart,
  textMessageContent,
  textMessageEnd,

  // Tool call events (for GenUI)
  toolCallStart,
  toolCallArgs,
  toolCallEnd,

  // State management
  stateUpdate,

  // Connection events
  runStarted,
  runFinished,
  runError,

  // Unknown/future event types
  unknown,
}

/// Base class for all AG-UI events.
sealed class AgUiEvent extends Equatable {
  const AgUiEvent({this.messageId, DateTime? timestamp})
    : timestamp = timestamp ?? const _DefaultDateTime();
  final String? messageId;
  final DateTime timestamp;

  AgUiEventType get type;

  @override
  List<Object?> get props => [messageId, timestamp, type];
}

// Helper class for default timestamp
class _DefaultDateTime implements DateTime {
  const _DefaultDateTime();

  @override
  dynamic noSuchMethod(Invocation invocation) => DateTime.now();
}

/// Text message started - signals a new text response from agent.
class TextMessageStartEvent extends AgUiEvent {
  const TextMessageStartEvent({
    super.messageId,
    super.timestamp,
    this.role = 'assistant',
  });
  final String role;

  @override
  AgUiEventType get type => AgUiEventType.textMessageStart;

  @override
  List<Object?> get props => [...super.props, role];
}

/// Text message content chunk - streaming text delta.
class TextMessageContentEvent extends AgUiEvent {
  const TextMessageContentEvent({
    required this.delta,
    super.messageId,
    super.timestamp,
  });
  final String delta;

  @override
  AgUiEventType get type => AgUiEventType.textMessageContent;

  @override
  List<Object?> get props => [...super.props, delta];
}

/// Text message ended - finalize the text message.
class TextMessageEndEvent extends AgUiEvent {
  const TextMessageEndEvent({super.messageId, super.timestamp});

  @override
  AgUiEventType get type => AgUiEventType.textMessageEnd;
}

/// Tool call started - agent is generating UI component.
class ToolCallStartEvent extends AgUiEvent {
  const ToolCallStartEvent({
    required this.toolCallId,
    required this.toolName,
    super.messageId,
    super.timestamp,
  });
  final String toolCallId;
  final String toolName;

  @override
  AgUiEventType get type => AgUiEventType.toolCallStart;

  @override
  List<Object?> get props => [...super.props, toolCallId, toolName];
}

/// Tool call arguments - contains tool arguments chunk (streamed JSON).
class ToolCallArgsEvent extends AgUiEvent {
  const ToolCallArgsEvent({
    required this.toolCallId,
    required this.argsChunk,
    super.messageId,
    super.timestamp,
  });
  final String toolCallId;
  final String argsChunk;

  @override
  AgUiEventType get type => AgUiEventType.toolCallArgs;

  @override
  List<Object?> get props => [...super.props, toolCallId, argsChunk];
}

/// Tool call ended - tool arguments complete, ready to execute.
class ToolCallEndEvent extends AgUiEvent {
  const ToolCallEndEvent({
    required this.toolCallId,
    super.messageId,
    super.timestamp,
  });
  final String toolCallId;

  @override
  AgUiEventType get type => AgUiEventType.toolCallEnd;

  @override
  List<Object?> get props => [...super.props, toolCallId];
}

/// State update - partial data update for existing GenUI widget.
class StateUpdateEvent extends AgUiEvent {
  const StateUpdateEvent({
    required this.targetId,
    required this.updates,
    super.messageId,
    super.timestamp,
  });
  final String targetId;
  final Map<String, dynamic> updates;

  @override
  AgUiEventType get type => AgUiEventType.stateUpdate;

  @override
  List<Object?> get props => [...super.props, targetId, updates];
}

/// Run started - agent has begun processing.
class RunStartedEvent extends AgUiEvent {
  const RunStartedEvent({
    required this.runId,
    super.messageId,
    super.timestamp,
  });
  final String runId;

  @override
  AgUiEventType get type => AgUiEventType.runStarted;

  @override
  List<Object?> get props => [...super.props, runId];
}

/// Run finished - agent has completed processing.
class RunFinishedEvent extends AgUiEvent {
  const RunFinishedEvent({
    required this.runId,
    super.messageId,
    super.timestamp,
  });
  final String runId;

  @override
  AgUiEventType get type => AgUiEventType.runFinished;

  @override
  List<Object?> get props => [...super.props, runId];
}

/// Run error - agent encountered an error.
class RunErrorEvent extends AgUiEvent {
  const RunErrorEvent({
    required this.errorCode,
    required this.errorMessage,
    super.messageId,
    super.timestamp,
  });
  final String errorCode;
  final String errorMessage;

  @override
  AgUiEventType get type => AgUiEventType.runError;

  @override
  List<Object?> get props => [...super.props, errorCode, errorMessage];
}

/// Unknown event type - for forward compatibility.
class UnknownEvent extends AgUiEvent {
  const UnknownEvent({
    required this.rawType,
    required this.rawData,
    super.messageId,
    super.timestamp,
  });
  final String rawType;
  final Map<String, dynamic> rawData;

  @override
  AgUiEventType get type => AgUiEventType.unknown;

  @override
  List<Object?> get props => [...super.props, rawType, rawData];
}

/// Parsed GenUI payload from tool call.
class GenUiPayload extends Equatable {
  const GenUiPayload({
    required this.toolCallId,
    required this.widgetName,
    this.libraryName = 'agent',
    this.libraryBlob,
    this.libraryText,
    this.initialData = const {},
  });
  final String toolCallId;
  final String widgetName;
  final String libraryName;
  final Uint8List? libraryBlob;
  final String? libraryText;
  final Map<String, dynamic> initialData;

  bool get hasBinaryLibrary => libraryBlob != null;
  bool get hasTextLibrary => libraryText != null;
  bool get hasLibrary => hasBinaryLibrary || hasTextLibrary;

  @override
  List<Object?> get props => [
    toolCallId,
    widgetName,
    libraryName,
    libraryBlob,
    libraryText,
    initialData,
  ];
}
