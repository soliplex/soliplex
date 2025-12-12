import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Represents an actively executing tool call for UI display.
class ActiveToolExecution {
  final String toolCallId;
  final String toolName;
  final DateTime startedAt;
  final Map<String, dynamic>? args;

  const ActiveToolExecution({
    required this.toolCallId,
    required this.toolName,
    required this.startedAt,
    this.args,
  });

  /// Duration since execution started.
  Duration get elapsed => DateTime.now().difference(startedAt);
}

/// State for tracking active tool executions.
class ToolExecutionState {
  final Map<String, ActiveToolExecution> activeExecutions;

  const ToolExecutionState({
    this.activeExecutions = const {},
  });

  /// Whether there are any active executions.
  bool get hasActiveExecutions => activeExecutions.isNotEmpty;

  /// Number of active executions.
  int get activeCount => activeExecutions.length;

  /// List of tool names currently executing.
  List<String> get activeToolNames =>
      activeExecutions.values.map((e) => e.toolName).toList();

  ToolExecutionState copyWith({
    Map<String, ActiveToolExecution>? activeExecutions,
  }) {
    return ToolExecutionState(
      activeExecutions: activeExecutions ?? this.activeExecutions,
    );
  }
}

/// StateNotifier for managing tool execution state.
///
/// Tracks which tools are currently executing for UI notifications.
class ToolExecutionNotifier extends StateNotifier<ToolExecutionState> {
  ToolExecutionNotifier() : super(const ToolExecutionState());

  /// Mark a tool as starting execution.
  void startExecution(
    String toolCallId,
    String toolName, {
    Map<String, dynamic>? args,
  }) {
    state = state.copyWith(
      activeExecutions: {
        ...state.activeExecutions,
        toolCallId: ActiveToolExecution(
          toolCallId: toolCallId,
          toolName: toolName,
          startedAt: DateTime.now(),
          args: args,
        ),
      },
    );
  }

  /// Mark a tool as finished executing.
  void endExecution(String toolCallId) {
    final updated = Map<String, ActiveToolExecution>.from(state.activeExecutions);
    updated.remove(toolCallId);
    state = state.copyWith(activeExecutions: updated);
  }

  /// Clear all active executions.
  void clearAll() {
    state = const ToolExecutionState();
  }

  /// Get execution info for a specific tool call.
  ActiveToolExecution? getExecution(String toolCallId) {
    return state.activeExecutions[toolCallId];
  }

  /// Check if a specific tool call is executing.
  bool isExecuting(String toolCallId) {
    return state.activeExecutions.containsKey(toolCallId);
  }
}

/// Riverpod provider for tool execution state.
final toolExecutionProvider =
    StateNotifierProvider<ToolExecutionNotifier, ToolExecutionState>((ref) {
  return ToolExecutionNotifier();
});
