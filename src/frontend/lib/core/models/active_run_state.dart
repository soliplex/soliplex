import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// State for an active AG-UI run.
///
/// Represents the current state of a streaming chat run, including:
/// - Run status and metadata
/// - Accumulated messages
/// - Streaming indicators
/// - Error state
///
/// This state is managed by the active run notifier which processes AG-UI
/// events from the backend SSE stream.
@immutable
class ActiveRunState {
  /// Creates an active run state.
  const ActiveRunState({
    required this.status,
    required this.messages,
    this.threadId,
    this.runId,
    this.errorMessage,
    this.currentMessageId,
    this.streamingText,
    this.isTextStreaming = false,
    this.activeToolCalls = const [],
    this.state = const {},
    this.rawEvents = const [],
  });

  /// Creates an idle state with no active run.
  const ActiveRunState.idle()
      : status = ThreadRunStatus.idle,
        messages = const [],
        threadId = null,
        runId = null,
        errorMessage = null,
        currentMessageId = null,
        streamingText = null,
        isTextStreaming = false,
        activeToolCalls = const [],
        state = const {},
        rawEvents = const [];

  /// Creates a running state for the given thread.
  const ActiveRunState.running({
    required this.threadId,
    required this.runId,
    this.messages = const [],
  })  : status = ThreadRunStatus.running,
        errorMessage = null,
        currentMessageId = null,
        streamingText = null,
        isTextStreaming = false,
        activeToolCalls = const [],
        state = const {},
        rawEvents = const [];

  /// Creates a cancelled state preserving existing messages.
  const ActiveRunState.cancelled({required this.messages})
      : status = ThreadRunStatus.idle,
        threadId = null,
        runId = null,
        errorMessage = 'Cancelled by user',
        currentMessageId = null,
        streamingText = null,
        isTextStreaming = false,
        activeToolCalls = const [],
        state = const {},
        rawEvents = const [];

  /// The ID of the thread this run belongs to.
  final String? threadId;

  /// The ID of this run.
  final String? runId;

  /// The current run status.
  final ThreadRunStatus status;

  /// All messages accumulated during this run.
  final List<ChatMessage> messages;

  /// Error message if status is error.
  final String? errorMessage;

  /// The ID of the message currently being streamed.
  final String? currentMessageId;

  /// The current partial text being streamed.
  final String? streamingText;

  /// Whether text is actively streaming.
  final bool isTextStreaming;

  /// Tool calls currently being executed.
  final List<ToolCallInfo> activeToolCalls;

  /// Latest state snapshot from backend.
  ///
  /// This field is included for AM5 (Detail panel) but unused in AM3.
  final Map<String, dynamic> state;

  /// All AG-UI events received during this run.
  ///
  /// This field is included for AM5 (Detail panel) but unused in AM3.
  final List<AgUiEvent> rawEvents;

  /// Whether the run is idle (no active run).
  bool get isIdle => status == ThreadRunStatus.idle;

  /// Whether the run is currently executing.
  bool get isRunning => status == ThreadRunStatus.running;

  /// Whether the run has finished successfully.
  bool get isFinished => status == ThreadRunStatus.finished;

  /// Whether the run encountered an error.
  bool get hasError => status == ThreadRunStatus.error;

  /// Creates a copy with the given fields replaced.
  ActiveRunState copyWith({
    String? threadId,
    String? runId,
    ThreadRunStatus? status,
    List<ChatMessage>? messages,
    String? errorMessage,
    String? currentMessageId,
    String? streamingText,
    bool? isTextStreaming,
    List<ToolCallInfo>? activeToolCalls,
    Map<String, dynamic>? state,
    List<AgUiEvent>? rawEvents,
  }) {
    return ActiveRunState(
      threadId: threadId ?? this.threadId,
      runId: runId ?? this.runId,
      status: status ?? this.status,
      messages: messages ?? this.messages,
      errorMessage: errorMessage ?? this.errorMessage,
      currentMessageId: currentMessageId ?? this.currentMessageId,
      streamingText: streamingText ?? this.streamingText,
      isTextStreaming: isTextStreaming ?? this.isTextStreaming,
      activeToolCalls: activeToolCalls ?? this.activeToolCalls,
      state: state ?? this.state,
      rawEvents: rawEvents ?? this.rawEvents,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is ActiveRunState &&
        other.threadId == threadId &&
        other.runId == runId &&
        other.status == status &&
        other.messages == messages &&
        other.errorMessage == errorMessage &&
        other.currentMessageId == currentMessageId &&
        other.streamingText == streamingText &&
        other.isTextStreaming == isTextStreaming &&
        other.activeToolCalls == activeToolCalls &&
        other.state == state &&
        other.rawEvents == rawEvents;
  }

  @override
  int get hashCode {
    return Object.hash(
      threadId,
      runId,
      status,
      messages,
      errorMessage,
      currentMessageId,
      streamingText,
      isTextStreaming,
      activeToolCalls,
      state,
      rawEvents,
    );
  }

  @override
  String toString() {
    return 'ActiveRunState('
        'status: $status, '
        'threadId: $threadId, '
        'runId: $runId, '
        'messages: ${messages.length}, '
        'isTextStreaming: $isTextStreaming, '
        'activeToolCalls: ${activeToolCalls.length}'
        ')';
  }
}
