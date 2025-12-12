import 'package:ag_ui/ag_ui.dart' as ag_ui;

/// Registry for tracking tool call lifecycle.
class ToolCallRegistry {
  final Map<String, ag_ui.ToolCall> _pendingCalls = {};
  final Map<String, ag_ui.ToolCall> _executingCalls = {};
  final Map<String, ag_ui.ToolMessage> _completedResults = {};
  final Map<String, String> _failedCalls = {};

  /// Register a new tool call.
  void register(ag_ui.ToolCall call) {
    _pendingCalls[call.id] = call;
  }

  /// Try to start execution of a tool call.
  /// Returns the call if it was pending, null if already executing or completed.
  ag_ui.ToolCall? tryStartExecution(String toolCallId) {
    final call = _pendingCalls.remove(toolCallId);
    if (call != null) {
      _executingCalls[toolCallId] = call;
    }
    return call;
  }

  /// Mark a tool call as completed.
  void markCompleted(String toolCallId, ag_ui.ToolMessage message) {
    _executingCalls.remove(toolCallId);
    _pendingCalls.remove(toolCallId);
    _completedResults[toolCallId] = message;
  }

  /// Mark a tool call as failed.
  void markFailed(String toolCallId, String error) {
    _executingCalls.remove(toolCallId);
    _pendingCalls.remove(toolCallId);
    _failedCalls[toolCallId] = error;
  }

  /// Get all pending tool calls.
  Iterable<ag_ui.ToolCall> get pendingCalls => _pendingCalls.values;

  /// Get all executing tool calls.
  Iterable<ag_ui.ToolCall> get executingCalls => _executingCalls.values;

  /// Get all completed results.
  Iterable<ag_ui.ToolMessage> get completedResults => _completedResults.values;

  /// Check if a tool call is pending.
  bool isPending(String toolCallId) => _pendingCalls.containsKey(toolCallId);

  /// Check if a tool call is executing.
  bool isExecuting(String toolCallId) =>
      _executingCalls.containsKey(toolCallId);

  /// Check if a tool call is completed.
  bool isCompleted(String toolCallId) =>
      _completedResults.containsKey(toolCallId);

  /// Check if a tool call has failed.
  bool isFailed(String toolCallId) => _failedCalls.containsKey(toolCallId);

  /// Clear all state.
  void clear() {
    _pendingCalls.clear();
    _executingCalls.clear();
    _completedResults.clear();
    _failedCalls.clear();
  }

  @override
  String toString() =>
      'ToolCallRegistry(pending: ${_pendingCalls.length}, executing: ${_executingCalls.length}, completed: ${_completedResults.length})';
}
