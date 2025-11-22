import 'dart:async';
import 'package:ag_ui/ag_ui.dart' hide Run;
import 'package:flutter/foundation.dart';
import 'run.dart' as agui_run;

/// A lean coordinator that aggregates data from Run objects.
///
/// A Thread represents a conversation with an AG-UI agent, composed of
/// one or more Runs. It provides a facade API for sending messages and
/// accessing aggregated data, but doesn't duplicate state - all data
/// lives in the Run objects.
class AguiThread {
  final String id;
  final AgUiClient _client;
  final String agentName;
  final List<Tool> clientTools;
  final Map<String, Future<String> Function(ToolCall)> toolExecutors;

  // Thread only maintains the list of runs
  final List<agui_run.Run> _runs = [];

  AguiThread({
    required this.id,
    required AgUiClient client,
    required this.agentName,
    this.clientTools = const [],
    this.toolExecutors = const {},
  }) : _client = client;

  // Public accessors - all computed from runs!
  List<agui_run.Run> get runs => List.unmodifiable(_runs);
  agui_run.Run? get currentRun => _runs.isEmpty ? null : _runs.last;

  ThreadStatus get status {
    if (_runs.isEmpty) return ThreadStatus.idle;

    return switch (currentRun!.status) {
      agui_run.RunStatus.running => ThreadStatus.running,
      agui_run.RunStatus.pending => ThreadStatus.pending,
      _ => ThreadStatus.ready,
    };
  }

  /// All messages across all runs (computed, not stored)
  /// Returns an Iterable to avoid allocating a new list on each call
  Iterable<Message> get messages {
    return _runs.expand((run) => run.messages);
  }

  /// Current state from the most recent run
  Map<String, dynamic>? get currentState => currentRun?.currentState;

  /// All thinking logs across all runs
  /// Returns an Iterable to avoid allocating a new list on each call
  Iterable<agui_run.ThinkingChunk> get allThinking {
    return _runs.expand((run) => run.thinkingLog);
  }

  /// Stream of all messages: historical + new from current run
  Stream<Message> get messageStream async* {
    // Yield historical messages from completed runs
    for (final run in _runs) {
      if (run.status != agui_run.RunStatus.running) {
        yield* Stream.fromIterable(run.messages);
      } else {
        // Current run - stream it live
        yield* run.messageStream;
      }
    }
  }

  /// Stream of state updates from current run
  Stream<Map<String, dynamic>> get stateStream async* {
    // If there's a current run, stream its state updates
    if (currentRun?.status == agui_run.RunStatus.running) {
      yield* currentRun!.stateStream;
    }
  }

  /// Send a user message and start a new run
  Future<void> sendMessage(String content) async {
    final userMsg = UserMessage(
      id: _generateId(UserMessage),
      content: content,
    );

    await _startNewRun([userMsg]);
  }

  /// Send tool results and start a new run
  Future<void> sendToolResults(List<ToolMessage> toolMessages) async {
    await _startNewRun(toolMessages);
  }

  /// Internal: Start a new run with the full message history
  /// Handles chaining if the run returns more tool results
  Future<void> _startNewRun(List<Message> newMessages) async {
    // Build full message history
    final allMessages = [...messages, ...newMessages];

    // Get state from previous run (if any)
    final previousState = currentRun?.currentState;

    // Create new run with full context and state
    final run = agui_run.Run(
      id: _runs.length.toString(),
      threadId: id,
      client: _client,
      agentName: agentName,
      inputMessages: allMessages,
      tools: clientTools,
      toolExecutors: toolExecutors,
      initialState: previousState,
    );

    _runs.add(run);

    // Start the run and get tool results (if any)
    final toolResults = await run.start();

    // If tool results were returned, chain another run
    if (toolResults.isNotEmpty) {
      debugPrint('Chaining run with ${toolResults.length} tool result(s)');
      await sendToolResults(toolResults);
    }
  }

  /// Cancel the current run if one is active
  Future<void> cancelCurrentRun() async {
    if (currentRun?.status == agui_run.RunStatus.running) {
      await currentRun!.cancel();
    }
  }

  String _generateId(Type type) {
    return '${type}_${DateTime.now().millisecondsSinceEpoch}';
  }

  // Persistence - serialize all runs
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'agentName': agentName,
      'clientTools': clientTools.map((t) => t.toJson()).toList(),
      'runs': _runs.map((r) => r.toJson()).toList(),
    };
  }

  void dispose() {
    // Cancel any active runs
    if (currentRun?.status == agui_run.RunStatus.running) {
      currentRun!.cancel();
    }
  }
}

enum ThreadStatus {
  idle, // No runs yet
  pending, // Run created but not started
  running, // Active run in progress
  ready, // Last run completed, ready for next message
}
