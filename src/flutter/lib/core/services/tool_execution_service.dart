import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/providers/server_scoped_notifier.dart';

/// Default timeout for tool executions (60 seconds).
///
/// If a tool doesn't complete within this time, it's automatically cleared
/// to prevent stale indicators from network drops or server crashes.
const _defaultToolTimeout = Duration(seconds: 60);

/// Represents an actively executing tool call for UI display.
class ActiveToolExecution {
  const ActiveToolExecution({
    required this.toolCallId,
    required this.toolName,
    required this.startedAt,
    this.args,
  });
  final String toolCallId;
  final String toolName;
  final DateTime startedAt;
  final Map<String, dynamic>? args;

  /// Duration since execution started.
  Duration get elapsed => DateTime.now().difference(startedAt);
}

/// State for tracking active tool executions.
class ToolExecutionState {
  const ToolExecutionState({this.activeExecutions = const {}});
  final Map<String, ActiveToolExecution> activeExecutions;

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

/// ServerScopedNotifier for managing tool execution state.
///
/// Tracks which tools are currently executing for UI notifications.
/// State is scoped per server+room to prevent cross-contamination.
class ToolExecutionNotifier extends ServerScopedNotifier<ToolExecutionState> {
  ToolExecutionNotifier({String? serverId, this.roomId})
    : super(const ToolExecutionState(), serverId: serverId);

  /// The room ID this notifier tracks (for per-room isolation).
  final String? roomId;

  /// Timeout timers for auto-clearing stale executions.
  final Map<String, Timer> _timeoutTimers = {};

  /// Mark a tool as starting execution.
  ///
  /// Schedules a timeout timer to auto-clear if completion never arrives.
  void startExecution(
    String toolCallId,
    String toolName, {
    Map<String, dynamic>? args,
  }) {
    // Cancel any existing timer for this tool call
    _cancelTimer(toolCallId);

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

    // Schedule timeout to auto-clear stale execution
    _scheduleTimeout(toolCallId);
  }

  /// Mark a tool as finished executing (success or error).
  void endExecution(String toolCallId) {
    _cancelTimer(toolCallId);

    final updated = Map<String, ActiveToolExecution>.from(
      state.activeExecutions,
    );
    updated.remove(toolCallId);
    state = state.copyWith(activeExecutions: updated);
  }

  /// Clear all active executions.
  void clearAll() {
    _cancelAllTimers();
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

  /// Schedule a timeout timer for a tool call.
  ///
  /// Auto-clears the execution if it hasn't completed within
  /// _defaultToolTimeout.
  void _scheduleTimeout(String toolCallId) {
    _timeoutTimers[toolCallId] = Timer(_defaultToolTimeout, () {
      if (state.activeExecutions.containsKey(toolCallId)) {
        endExecution(toolCallId);
      }
    });
  }

  /// Cancel the timeout timer for a specific tool call.
  void _cancelTimer(String toolCallId) {
    _timeoutTimers[toolCallId]?.cancel();
    _timeoutTimers.remove(toolCallId);
  }

  /// Cancel all pending timeout timers.
  void _cancelAllTimers() {
    for (final timer in _timeoutTimers.values) {
      timer.cancel();
    }
    _timeoutTimers.clear();
  }

  @override
  void dispose() {
    _cancelAllTimers();
    super.dispose();
  }
}

/// Legacy global provider for tool execution state.
///
/// DEPRECATED: Prefer roomToolExecutionProvider for per-room state.
/// This provider exists for backwards compatibility during migration.
final toolExecutionProvider =
    StateNotifierProvider<ToolExecutionNotifier, ToolExecutionState>((ref) {
      return ToolExecutionNotifier();
    });
