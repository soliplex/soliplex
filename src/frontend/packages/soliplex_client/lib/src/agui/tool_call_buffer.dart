import 'package:meta/meta.dart';
import 'package:soliplex_client/src/models/chat_message.dart';

/// Internal state for a tool call being buffered.
class _ToolCallState {
  _ToolCallState({
    required this.id,
    required this.name,
    this.parentMessageId,
  }) : startedAt = DateTime.now();

  final String id;
  final String name;
  final String? parentMessageId;
  final DateTime startedAt;
  final StringBuffer arguments = StringBuffer();
  String? result;
  DateTime? completedAt;
  bool isComplete = false;
}

/// Buffer that tracks multiple concurrent tool calls.
///
/// Usage:
/// 1. Call [startToolCall] when TOOL_CALL_START event is received
/// 2. Call [appendArgs] for each TOOL_CALL_ARGS event
/// 3. Call [completeToolCall] when TOOL_CALL_END event is received
/// 4. Call [setResult] when TOOL_CALL_RESULT event is received
///
/// Example:
/// ```dart
/// final buffer = ToolCallBuffer();
///
/// // When TOOL_CALL_START arrives
/// buffer.startToolCall(callId: 'tc-1', name: 'search');
///
/// // When TOOL_CALL_ARGS arrives
/// buffer.appendArgs(callId: 'tc-1', delta: '{"query":');
/// buffer.appendArgs(callId: 'tc-1', delta: '"test"}');
///
/// // When TOOL_CALL_END arrives
/// final toolCallInfo = buffer.completeToolCall(callId: 'tc-1');
///
/// // When TOOL_CALL_RESULT arrives
/// buffer.setResult(callId: 'tc-1', result: 'Search results...');
/// ```
class ToolCallBuffer {
  final Map<String, _ToolCallState> _activeToolCalls = {};

  /// Returns the number of active (started but not removed) tool calls.
  int get activeCount => _activeToolCalls.length;

  /// Returns whether there are any active tool calls.
  bool get hasActiveToolCalls => _activeToolCalls.isNotEmpty;

  /// Returns the IDs of all active tool calls.
  List<String> get activeToolCallIds => _activeToolCalls.keys.toList();

  /// Starts tracking a new tool call.
  ///
  /// Throws [StateError] if a tool call with the same ID is already active.
  void startToolCall({
    required String callId,
    required String name,
    String? parentMessageId,
  }) {
    if (_activeToolCalls.containsKey(callId)) {
      throw StateError(
        'Tool call with ID "$callId" is already active. '
        'Each tool call ID must be unique.',
      );
    }

    _activeToolCalls[callId] = _ToolCallState(
      id: callId,
      name: name,
      parentMessageId: parentMessageId,
    );
  }

  /// Appends arguments to an active tool call.
  ///
  /// Throws [StateError] if the tool call is not active.
  void appendArgs({
    required String callId,
    required String delta,
  }) {
    final state = _activeToolCalls[callId];
    if (state == null) {
      throw StateError(
        'Cannot append arguments to tool call "$callId": not found. '
        'Call startToolCall() first.',
      );
    }

    if (state.isComplete) {
      throw StateError(
        'Cannot append arguments to tool call "$callId": already complete. '
        'Arguments were finalized by completeToolCall().',
      );
    }

    state.arguments.write(delta);
  }

  /// Completes the arguments for a tool call and returns a [ToolCallInfo].
  ///
  /// The tool call remains in the buffer until [removeToolCall] is called.
  ///
  /// Throws [StateError] if the tool call is not active.
  ToolCallInfo completeToolCall({required String callId}) {
    final state = _activeToolCalls[callId];
    if (state == null) {
      throw StateError(
        'Cannot complete tool call "$callId": not found. '
        'Call startToolCall() first.',
      );
    }

    state
      ..isComplete = true
      ..completedAt = DateTime.now();

    return ToolCallInfo(
      id: state.id,
      name: state.name,
      arguments: state.arguments.toString(),
      startedAt: state.startedAt,
      completedAt: state.completedAt,
    );
  }

  /// Sets the result for a completed tool call and returns updated info.
  ///
  /// Throws [StateError] if the tool call is not active.
  ToolCallInfo setResult({
    required String callId,
    required String result,
  }) {
    final state = _activeToolCalls[callId];
    if (state == null) {
      throw StateError(
        'Cannot set result for tool call "$callId": not found. '
        'The tool call may have been removed.',
      );
    }

    state.result = result;

    return ToolCallInfo(
      id: state.id,
      name: state.name,
      arguments: state.arguments.toString(),
      status: ToolCallStatus.completed,
      result: result,
      startedAt: state.startedAt,
      completedAt: state.completedAt ?? DateTime.now(),
    );
  }

  /// Gets the current state of a tool call.
  ///
  /// Returns null if the tool call is not active.
  ToolCallInfo? getToolCall(String callId) {
    final state = _activeToolCalls[callId];
    if (state == null) return null;

    return ToolCallInfo(
      id: state.id,
      name: state.name,
      arguments: state.arguments.toString(),
      status: state.result != null
          ? ToolCallStatus.completed
          : ToolCallStatus.pending,
      result: state.result,
      startedAt: state.startedAt,
      completedAt: state.completedAt,
    );
  }

  /// Gets all currently active tool calls.
  List<ToolCallInfo> get allToolCalls {
    return _activeToolCalls.values.map((state) {
      return ToolCallInfo(
        id: state.id,
        name: state.name,
        arguments: state.arguments.toString(),
        status: state.result != null
            ? ToolCallStatus.completed
            : ToolCallStatus.pending,
        result: state.result,
        startedAt: state.startedAt,
        completedAt: state.completedAt,
      );
    }).toList();
  }

  /// Removes a tool call from the buffer.
  ///
  /// Returns the final [ToolCallInfo] if found, null otherwise.
  ToolCallInfo? removeToolCall(String callId) {
    final state = _activeToolCalls.remove(callId);
    if (state == null) return null;

    return ToolCallInfo(
      id: state.id,
      name: state.name,
      arguments: state.arguments.toString(),
      status: state.result != null
          ? ToolCallStatus.completed
          : ToolCallStatus.pending,
      result: state.result,
      startedAt: state.startedAt,
      completedAt: state.completedAt,
    );
  }

  /// Checks if a tool call is active.
  bool isActive(String callId) => _activeToolCalls.containsKey(callId);

  /// Checks if a tool call has been completed (TOOL_CALL_END received).
  bool isComplete(String callId) =>
      _activeToolCalls[callId]?.isComplete ?? false;

  /// Checks if a tool call has a result.
  bool hasResult(String callId) => _activeToolCalls[callId]?.result != null;

  /// Clears all tool calls from the buffer.
  void reset() {
    _activeToolCalls.clear();
  }
}

/// Immutable snapshot of a tool call buffer state.
///
/// Useful for exposing buffer state without allowing modifications.
@immutable
class ToolCallBufferSnapshot {
  /// Creates a new [ToolCallBufferSnapshot] with the given state.
  const ToolCallBufferSnapshot({
    required this.activeCount,
    required this.toolCalls,
  });

  /// Creates a snapshot from a [ToolCallBuffer].
  factory ToolCallBufferSnapshot.fromBuffer(ToolCallBuffer buffer) {
    return ToolCallBufferSnapshot(
      activeCount: buffer.activeCount,
      toolCalls: buffer.allToolCalls,
    );
  }

  /// The number of active tool calls.
  final int activeCount;

  /// List of all tool calls in the buffer.
  final List<ToolCallInfo> toolCalls;

  /// Whether there are any active tool calls.
  bool get hasActiveToolCalls => activeCount > 0;
}
