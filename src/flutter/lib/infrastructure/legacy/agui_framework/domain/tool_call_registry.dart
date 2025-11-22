import 'package:ag_ui/ag_ui.dart';

/// Tracks tool calls and their completion status within a run
class ToolCallRegistry {
  final Map<String, ToolCall> _calls = {};
  final Set<String> _completedIds = {};

  /// Register a new tool call
  void register(ToolCall call) {
    _calls[call.id] = call;
  }

  /// Mark a tool call as completed (result received)
  void markCompleted(String toolCallId) {
    _completedIds.add(toolCallId);
  }

  /// Check if a tool call is pending (registered but not completed)
  bool isPending(String toolCallId) {
    return _calls.containsKey(toolCallId) && !_completedIds.contains(toolCallId);
  }

  /// Get all pending tool calls (both client and server)
  Iterable<ToolCall> get allPending {
    final pendingIds = _calls.keys.toSet().difference(_completedIds);
    return pendingIds.map((id) => _calls[id]!);
  }

  /// Get all pending tool calls for client-side tools
  Iterable<ToolCall> getPendingClientCalls(List<Tool> clientTools) {
    final clientToolNames = clientTools.map((t) => t.name).toSet();
    final pendingIds = _calls.keys.toSet().difference(_completedIds);

    return pendingIds
        .map((id) => _calls[id]!)
        .where((tc) => clientToolNames.contains(tc.function.name));
  }

  /// Get all tool calls (for debugging/inspection)
  Iterable<ToolCall> get allCalls => _calls.values;

  /// Get all completed tool call IDs
  Set<String> get completedIds => Set.unmodifiable(_completedIds);
}
