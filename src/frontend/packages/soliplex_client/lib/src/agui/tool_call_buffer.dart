import 'package:meta/meta.dart';
import 'package:soliplex_client/src/models/chat_message.dart';

/// Internal state for a tool call being buffered.
class _ToolCallState {
  _ToolCallState({required this.id, required this.name});

  final String id;
  final String name;
  final StringBuffer arguments = StringBuffer();
  String result = '';
  bool isComplete = false;
}

/// Buffer that tracks multiple concurrent tool calls.
class ToolCallBuffer {
  final Map<String, _ToolCallState> _activeToolCalls = {};

  /// Number of active tool calls.
  int get activeCount => _activeToolCalls.length;

  /// Whether there are any active tool calls.
  bool get hasActiveToolCalls => _activeToolCalls.isNotEmpty;

  /// List of active tool call IDs.
  List<String> get activeToolCallIds => _activeToolCalls.keys.toList();

  /// Starts a new tool call with the given ID and name.
  void startToolCall({required String callId, required String name}) {
    if (_activeToolCalls.containsKey(callId)) {
      throw StateError('Tool call "$callId" already active.');
    }
    _activeToolCalls[callId] = _ToolCallState(id: callId, name: name);
  }

  /// Appends arguments to an active tool call.
  void appendArgs({required String callId, required String delta}) {
    final state = _activeToolCalls[callId];
    if (state == null) throw StateError('Tool call "$callId" not found.');
    if (state.isComplete) throw StateError('Tool call "$callId" complete.');
    state.arguments.write(delta);
  }

  /// Marks a tool call as complete and returns its info.
  ToolCallInfo completeToolCall({required String callId}) {
    final state = _activeToolCalls[callId];
    if (state == null) throw StateError('Tool call "$callId" not found.');
    state.isComplete = true;
    return ToolCallInfo(
      id: state.id,
      name: state.name,
      arguments: state.arguments.toString(),
      status: ToolCallStatus.executing,
    );
  }

  /// Sets the result for a tool call.
  ToolCallInfo setResult({required String callId, required String result}) {
    final state = _activeToolCalls[callId];
    if (state == null) throw StateError('Tool call "$callId" not found.');
    state.result = result;
    return ToolCallInfo(
      id: state.id,
      name: state.name,
      arguments: state.arguments.toString(),
      status: ToolCallStatus.completed,
      result: result,
    );
  }

  /// Gets info for a specific tool call, or null if not found.
  ToolCallInfo? getToolCall(String callId) {
    final state = _activeToolCalls[callId];
    if (state == null) return null;
    return _toToolCallInfo(state);
  }

  /// All active tool calls as [ToolCallInfo] list.
  List<ToolCallInfo> get allToolCalls =>
      _activeToolCalls.values.map(_toToolCallInfo).toList();

  /// Removes a tool call and returns its info, or null if not found.
  ToolCallInfo? removeToolCall(String callId) {
    final state = _activeToolCalls.remove(callId);
    if (state == null) return null;
    return _toToolCallInfo(state);
  }

  ToolCallInfo _toToolCallInfo(_ToolCallState state) => ToolCallInfo(
        id: state.id,
        name: state.name,
        arguments: state.arguments.toString(),
        status: state.result.isNotEmpty
            ? ToolCallStatus.completed
            : ToolCallStatus.pending,
        result: state.result,
      );

  /// Whether a tool call with the given ID is active.
  bool isActive(String callId) => _activeToolCalls.containsKey(callId);

  /// Whether a tool call is complete.
  bool isComplete(String callId) =>
      _activeToolCalls[callId]?.isComplete ?? false;

  /// Whether a tool call has a result.
  bool hasResult(String callId) =>
      _activeToolCalls[callId]?.result.isNotEmpty ?? false;

  /// Clears all active tool calls.
  void reset() => _activeToolCalls.clear();
}

/// Immutable snapshot of a tool call buffer state.
@immutable
class ToolCallBufferSnapshot {
  /// Creates a snapshot with the given state.
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

  /// Number of active tool calls.
  final int activeCount;

  /// List of tool call info objects.
  final List<ToolCallInfo> toolCalls;

  /// Whether there are any active tool calls.
  bool get hasActiveToolCalls => activeCount > 0;
}
