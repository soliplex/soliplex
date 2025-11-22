import 'dart:async';
import 'package:ag_ui/ag_ui.dart';
import 'package:flutter/foundation.dart';
import '../parsing/event_parser.dart';
import '../parsing/parse_result.dart';
import 'tool_call_registry.dart';

/// A single request-response cycle with an AG-UI agent.
///
/// A Run owns its execution state and produces messages by processing
/// a stream of events from the agent. It's a self-contained unit that
/// manages its own lifecycle (start, complete, fail, cancel).
class Run {
  final String id;
  final String threadId;
  final DateTime startedAt;
  DateTime? finishedAt;
  RunStatus status;

  final AgUiClient _client;
  final String _agentName;
  final List<Message> _inputMessages; // Context sent to agent
  final List<Tool> _tools;
  final Map<String, Future<String> Function(ToolCall)> _toolExecutors;

  // Run owns its produced data
  final List<BaseEvent> _events = [];
  final List<Message> _producedMessages = []; // NEW messages from this run
  final List<ThinkingChunk> _thinkingLog = [];

  // Tool call tracking
  final ToolCallRegistry _toolCallRegistry = ToolCallRegistry();

  // State management - only current state (YAGNI)
  Map<String, dynamic>? _currentState;

  // Thinking accumulation buffer
  final StringBuffer _thinkingBuffer = StringBuffer();

  // Streams for real-time updates
  final StreamController<Message> _messageController =
      StreamController<Message>();
  final StreamController<Map<String, dynamic>> _stateController =
      StreamController<Map<String, dynamic>>();

  final EventParser _parser = EventParser();
  StreamSubscription<BaseEvent>? _subscription;

  // Completer for start() return value
  final Completer<List<ToolMessage>> _completionCompleter = Completer();

  Run({
    required this.id,
    required this.threadId,
    required AgUiClient client,
    required String agentName,
    required List<Message> inputMessages,
    required List<Tool> tools,
    required Map<String, Future<String> Function(ToolCall)> toolExecutors,
    Map<String, dynamic>? initialState,
    DateTime? startedAt,
  })  : _client = client,
        _agentName = agentName,
        _inputMessages = List.unmodifiable(inputMessages),
        _tools = tools,
        _toolExecutors = toolExecutors,
        _currentState = initialState,
        startedAt = startedAt ?? DateTime.now(),
        status = RunStatus.pending;

  // Public accessors - Run owns all its data
  List<BaseEvent> get events => List.unmodifiable(_events);
  List<Message> get messages => List.unmodifiable(_producedMessages);
  List<Message> get inputMessages => _inputMessages;
  Map<String, dynamic>? get currentState => _currentState;
  List<ThinkingChunk> get thinkingLog => List.unmodifiable(_thinkingLog);

  Stream<Message> get messageStream => _messageController.stream;
  Stream<Map<String, dynamic>> get stateStream => _stateController.stream;

  /// Start the run and begin processing events
  /// Returns list of ToolMessages if client tools were executed, empty list otherwise
  Future<List<ToolMessage>> start() async {
    if (status != RunStatus.pending) {
      throw StateError('Run $id has already been started');
    }

    status = RunStatus.running;
    debugPrint('Starting run $id for thread $threadId');

    final input = SimpleRunAgentInput(
      threadId: threadId,
      runId: id,
      messages: _inputMessages,
      tools: _tools,
      state: _currentState, // Send current state to agent
    );

    try {
      final eventStream = _client.runAgent(_agentName, input);

      _subscription = eventStream.listen(
        _handleEvent,
        onDone: _handleComplete,
        onError: _handleError,
      );
    } catch (e) {
      _handleError(e);
    }

    return _completionCompleter.future;
  }

  void _handleEvent(BaseEvent event) {
    _events.add(event);

    // Log raw event for full visibility
    debugPrint('[EVENT] ${event.eventType.name}');

    // Handle thinking events specially to accumulate complete blocks
    if (event is ThinkingStartEvent || event is ThinkingTextMessageStartEvent) {
      _thinkingBuffer.clear();
      debugPrint('====== THINKING START ======');
    } else if (event is ThinkingContentEvent) {
      _thinkingBuffer.write(event.delta);
    } else if (event is ThinkingTextMessageContentEvent) {
      _thinkingBuffer.write(event.delta);
    } else if (event is ThinkingEndEvent || event is ThinkingTextMessageEndEvent) {
      debugPrint('====== THINKING CONTENT ======');
      debugPrint(_thinkingBuffer.toString());
      debugPrint('====== THINKING END ======');
    }

    // Parse event, passing current state for delta events
    final result = _parser.processEvent(event, currentState: _currentState);

    switch (result) {
      case MessageResult(message: final msg):
        _producedMessages.add(msg);
        debugPrint('[${DateTime.now().millisecondsSinceEpoch}] Emitting message: ${msg.runtimeType}');
        _messageController.add(msg);

        // Register tool calls
        if (msg is AssistantMessage && msg.toolCalls != null) {
          for (final toolCall in msg.toolCalls!) {
            _toolCallRegistry.register(toolCall);
            final isClientTool = _tools.any((t) => t.name == toolCall.function.name);
            debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
            debugPrint('TOOL CALL: ${toolCall.function.name}');
            debugPrint('  ID: ${toolCall.id}');
            debugPrint('  Type: ${isClientTool ? "CLIENT" : "INTERACTIVE (needs user input)"}');
            debugPrint('  Args: ${toolCall.function.arguments}');
            debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
          }
        }

        // Mark tool calls as completed (server-side)
        if (msg is ToolMessage) {
          _toolCallRegistry.markCompleted(msg.toolCallId);
          debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
          debugPrint('TOOL RESULT received');
          debugPrint('  Call ID: ${msg.toolCallId}');
          debugPrint('  Content: ${msg.content}');
          debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        }

      case StateUpdateResult(state: final state):
        _currentState = state; // Run manages state
        _stateController.add(state);
        debugPrint('State updated');

      case ThinkingResult(content: final content, timestamp: final ts):
        _thinkingLog.add(ThinkingChunk(content: content, timestamp: ts));
        // Don't log individual deltas - we log the complete block above

      case LifecycleResult(lifecycle: final lifecycle):
        debugPrint('[${DateTime.now().millisecondsSinceEpoch}] Run lifecycle: ${lifecycle.name}');

        if (lifecycle == RunLifecycle.finished) {
          _handleRunFinished();
        } else if (lifecycle == RunLifecycle.error) {
          _handleRunError();
        }

      case NoResult():
        // Still accumulating chunks
        break;
    }
  }

  void _handleComplete() {
    // Stream completed - this is called by the subscription's onDone
    // Actual completion logic is in _handleRunFinished or _handleRunError
  }

  void _handleError(Object error) {
    debugPrint('[${DateTime.now().millisecondsSinceEpoch}] Run error: $error');
    status = RunStatus.failed;
    finishedAt = DateTime.now();

    // Only add error and close if not already closed
    // (can happen if RunError event already triggered _handleRunError)
    if (!_messageController.isClosed) {
      _messageController.addError(error);
      _messageController.close();
    }
    if (!_stateController.isClosed) {
      _stateController.close();
    }

    if (!_completionCompleter.isCompleted) {
      _completionCompleter.completeError(error);
    }
  }

  Future<void> _handleRunFinished() async {
    debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    debugPrint('RUN FINISHED - Checking for pending tool calls');

    final allPending = _toolCallRegistry.allPending.toList();
    final clientPending = _toolCallRegistry.getPendingClientCalls(_tools).toList();
    final interactivePending = allPending.where(
      (tc) => !_tools.any((t) => t.name == tc.function.name)
    ).toList();

    debugPrint('  Total pending: ${allPending.length}');
    debugPrint('  Client tools (auto-execute): ${clientPending.length}');
    debugPrint('  Interactive tools (need user): ${interactivePending.length}');

    if (interactivePending.isNotEmpty) {
      for (final tc in interactivePending) {
        debugPrint('  → ${tc.function.name} (${tc.id}) - WAITING FOR USER INPUT');
      }
    }
    debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    if (clientPending.isEmpty) {
      // No client tools to execute - run is complete
      // (Interactive tools will be handled via UI → sendToolResults)
      debugPrint('No client tools to execute, run complete');
      _completeRun([]);
      return;
    }

    debugPrint('Executing ${clientPending.length} client tool call(s)...');

    try {
      // Execute all client tools concurrently
      final toolMessages = await _executeClientTools(clientPending);
      _completeRun(toolMessages);
    } catch (e, stackTrace) {
      debugPrint('Error executing client tools: $e\n$stackTrace');
      _handleError(e);
    }
  }

  void _handleRunError() {
    debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    debugPrint('RUN ERROR - Aborting');

    final allPending = _toolCallRegistry.allPending.toList();
    if (allPending.isNotEmpty) {
      debugPrint('  Pending tool calls (will NOT execute):');
      for (final tc in allPending) {
        debugPrint('  → ${tc.function.name} (${tc.id})');
      }
    }
    debugPrint('━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    // Mark all pending tool calls as failed - they won't be executed
    // Just complete the run with empty list
    status = RunStatus.failed;
    finishedAt = DateTime.now();
    _messageController.close();
    _stateController.close();

    if (!_completionCompleter.isCompleted) {
      _completionCompleter.complete([]);
    }
  }

  Future<List<ToolMessage>> _executeClientTools(List<ToolCall> toolCalls) async {
    final results = await Future.wait(
      toolCalls.map((toolCall) => _executeClientTool(toolCall)),
    );

    final toolMessages = <ToolMessage>[];
    for (int i = 0; i < results.length; i++) {
      final toolCallId = toolCalls[i].id;
      final result = results[i];

      toolMessages.add(ToolMessage(
        id: _generateId(ToolMessage),
        toolCallId: toolCallId,
        content: result,
      ));

      debugPrint('Tool call result: $toolCallId = $result');
    }

    return toolMessages;
  }

  Future<String> _executeClientTool(ToolCall toolCall) async {
    final executor = _toolExecutors[toolCall.function.name];

    if (executor == null) {
      throw StateError(
        'No executor registered for client tool: ${toolCall.function.name}',
      );
    }

    try {
      debugPrint('Executing tool: ${toolCall.function.name}');
      final result = await executor(toolCall);
      debugPrint('Tool ${toolCall.function.name} completed successfully');
      return result;
    } catch (e) {
      // Client-side tool error: return error string
      debugPrint('Tool ${toolCall.function.name} failed: $e');
      return 'ERROR: ${e.toString()}';
    }
  }

  void _completeRun(List<ToolMessage> toolMessages) {
    status = RunStatus.completed;
    finishedAt = DateTime.now();
    _messageController.close();
    _stateController.close();

    debugPrint('Run completed with ${toolMessages.length} tool result(s)');

    if (!_completionCompleter.isCompleted) {
      _completionCompleter.complete(toolMessages);
    }
  }

  String _generateId(Type type) {
    return '${type}_${DateTime.now().millisecondsSinceEpoch}';
  }

  /// Cancel the run if it's still running
  Future<void> cancel() async {
    if (status == RunStatus.running) {
      await _subscription?.cancel();
      status = RunStatus.cancelled;
      finishedAt = DateTime.now();
      _messageController.close();
      _stateController.close();
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'threadId': threadId,
      'startedAt': startedAt.toIso8601String(),
      'finishedAt': finishedAt?.toIso8601String(),
      'status': status.name,
      'inputMessages': _inputMessages.map((m) => m.toJson()).toList(),
      'producedMessages': _producedMessages.map((m) => m.toJson()).toList(),
      'currentState': _currentState,
    };
  }
}

enum RunStatus {
  pending,
  running,
  completed,
  failed,
  cancelled,
}

/// A chunk of thinking content from the agent
class ThinkingChunk {
  final String content;
  final DateTime timestamp;

  ThinkingChunk({required this.content, required this.timestamp});
}
