import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// State for an active AG-UI run.
///
/// This is a sealed class hierarchy with 3 states:
/// - [IdleState]: No active run (sentinel state)
/// - [RunningState]: Run is executing
/// - [CompletedState]: Run finished (success, error, or cancelled)
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (state) {
///   case IdleState():
///     // No active run
///   case RunningState(:final threadId, :final streaming):
///     // Run is active
///   case CompletedState(:final result):
///     switch (result) {
///       case Success():
///         // Completed successfully
///       case Failed(:final errorMessage):
///         // Failed with error
///       case Cancelled(:final reason):
///         // Cancelled by user
///     }
/// }
/// ```
@immutable
sealed class ActiveRunState {
  const ActiveRunState();

  /// The conversation (domain state). IdleState returns an empty sentinel.
  Conversation get conversation;

  /// The streaming state (application layer). IdleState returns NotStreaming.
  StreamingState get streaming;

  /// All messages from the conversation.
  List<ChatMessage> get messages => conversation.messages;

  /// Tool calls currently being executed.
  List<ToolCallInfo> get activeToolCalls => conversation.toolCalls;

  /// Whether a run is currently executing.
  bool get isRunning => this is RunningState;
}

/// No run is currently active. Sentinel state.
///
/// IdleState intentionally has no threadId - it represents "no conversation".
/// Widgets needing threadId should only access [RunningState] or
/// [CompletedState].
@immutable
class IdleState extends ActiveRunState {
  /// Creates an idle state.
  const IdleState();

  @override
  Conversation get conversation => Conversation.empty(threadId: '');

  @override
  StreamingState get streaming => const NotStreaming();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is IdleState;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'IdleState()';
}

/// A run is currently executing.
///
/// Contains the conversation (domain state) and streaming state (application
/// layer).
@immutable
class RunningState extends ActiveRunState {
  /// Creates a running state.
  const RunningState({
    required this.conversation,
    this.streaming = const NotStreaming(),
  });

  @override
  final Conversation conversation;

  @override
  final StreamingState streaming;

  /// The ID of the thread this run belongs to.
  String get threadId => conversation.threadId;

  /// The ID of this run.
  String get runId => switch (conversation.status) {
        Running(:final runId) => runId,
        _ => throw StateError('RunningState must have Running status'),
      };

  /// Whether text is actively streaming.
  bool get isStreaming => streaming is Streaming;

  /// Creates a copy with the given fields replaced.
  RunningState copyWith({
    Conversation? conversation,
    StreamingState? streaming,
  }) {
    return RunningState(
      conversation: conversation ?? this.conversation,
      streaming: streaming ?? this.streaming,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RunningState &&
          conversation == other.conversation &&
          streaming == other.streaming;

  @override
  int get hashCode => Object.hash(conversation, streaming);

  @override
  String toString() => 'RunningState(threadId: $threadId, '
      'messages: ${messages.length}, streaming: $streaming)';
}

/// A run has completed (success, error, or cancelled).
///
/// Use [result] to determine the outcome:
/// ```dart
/// switch (state.result) {
///   case Success():
///     // Completed successfully
///   case FailedResult(:final errorMessage):
///     // Failed with error
///   case CancelledResult(:final reason):
///     // Cancelled by user
/// }
/// ```
@immutable
class CompletedState extends ActiveRunState {
  /// Creates a completed state.
  const CompletedState({
    required this.conversation,
    required this.result,
    this.streaming = const NotStreaming(),
  });

  @override
  final Conversation conversation;

  @override
  final StreamingState streaming;

  /// The result of the run.
  final CompletionResult result;

  /// The ID of the thread this run belonged to.
  String get threadId => conversation.threadId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CompletedState &&
          conversation == other.conversation &&
          streaming == other.streaming &&
          result == other.result;

  @override
  int get hashCode => Object.hash(conversation, streaming, result);

  @override
  String toString() => 'CompletedState(threadId: $threadId, '
      'result: $result, messages: ${messages.length})';
}

/// Result of a completed run.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (result) {
///   case Success():
///     // Completed successfully
///   case FailedResult(:final errorMessage):
///     // Failed with error
///   case CancelledResult(:final reason):
///     // Cancelled by user
/// }
/// ```
@immutable
sealed class CompletionResult {
  const CompletionResult();
}

/// The run completed successfully.
@immutable
class Success extends CompletionResult {
  const Success();

  @override
  bool operator ==(Object other) => identical(this, other) || other is Success;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'Success()';
}

/// The run failed with an error.
@immutable
class FailedResult extends CompletionResult {
  const FailedResult({required this.errorMessage});

  /// The error message describing what went wrong.
  final String errorMessage;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FailedResult && errorMessage == other.errorMessage;

  @override
  int get hashCode => Object.hash(runtimeType, errorMessage);

  @override
  String toString() => 'FailedResult(errorMessage: $errorMessage)';
}

/// The run was cancelled by the user.
@immutable
class CancelledResult extends CompletionResult {
  const CancelledResult({required this.reason});

  /// The reason for cancellation.
  final String reason;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CancelledResult && reason == other.reason;

  @override
  int get hashCode => Object.hash(runtimeType, reason);

  @override
  String toString() => 'CancelledResult(reason: $reason)';
}
