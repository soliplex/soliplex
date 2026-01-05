import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client/soliplex_client.dart' as domain
    show Cancelled, Completed, Conversation, Failed, Idle, Running;
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
    if (existingRunId != null && existingRunId.isNotEmpty) {
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

    // Create conversation with user message and Running status
    final conversation = domain.Conversation(
      threadId: threadId,
      messages: [userMessageObj],
      status: domain.Running(runId: runId),
    );

    // Set running state
    state = RunningState(
      conversation: conversation,
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
              conversation: currentState.conversation.withStatus(
                domain.Failed(error: error.toString()),
              ),
              result: FailedResult(errorMessage: error.toString()),
            );
          }
        },
        onDone: () {
          // If stream ends without RUN_FINISHED or RUN_ERROR,
          // mark as finished
          final currentState = state;
          if (currentState is RunningState) {
            state = CompletedState(
              conversation: currentState.conversation.withStatus(
                const domain.Completed(),
              ),
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
        conversation: conversation.withStatus(
          const domain.Cancelled(reason: 'Cancelled by user'),
        ),
        result: const CancelledResult(reason: 'Cancelled by user'),
      );
      _internalState = const IdleInternalState();
    } catch (e) {
      state = CompletedState(
        conversation: conversation.withStatus(
          domain.Failed(error: e.toString()),
        ),
        result: FailedResult(errorMessage: e.toString()),
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
        conversation: currentState.conversation.withStatus(
          const domain.Cancelled(reason: 'User cancelled'),
        ),
        result: const CancelledResult(reason: 'Cancelled by user'),
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

    // Use application layer processor
    final result = processEvent(
      currentState.conversation,
      currentState.streaming,
      event,
    );

    // Map result to frontend state
    state = _mapResultToState(currentState, result);
  }

  /// Maps an EventProcessingResult to the appropriate ActiveRunState.
  ActiveRunState _mapResultToState(
    RunningState previousState,
    EventProcessingResult result,
  ) {
    return switch (result.conversation.status) {
      domain.Completed() => CompletedState(
          conversation: result.conversation,
          streaming: result.streaming,
          result: const Success(),
        ),
      domain.Failed(:final error) => CompletedState(
          conversation: result.conversation,
          streaming: result.streaming,
          result: FailedResult(errorMessage: error),
        ),
      domain.Cancelled(:final reason) => CompletedState(
          conversation: result.conversation,
          streaming: result.streaming,
          result: CancelledResult(reason: reason),
        ),
      domain.Running() => previousState.copyWith(
          conversation: result.conversation,
          streaming: result.streaming,
        ),
      domain.Idle() => throw StateError(
          'Unexpected Idle status during event processing',
        ),
    };
  }
}
