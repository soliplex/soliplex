import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

/// Internal state representing the notifier's resource management.
///
/// This sealed class ensures proper lifecycle management of the AgUiClient,
/// CancelToken, and StreamSubscription without nullable fields.
sealed class NotifierInternalState {
  const NotifierInternalState();
}

/// No active run - initial state or after reset.
@immutable
class IdleInternalState extends NotifierInternalState {
  const IdleInternalState();
}

/// A run is currently active with associated resources.
///
/// Not marked as @immutable because it holds mutable StreamSubscription.
class RunningInternalState extends NotifierInternalState {
  RunningInternalState({
    required this.cancelToken,
    required this.subscription,
  });

  /// Token for cancelling the run.
  final CancelToken cancelToken;

  /// Subscription to the event stream.
  final StreamSubscription<BaseEvent> subscription;

  /// Disposes of all resources.
  Future<void> dispose() async {
    cancelToken.cancel();
    await subscription.cancel();
  }
}

/// Manages the lifecycle of an active AG-UI run.
///
/// This notifier:
/// - Uses [AgUiClient] for SSE streaming
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
class ActiveRunNotifier extends Notifier<ActiveRunState> {
  late final AgUiClient _agUiClient;
  NotifierInternalState _internalState = const IdleInternalState();

  @override
  ActiveRunState build() {
    _agUiClient = ref.watch(agUiClientProvider);

    ref.onDispose(() {
      if (_internalState is RunningInternalState) {
        (_internalState as RunningInternalState).dispose();
      }
    });

    return const IdleState();
  }

  /// Starts a new run with the given message.
  ///
  /// Two-step process:
  /// 1. Creates run via API to get backend-generated run_id (or uses provided)
  /// 2. Streams AG-UI events using that run_id
  ///
  /// If [existingRunId] is provided, uses that run instead of creating new.
  /// Useful when a thread was just created with an initial run.
  ///
  /// Throws [StateError] if a run is already active. Call [cancelRun] first.
  Future<void> startRun({
    required String roomId,
    required String threadId,
    required String userMessage,
    String? existingRunId,
    Map<String, dynamic>? initialState,
  }) async {
    if (state.isRunning) {
      throw StateError(
        'Cannot start run: a run is already active. '
        'Call cancelRun() first.',
      );
    }

    // Dispose any previous resources
    if (_internalState is RunningInternalState) {
      await (_internalState as RunningInternalState).dispose();
    }

    // Create new resources
    final cancelToken = CancelToken();

    // Step 1: Get run_id (use existing or create new)
    final String runId;
    if (existingRunId != null) {
      runId = existingRunId;
    } else {
      final api = ref.read(apiProvider);
      final runInfo = await api.createRun(roomId, threadId);
      runId = runInfo.id;
    }

    // Create user message
    final userMessageObj = TextMessage.create(
      id: 'user_${DateTime.now().millisecondsSinceEpoch}',
      user: ChatUser.user,
      text: userMessage,
    );

    // Set running state with user message
    state = RunningState(
      threadId: threadId,
      runId: runId,
      context: state.context.copyWith(
        messages: [...state.context.messages, userMessageObj],
      ),
    );

    try {
      // Step 2: Build the streaming endpoint URL with backend run_id
      final endpoint = 'rooms/$roomId/agui/$threadId/$runId';

      // Create the input for the run
      final input = SimpleRunAgentInput(
        threadId: threadId,
        runId: runId,
        messages: [
          UserMessage(
            id: userMessageObj.id,
            content: userMessage,
          ),
        ],
        state: initialState,
      );

      // Start streaming
      final eventStream = _agUiClient.runAgent(
        endpoint,
        input,
        cancelToken: cancelToken,
      );

      // Process events
      // ignore: cancel_subscriptions - stored in _internalState and cancelled
      final subscription = eventStream.listen(
        _processEvent,
        onError: (Object error, StackTrace stackTrace) {
          final currentState = state;
          if (currentState is RunningState) {
            state = CompletedState(
              threadId: currentState.threadId,
              runId: currentState.runId,
              context: currentState.context,
              result: Failed(errorMessage: error.toString()),
            );
          }
        },
        onDone: () {
          // If stream ends without RUN_FINISHED or RUN_ERROR,
          // mark as finished
          final currentState = state;
          if (currentState is RunningState) {
            state = CompletedState(
              threadId: currentState.threadId,
              runId: currentState.runId,
              context: currentState.context,
              result: const Success(),
            );
          }
        },
        cancelOnError: false,
      );

      // Store running state
      _internalState = RunningInternalState(
        cancelToken: cancelToken,
        subscription: subscription,
      );
    } on CancellationError {
      // User cancelled - already handled in cancelRun
      state = CompletedState(
        threadId: threadId,
        runId: runId,
        context: state.context,
        result: const Cancelled(reason: 'Cancelled by user'),
      );
      _internalState = const IdleInternalState();
    } catch (e) {
      state = CompletedState(
        threadId: threadId,
        runId: runId,
        context: state.context,
        result: Failed(errorMessage: e.toString()),
      );
      _internalState = const IdleInternalState();
    }
  }

  /// Cancels the active run.
  ///
  /// Preserves all completed messages but clears streaming state.
  Future<void> cancelRun() async {
    final currentState = state;

    if (_internalState is RunningInternalState) {
      await (_internalState as RunningInternalState).dispose();
      _internalState = const IdleInternalState();
    }

    if (currentState is RunningState) {
      state = CompletedState(
        threadId: currentState.threadId,
        runId: currentState.runId,
        context: currentState.context,
        result: const Cancelled(reason: 'Cancelled by user'),
      );
    }
  }

  /// Resets to idle state, clearing all messages and state.
  void reset() {
    if (_internalState is RunningInternalState) {
      (_internalState as RunningInternalState).dispose();
      _internalState = const IdleInternalState();
    }

    state = const IdleState();
  }

  /// Processes a single AG-UI event and updates state accordingly.
  void _processEvent(BaseEvent event) {
    final currentState = state;
    if (currentState is! RunningState) return;

    // Store raw event
    final updatedContext = currentState.context.copyWith(
      rawEvents: [...currentState.rawEvents, event],
    );

    switch (event) {
      case RunStartedEvent():
        // Run started - just update raw events
        state = currentState.copyWith(context: updatedContext);

      case RunFinishedEvent():
        // Run finished successfully
        state = CompletedState(
          threadId: currentState.threadId,
          runId: currentState.runId,
          context: updatedContext,
          result: const Success(),
        );

      case RunErrorEvent(:final message):
        // Run encountered an error
        state = CompletedState(
          threadId: currentState.threadId,
          runId: currentState.runId,
          context: updatedContext,
          result: Failed(errorMessage: message),
        );

      case TextMessageStartEvent(:final messageId):
        // Start streaming a new text message
        state = currentState.copyWith(
          context: updatedContext,
          textStreaming: Streaming(messageId: messageId, text: ''),
        );

      case TextMessageContentEvent(:final messageId, :final delta):
        // Append streaming text content
        final streaming = currentState.textStreaming;
        if (streaming is Streaming && streaming.messageId == messageId) {
          state = currentState.copyWith(
            context: updatedContext,
            textStreaming: Streaming(
              messageId: messageId,
              text: streaming.text + delta,
            ),
          );
        }

      case TextMessageEndEvent(:final messageId):
        // Complete the streaming message
        final streaming = currentState.textStreaming;
        if (streaming is Streaming && streaming.messageId == messageId) {
          final newMessage = TextMessage.create(
            id: messageId,
            user: ChatUser.assistant,
            text: streaming.text,
          );
          state = currentState.copyWith(
            context: updatedContext.copyWith(
              messages: [...currentState.messages, newMessage],
            ),
            textStreaming: const NotStreaming(),
          );
        }

      case ToolCallStartEvent(:final toolCallId, :final toolCallName):
        final toolCall = ToolCallInfo(id: toolCallId, name: toolCallName);
        state = currentState.copyWith(
          context: updatedContext.copyWith(
            activeToolCalls: [...currentState.activeToolCalls, toolCall],
          ),
        );

      case ToolCallEndEvent(:final toolCallId):
        // Tool call finished
        final updatedToolCalls = currentState.activeToolCalls
            .where((tc) => tc.id != toolCallId)
            .toList();
        state = currentState.copyWith(
          context: updatedContext.copyWith(activeToolCalls: updatedToolCalls),
        );

      case StateSnapshotEvent(:final snapshot):
        // State snapshot received
        state = currentState.copyWith(
          context: updatedContext.copyWith(
            state: Map<String, dynamic>.from(snapshot as Map),
          ),
        );

      case StateDeltaEvent():
      case StepStartedEvent():
      case StepFinishedEvent():
      case ToolCallArgsEvent():
      case ToolCallResultEvent():
      case ActivitySnapshotEvent():
      case MessagesSnapshotEvent():
      case CustomEvent():
      case RawEvent():
      case TextMessageChunkEvent():
      case ToolCallChunkEvent():
      case ThinkingStartEvent():
      case ThinkingContentEvent():
      case ThinkingEndEvent():
      case ThinkingTextMessageStartEvent():
      case ThinkingTextMessageContentEvent():
      case ThinkingTextMessageEndEvent():
        // Store event but don't process (AM3 doesn't need these)
        state = currentState.copyWith(context: updatedContext);
    }
  }
}
