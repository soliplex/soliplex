import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Shared context that persists across all run states.
///
/// Contains accumulated data that is preserved regardless of run state:
/// - Messages from the conversation
/// - Raw AG-UI events for debugging/detail panel
/// - State snapshots from the backend
/// - Active tool calls
@immutable
class RunContext {
  /// Creates a run context with the given data.
  const RunContext({
    this.messages = const [],
    this.rawEvents = const [],
    this.state = const {},
    this.activeToolCalls = const [],
  });

  /// Empty context with no data.
  static const empty = RunContext();

  /// All messages accumulated during runs.
  final List<ChatMessage> messages;

  /// All AG-UI events received (for AM5 Detail panel).
  final List<AgUiEvent> rawEvents;

  /// Latest state snapshot from backend.
  final Map<String, dynamic> state;

  /// Tool calls currently being executed.
  final List<ToolCallInfo> activeToolCalls;

  /// Creates a copy with the given fields replaced.
  RunContext copyWith({
    List<ChatMessage>? messages,
    List<AgUiEvent>? rawEvents,
    Map<String, dynamic>? state,
    List<ToolCallInfo>? activeToolCalls,
  }) {
    return RunContext(
      messages: messages ?? this.messages,
      rawEvents: rawEvents ?? this.rawEvents,
      state: state ?? this.state,
      activeToolCalls: activeToolCalls ?? this.activeToolCalls,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RunContext &&
          runtimeType == other.runtimeType &&
          messages == other.messages &&
          rawEvents == other.rawEvents &&
          state == other.state &&
          activeToolCalls == other.activeToolCalls;

  @override
  int get hashCode => Object.hash(messages, rawEvents, state, activeToolCalls);
}

/// Text streaming state - eliminates nullable messageId/streamingText.
///
/// Use pattern matching to handle streaming vs not streaming:
/// ```dart
/// switch (state.textStreaming) {
///   case NotStreaming():
///     // No text being streamed
///   case Streaming(:final messageId, :final text):
///     // Text is streaming for messageId
/// }
/// ```
@immutable
sealed class TextStreaming {
  const TextStreaming();
}

/// No text message is currently being streamed.
@immutable
class NotStreaming extends TextStreaming {
  const NotStreaming();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is NotStreaming;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NotStreaming()';
}

/// A text message is being streamed.
@immutable
class Streaming extends TextStreaming {
  const Streaming({required this.messageId, required this.text});

  /// The ID of the message being streamed.
  final String messageId;

  /// The accumulated text content so far.
  final String text;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Streaming &&
          runtimeType == other.runtimeType &&
          messageId == other.messageId &&
          text == other.text;

  @override
  int get hashCode => Object.hash(messageId, text);

  @override
  String toString() => 'Streaming(messageId: $messageId, text: ${text.length} '
      'chars)';
}

/// State for an active AG-UI run.
///
/// This is a sealed class hierarchy with 3 states:
/// - [IdleState]: No active run
/// - [RunningState]: Run is executing
/// - [CompletedState]: Run finished (success, error, or cancelled)
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (state) {
///   case IdleState():
///     // No active run
///   case RunningState(:final threadId, :final runId, :final textStreaming):
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
  const ActiveRunState({required this.context});

  /// Shared context containing messages, events, and state.
  final RunContext context;

  // Convenience getters for common context fields
  /// All messages accumulated during runs.
  List<ChatMessage> get messages => context.messages;

  /// All AG-UI events received.
  List<AgUiEvent> get rawEvents => context.rawEvents;

  /// Latest state snapshot from backend.
  Map<String, dynamic> get state => context.state;

  /// Tool calls currently being executed.
  List<ToolCallInfo> get activeToolCalls => context.activeToolCalls;

  /// Whether the run is currently executing.
  bool get isRunning => this is RunningState;
}

/// No run is currently active.
///
/// This is the initial state before any run has started.
@immutable
class IdleState extends ActiveRunState {
  /// Creates an idle state with optional context.
  const IdleState({super.context = RunContext.empty});

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is IdleState &&
          runtimeType == other.runtimeType &&
          context == other.context;

  @override
  int get hashCode => Object.hash(runtimeType, context);

  @override
  String toString() => 'IdleState(messages: ${messages.length})';
}

/// A run is currently executing.
///
/// Contains thread/run identifiers and text streaming state.
@immutable
class RunningState extends ActiveRunState {
  /// Creates a running state.
  const RunningState({
    required this.threadId,
    required this.runId,
    required super.context,
    this.textStreaming = const NotStreaming(),
  });

  /// The ID of the thread this run belongs to.
  final String threadId;

  /// The ID of this run.
  final String runId;

  /// Current text streaming state.
  final TextStreaming textStreaming;

  /// Whether text is actively streaming.
  bool get isTextStreaming => textStreaming is Streaming;

  /// Creates a copy with the given fields replaced.
  RunningState copyWith({
    String? threadId,
    String? runId,
    RunContext? context,
    TextStreaming? textStreaming,
  }) {
    return RunningState(
      threadId: threadId ?? this.threadId,
      runId: runId ?? this.runId,
      context: context ?? this.context,
      textStreaming: textStreaming ?? this.textStreaming,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RunningState &&
          runtimeType == other.runtimeType &&
          threadId == other.threadId &&
          runId == other.runId &&
          context == other.context &&
          textStreaming == other.textStreaming;

  @override
  int get hashCode => Object.hash(threadId, runId, context, textStreaming);

  @override
  String toString() => 'RunningState(threadId: $threadId, runId: $runId, '
      'messages: ${messages.length}, textStreaming: $textStreaming)';
}

/// A run has completed (success, error, or cancelled).
///
/// Use [result] to determine the outcome:
/// ```dart
/// switch (state.result) {
///   case Success():
///     // Completed successfully
///   case Failed(:final errorMessage):
///     // Failed with error
///   case Cancelled(:final reason):
///     // Cancelled by user
/// }
/// ```
@immutable
class CompletedState extends ActiveRunState {
  /// Creates a completed state.
  const CompletedState({
    required this.threadId,
    required this.runId,
    required super.context,
    required this.result,
  });

  /// The ID of the thread this run belonged to.
  final String threadId;

  /// The ID of the completed run.
  final String runId;

  /// The result of the run.
  final CompletionResult result;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CompletedState &&
          runtimeType == other.runtimeType &&
          threadId == other.threadId &&
          runId == other.runId &&
          context == other.context &&
          result == other.result;

  @override
  int get hashCode => Object.hash(threadId, runId, context, result);

  @override
  String toString() => 'CompletedState(threadId: $threadId, runId: $runId, '
      'result: $result, messages: ${messages.length})';
}

/// Result of a completed run.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (result) {
///   case Success():
///     // Completed successfully
///   case Failed(:final errorMessage):
///     // Failed with error
///   case Cancelled(:final reason):
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
  bool operator ==(Object other) =>
      identical(this, other) || other is Success;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'Success()';
}

/// The run failed with an error.
@immutable
class Failed extends CompletionResult {
  const Failed({required this.errorMessage});

  /// The error message describing what went wrong.
  final String errorMessage;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Failed &&
          runtimeType == other.runtimeType &&
          errorMessage == other.errorMessage;

  @override
  int get hashCode => Object.hash(runtimeType, errorMessage);

  @override
  String toString() => 'Failed(errorMessage: $errorMessage)';
}

/// The run was cancelled by the user.
@immutable
class Cancelled extends CompletionResult {
  const Cancelled({required this.reason});

  /// The reason for cancellation.
  final String reason;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Cancelled &&
          runtimeType == other.runtimeType &&
          reason == other.reason;

  @override
  int get hashCode => Object.hash(runtimeType, reason);

  @override
  String toString() => 'Cancelled(reason: $reason)';
}
