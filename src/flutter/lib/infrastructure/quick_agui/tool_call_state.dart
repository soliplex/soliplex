import 'package:ag_ui/ag_ui.dart';

/// Lifecycle state for a tool call.
///
/// State machine: RECEIVED -> EXECUTING -> COMPLETED
///                              |
///                              v
///                           FAILED
enum ToolCallState {
  /// Tool call has been received from the server but not yet executed.
  received,

  /// Tool call is currently being executed.
  executing,

  /// Tool call completed successfully.
  completed,

  /// Tool call failed during execution.
  failed,
}

/// A tool call with lifecycle state tracking.
///
/// Wraps an AG-UI ToolCall with state, timestamps, and optional result/error.
class TrackedToolCall {
  const TrackedToolCall({
    required this.call,
    required this.state,
    required this.receivedAt,
    this.executionStartedAt,
    this.completedAt,
    this.result,
    this.error,
  });

  /// Create a new tracked tool call in the received state.
  factory TrackedToolCall.received(ToolCall call) {
    return TrackedToolCall(
      call: call,
      state: ToolCallState.received,
      receivedAt: DateTime.now(),
    );
  }
  final ToolCall call;
  final ToolCallState state;
  final DateTime receivedAt;
  final DateTime? executionStartedAt;
  final DateTime? completedAt;
  final ToolMessage? result;
  final String? error;

  /// Tool call ID (convenience accessor).
  String get id => call.id;

  /// Tool name (convenience accessor).
  String get toolName => call.function.name;

  /// Create a copy with updated fields.
  TrackedToolCall copyWith({
    ToolCallState? state,
    DateTime? executionStartedAt,
    DateTime? completedAt,
    ToolMessage? result,
    String? error,
  }) {
    return TrackedToolCall(
      call: call,
      state: state ?? this.state,
      receivedAt: receivedAt,
      executionStartedAt: executionStartedAt ?? this.executionStartedAt,
      completedAt: completedAt ?? this.completedAt,
      result: result ?? this.result,
      error: error ?? this.error,
    );
  }

  /// Transition to executing state.
  TrackedToolCall toExecuting() {
    assert(
      state == ToolCallState.received,
      'Can only execute from received state',
    );
    return copyWith(
      state: ToolCallState.executing,
      executionStartedAt: DateTime.now(),
    );
  }

  /// Transition to completed state with result.
  TrackedToolCall toCompleted(ToolMessage result) {
    assert(
      state == ToolCallState.executing,
      'Can only complete from executing state',
    );
    return copyWith(
      state: ToolCallState.completed,
      completedAt: DateTime.now(),
      result: result,
    );
  }

  /// Transition to failed state with error.
  TrackedToolCall toFailed(String error) {
    assert(
      state == ToolCallState.executing,
      'Can only fail from executing state',
    );
    return copyWith(
      state: ToolCallState.failed,
      completedAt: DateTime.now(),
      error: error,
    );
  }
}

/// Event emitted when a tool call's state changes.
class ToolCallStateChange {
  const ToolCallStateChange({
    required this.toolCallId,
    required this.toolName,
    required this.previousState,
    required this.newState,
    required this.timestamp,
    this.result,
    this.error,
  });
  final String toolCallId;
  final String toolName;
  final ToolCallState previousState;
  final ToolCallState newState;
  final DateTime timestamp;
  final ToolMessage? result;
  final String? error;

  /// Whether this is a transition to an executing state.
  bool get isStarting => newState == ToolCallState.executing;

  /// Whether this is a transition to a terminal state (completed or failed).
  bool get isEnding =>
      newState == ToolCallState.completed || newState == ToolCallState.failed;

  /// Whether this represents a successful completion.
  bool get isSuccess => newState == ToolCallState.completed;

  /// Whether this represents a failure.
  bool get isFailure => newState == ToolCallState.failed;
}
