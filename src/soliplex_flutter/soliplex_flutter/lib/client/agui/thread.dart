import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../utils/cancel_token.dart';
import 'text_message_buffer.dart';
import 'tool_call_reception_buffer.dart';
import 'tool_call_registry.dart';

/// Function signature for tool executors.
typedef ToolExecutor = Future<String> Function(ag_ui.ToolCall call);

/// Handles AG-UI protocol for a single thread.
class Thread {
  Thread({required this.id, required this.client});

  final String id;
  final ag_ui.AgUiClient client;

  final List<ag_ui.Tool> _tools = [];
  final Map<String, ToolExecutor> _toolExecutors = {};
  final Set<String> _fireAndForgetTools = {};
  final List<ag_ui.Run> _runs = [];
  final List<ag_ui.Message> _messageHistory = [];
  final Map<String, TextMessageBuffer> _textBuffers = {};
  final Map<String, ToolCallReceptionBuffer> _toolCallBuffers = {};
  final ToolCallRegistry _toolRegistry = ToolCallRegistry();

  final StreamController<ag_ui.Message> _messageController =
      StreamController<ag_ui.Message>.broadcast();
  final StreamController<ag_ui.BaseEvent> _stepsController =
      StreamController<ag_ui.BaseEvent>.broadcast();

  bool _disposed = false;

  /// Stream of messages.
  Stream<ag_ui.Message> get messageStream => _messageController.stream;

  /// Stream of all events (steps).
  Stream<ag_ui.BaseEvent> get stepsStream => _stepsController.stream;

  /// Get the message history.
  List<ag_ui.Message> get messageHistory => List.unmodifiable(_messageHistory);

  /// Get all runs.
  List<ag_ui.Run> get runs => List.unmodifiable(_runs);

  /// Get pending tool calls.
  Iterable<ag_ui.ToolCall> get pendingToolCalls => _toolRegistry.pendingCalls;

  /// Add a tool.
  ///
  /// If [fireAndForget] is true, the tool will be executed but its result
  /// will NOT be sent back to the server.
  void addTool(
    ag_ui.Tool tool,
    ToolExecutor executor, {
    bool fireAndForget = false,
  }) {
    // Remove existing tool with same name
    _tools.removeWhere((t) => t.name == tool.name);
    _tools.add(tool);
    _toolExecutors[tool.name] = executor;

    if (fireAndForget) {
      _fireAndForgetTools.add(tool.name);
    } else {
      _fireAndForgetTools.remove(tool.name);
    }
  }

  /// Remove a tool.
  void removeTool(String name) {
    _tools.removeWhere((t) => t.name == name);
    _toolExecutors.remove(name);
    _fireAndForgetTools.remove(name);
  }

  /// Start a run and process events.
  ///
  /// Returns a list of tool messages to send back (empty if no tool calls
  /// or all tools are fire-and-forget).
  Future<List<ag_ui.ToolMessage>> startRun({
    required String endpoint,
    required String runId,
    List<ag_ui.Message>? messages,
    dynamic state,
    CancelToken? cancelToken,
  }) async {
    if (_disposed) return [];
    cancelToken?.throwIfCancelled();

    final run = ag_ui.Run(threadId: id, runId: runId);
    _runs.add(run);

    // Add new messages to history
    if (messages != null) {
      _messageHistory.addAll(messages);
      for (final msg in messages) {
        _addMessage(msg);
      }
    }

    final agentInput = ag_ui.SimpleRunAgentInput(
      threadId: id,
      runId: runId,
      messages: _messageHistory,
      state: state,
      tools: _tools,
    );

    try {
      await for (final event in client.runAgent(endpoint, agentInput)) {
        if (_disposed) break;
        cancelToken?.throwIfCancelled();

        _addStep(event);
        _processEvent(event);
      }
    } on ag_ui.DecodingError {
      // Ignore decoding errors - some events may be malformed
    }

    // Execute pending client tools
    final pendingCalls = _toolRegistry.pendingCalls.toList();
    if (pendingCalls.isEmpty) return [];

    return _executeClientTools(pendingCalls);
  }

  void _processEvent(ag_ui.BaseEvent event) {
    switch (event) {
      case ag_ui.TextMessageStartEvent(messageId: final msgId):
        _textBuffers[msgId] = TextMessageBuffer(msgId);

      case ag_ui.TextMessageContentEvent(
        messageId: final msgId,
        delta: final text,
      ):
        _textBuffers[msgId]?.add(msgId, text);

      case ag_ui.TextMessageEndEvent(messageId: final msgId):
        final buffer = _textBuffers.remove(msgId);
        if (buffer != null) {
          final message = ag_ui.AssistantMessage(
            id: msgId,
            content: buffer.content,
          );
          _messageHistory.add(message);
          _addMessage(message);
        }

      case ag_ui.ToolCallStartEvent(
        toolCallId: final tcId,
        toolCallName: final name,
      ):
        _toolCallBuffers[tcId] = ToolCallReceptionBuffer(tcId, name);

      case ag_ui.ToolCallArgsEvent(toolCallId: final tcId, delta: final delta):
        _toolCallBuffers[tcId]?.appendArgs(delta);

      case ag_ui.ToolCallEndEvent(toolCallId: final tcId):
        final buffer = _toolCallBuffers.remove(tcId);
        if (buffer != null) {
          _messageHistory.add(buffer.message);
          final toolCall = buffer.toolCall;
          final isClientTool = _tools.any(
            (t) => t.name == toolCall.function.name,
          );
          if (isClientTool) {
            _toolRegistry.register(toolCall);
          }
        }

      default:
        // Other events are forwarded via stepsStream
        break;
    }
  }

  Future<List<ag_ui.ToolMessage>> _executeClientTools(
    List<ag_ui.ToolCall> toolCalls,
  ) async {
    final toolMessages = <ag_ui.ToolMessage>[];
    final futures = <Future<void>>[];

    for (final toolCall in toolCalls) {
      final callToExecute = _toolRegistry.tryStartExecution(toolCall.id);
      if (callToExecute == null) continue;

      futures.add(_executeAndTrack(callToExecute, toolMessages));
    }

    await Future.wait(futures);
    return toolMessages;
  }

  Future<void> _executeAndTrack(
    ag_ui.ToolCall toolCall,
    List<ag_ui.ToolMessage> results,
  ) async {
    final toolName = toolCall.function.name;
    final executor = _toolExecutors[toolName];
    final isFireAndForget = _fireAndForgetTools.contains(toolName);

    if (executor == null) {
      final errorMessage = ag_ui.ToolMessage(
        id: 'msg-${toolCall.id}',
        toolCallId: toolCall.id,
        content: 'ERROR: No executor for tool $toolName',
      );
      _toolRegistry.markFailed(toolCall.id, 'No executor');
      if (!isFireAndForget) {
        results.add(errorMessage);
      }
      return;
    }

    try {
      final result = await executor(toolCall);
      final message = ag_ui.ToolMessage(
        id: 'msg-${toolCall.id}',
        toolCallId: toolCall.id,
        content: result,
      );

      if (!isFireAndForget) {
        results.add(message);
      }
      _toolRegistry.markCompleted(toolCall.id, message);
    } catch (e) {
      _toolRegistry.markFailed(toolCall.id, e.toString());
      if (!isFireAndForget) {
        results.add(
          ag_ui.ToolMessage(
            id: 'msg-${toolCall.id}',
            toolCallId: toolCall.id,
            content: 'ERROR: $e',
          ),
        );
      }
    }
  }

  void _addMessage(ag_ui.Message message) {
    if (!_messageController.isClosed) {
      _messageController.add(message);
    }
  }

  void _addStep(ag_ui.BaseEvent event) {
    if (!_stepsController.isClosed) {
      _stepsController.add(event);
    }
  }

  /// Dispose the thread.
  void dispose() {
    _disposed = true;
    _messageController.close();
    _stepsController.close();
    _textBuffers.clear();
    _toolCallBuffers.clear();
    _toolRegistry.clear();
  }

  @override
  String toString() => 'Thread(id: $id, runs: ${_runs.length})';
}
