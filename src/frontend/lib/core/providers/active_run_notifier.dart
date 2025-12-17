import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';

/// Manages the lifecycle of an active AG-UI run.
///
/// This notifier:
/// - Creates [Thread] instances for SSE streaming
/// - Processes AG-UI events from the backend
/// - Updates state as messages stream in
/// - Handles cancellation and errors
///
/// Usage:
/// ```dart
/// final notifier = ref.read(activeRunNotifierProvider.notifier);
/// await notifier.startRun(
///   roomId: 'room-123',
///   threadId: 'thread-456',
///   userMessage: 'Hello!',
/// );
/// ```
class ActiveRunNotifier extends StateNotifier<ActiveRunState> {
  /// Creates an active run notifier.
  ActiveRunNotifier({
    required HttpTransport transport,
  })  : _transport = transport,
        super(const ActiveRunState.idle());

  final HttpTransport _transport;
  Thread? _thread;
  CancelToken? _cancelToken;
  StreamSubscription<AgUiEvent>? _eventSubscription;

  /// Starts a new run with the given message.
  ///
  /// Creates a [Thread], starts SSE streaming, and processes events
  /// to update the state.
  ///
  /// Throws [StateError] if a run is already active. Call [cancelRun] first.
  Future<void> startRun({
    required String roomId,
    required String threadId,
    required String userMessage,
    Map<String, dynamic>? initialState,
  }) async {
    if (state.isRunning) {
      throw StateError(
        'Cannot start run: a run is already active. '
        'Call cancelRun() first.',
      );
    }

    // Cancel any previous subscription
    await _eventSubscription?.cancel();
    _cancelToken?.cancel();

    // Create new cancel token and thread
    _cancelToken = CancelToken();
    _thread = Thread(
      transport: _transport,
      roomId: roomId,
      threadId: threadId,
    );

    // Generate run ID
    final runId = 'run_${DateTime.now().millisecondsSinceEpoch}';

    // Set running state
    state = ActiveRunState.running(
      threadId: threadId,
      runId: runId,
    );

    try {
      // Start streaming
      final eventStream = _thread!.run(
        runId: runId,
        userMessage: userMessage,
        initialState: initialState,
        cancelToken: _cancelToken,
      );

      // Process events
      _eventSubscription = eventStream.listen(
        _processEvent,
        onError: (Object error, StackTrace stackTrace) {
          state = state.copyWith(
            status: ThreadRunStatus.error,
            errorMessage: error.toString(),
          );
        },
        onDone: () {
          // If stream ends without RUN_FINISHED or RUN_ERROR,
          // mark as finished
          if (state.isRunning) {
            state = state.copyWith(status: ThreadRunStatus.finished);
          }
        },
        cancelOnError: false,
      );
    } on CancelledException {
      // User cancelled - already handled in cancelRun
      state = ActiveRunState.cancelled(messages: state.messages);
    } catch (e) {
      state = state.copyWith(
        status: ThreadRunStatus.error,
        errorMessage: e.toString(),
      );
    }
  }

  /// Cancels the active run.
  ///
  /// Preserves all completed messages but clears streaming state.
  Future<void> cancelRun() async {
    _cancelToken?.cancel();
    await _eventSubscription?.cancel();
    _eventSubscription = null;

    state = ActiveRunState.cancelled(messages: state.messages);
  }

  /// Resets to idle state, clearing all messages and state.
  void reset() {
    _cancelToken?.cancel();
    _eventSubscription?.cancel();
    _eventSubscription = null;
    _thread = null;

    state = const ActiveRunState.idle();
  }

  /// Processes a single AG-UI event and updates state accordingly.
  void _processEvent(AgUiEvent event) {
    // Store raw event (for AM5 Detail panel)
    final updatedRawEvents = [...state.rawEvents, event];

    switch (event) {
      case RunStartedEvent():
        // Run started - status already set to running
        state = state.copyWith(rawEvents: updatedRawEvents);

      case RunFinishedEvent():
        // Run finished successfully
        state = state.copyWith(
          status: ThreadRunStatus.finished,
          isTextStreaming: false,
          streamingText: null,
          currentMessageId: null,
          rawEvents: updatedRawEvents,
        );

      case RunErrorEvent(:final message):
        // Run encountered an error
        state = state.copyWith(
          status: ThreadRunStatus.error,
          errorMessage: message,
          isTextStreaming: false,
          streamingText: null,
          currentMessageId: null,
          rawEvents: updatedRawEvents,
        );

      case TextMessageStartEvent(:final messageId):
        // Start streaming a new text message
        state = state.copyWith(
          currentMessageId: messageId,
          streamingText: '',
          isTextStreaming: true,
          rawEvents: updatedRawEvents,
        );

      case TextMessageContentEvent(:final messageId, :final delta):
        // Append streaming text content
        if (state.currentMessageId == messageId) {
          final newText = (state.streamingText ?? '') + delta;
          state = state.copyWith(
            streamingText: newText,
            rawEvents: updatedRawEvents,
          );
        }

      case TextMessageEndEvent(:final messageId):
        // Complete the streaming message
        if (state.currentMessageId == messageId && state.streamingText != null) {
          final newMessage = ChatMessage.text(
            id: messageId,
            user: ChatUser.assistant,
            text: state.streamingText!,
          );

          state = state.copyWith(
            messages: [...state.messages, newMessage],
            currentMessageId: null,
            streamingText: null,
            isTextStreaming: false,
            rawEvents: updatedRawEvents,
          );
        }

      case ToolCallStartEvent(:final toolCallId, :final toolCallName):
        // Tool call started
        final toolCall = ToolCallInfo(
          id: toolCallId,
          name: toolCallName,
          arguments: '',
          status: ToolCallStatus.pending,
        );
        state = state.copyWith(
          activeToolCalls: [...state.activeToolCalls, toolCall],
          rawEvents: updatedRawEvents,
        );

      case ToolCallEndEvent(:final toolCallId):
        // Tool call finished
        final updatedToolCalls = state.activeToolCalls
            .where((tc) => tc.id != toolCallId)
            .toList();
        state = state.copyWith(
          activeToolCalls: updatedToolCalls,
          rawEvents: updatedRawEvents,
        );

      case StateSnapshotEvent(:final snapshot):
        // State snapshot received
        state = state.copyWith(
          state: Map<String, dynamic>.from(snapshot),
          rawEvents: updatedRawEvents,
        );

      case StateDeltaEvent():
      case StepStartedEvent():
      case StepFinishedEvent():
      case ToolCallArgsEvent():
      case ToolCallResultEvent():
      case ActivitySnapshotEvent():
      case ActivityDeltaEvent():
      case MessagesSnapshotEvent():
      case CustomEvent():
      case UnknownEvent():
        // Store event but don't process (AM3 doesn't need these)
        state = state.copyWith(rawEvents: updatedRawEvents);
    }
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    _cancelToken?.cancel();
    super.dispose();
  }
}
