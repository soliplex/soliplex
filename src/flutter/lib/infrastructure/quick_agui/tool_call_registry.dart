import 'dart:async';

import 'package:ag_ui/ag_ui.dart';

import 'package:soliplex/infrastructure/quick_agui/tool_call_state.dart';

/// Registry for tracking tool calls with lifecycle state management.
///
/// Provides:
/// - Idempotent registration (duplicate registrations are ignored)
/// - State machine transitions (received -> executing -> completed/failed)
/// - Atomic execution guard via [tryStartExecution]
/// - Stream of state changes for UI notifications
///
/// Double execution is prevented by design:
/// - [tryStartExecution] atomically checks state and transitions
/// - Only calls in 'received' state can be executed
/// - Dart's single-threaded event loop ensures atomicity
class ToolCallRegistry {
  final Map<String, TrackedToolCall> _calls = {};
  final StreamController<ToolCallStateChange> _stateChangeController =
      StreamController<ToolCallStateChange>.broadcast();

  /// Stream of state changes for UI notifications.
  Stream<ToolCallStateChange> get stateChanges => _stateChangeController.stream;

  /// Register a tool call in the received state.
  ///
  /// Returns true if this was a new registration, false if already registered.
  /// This is idempotent - calling with the same ID multiple times is safe.
  bool register(ToolCall call) {
    if (_calls.containsKey(call.id)) {
      return false;
    }

    final tracked = TrackedToolCall.received(call);
    _calls[call.id] = tracked;

    _emitStateChange(
      tracked,
      ToolCallState.received, // "previous" state for initial registration
      ToolCallState.received,
    );

    return true;
  }

  /// Atomically try to start execution of a tool call.
  ///
  /// Returns the ToolCall if successful (state was 'received'), null otherwise.
  /// This is the key method for preventing double execution:
  /// - Only one caller can get a non-null result for a given ID
  /// - The state is atomically transitioned to 'executing'
  ToolCall? tryStartExecution(String callId) {
    final tracked = _calls[callId];
    if (tracked == null || tracked.state != ToolCallState.received) {
      return null;
    }

    final executing = tracked.toExecuting();
    _calls[callId] = executing;

    _emitStateChange(
      executing,
      ToolCallState.received,
      ToolCallState.executing,
    );

    return tracked.call;
  }

  /// Mark a tool call as completed with its result.
  void markCompleted(String toolCallId, ToolMessage message) {
    final tracked = _calls[toolCallId];
    if (tracked == null) return;

    // Allow completion from either executing or received state
    // (in case tryStartExecution wasn't used)
    if (tracked.state != ToolCallState.executing &&
        tracked.state != ToolCallState.received) {
      return;
    }

    final previousState = tracked.state;
    final completed = tracked.copyWith(
      state: ToolCallState.completed,
      completedAt: DateTime.now(),
      result: message,
    );
    _calls[toolCallId] = completed;

    _emitStateChange(
      completed,
      previousState,
      ToolCallState.completed,
      result: message,
    );
  }

  /// Mark a tool call as failed with an error message.
  void markFailed(String toolCallId, String error) {
    final tracked = _calls[toolCallId];
    if (tracked == null) return;

    if (tracked.state != ToolCallState.executing &&
        tracked.state != ToolCallState.received) {
      return;
    }

    final previousState = tracked.state;
    final failed = tracked.copyWith(
      state: ToolCallState.failed,
      completedAt: DateTime.now(),
      error: error,
    );
    _calls[toolCallId] = failed;

    _emitStateChange(failed, previousState, ToolCallState.failed, error: error);
  }

  /// Get all completed tool messages.
  Iterable<ToolMessage> get results => _calls.values
      .where((t) => t.state == ToolCallState.completed && t.result != null)
      .map((t) => t.result!);

  /// Get tool calls ready for execution (state == received).
  Iterable<ToolCall> get pendingCalls => _calls.values
      .where((t) => t.state == ToolCallState.received)
      .map((t) => t.call);

  /// Get tool calls currently executing.
  Iterable<TrackedToolCall> get executingCalls =>
      _calls.values.where((t) => t.state == ToolCallState.executing);

  /// Check if a tool call exists and its current state.
  TrackedToolCall? getTracked(String callId) => _calls[callId];

  /// Check if there are any pending or executing calls.
  bool get hasActiveWork => _calls.values.any(
    (t) =>
        t.state == ToolCallState.received || t.state == ToolCallState.executing,
  );

  /// Clear all tracked calls.
  void clear() {
    _calls.clear();
  }

  /// Dispose of resources.
  void dispose() {
    _stateChangeController.close();
  }

  void _emitStateChange(
    TrackedToolCall tracked,
    ToolCallState previousState,
    ToolCallState newState, {
    ToolMessage? result,
    String? error,
  }) {
    if (_stateChangeController.isClosed) return;

    _stateChangeController.add(
      ToolCallStateChange(
        toolCallId: tracked.id,
        toolName: tracked.toolName,
        previousState: previousState,
        newState: newState,
        timestamp: DateTime.now(),
        result: result,
        error: error,
      ),
    );
  }
}
