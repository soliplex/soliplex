import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../../core/network/cancel_token.dart';
import '../../core/utils/debug_log.dart';
import 'text_message_buffer.dart';
import 'tool_call_reception_buffer.dart';
import 'tool_call_registry.dart';
import 'tool_call_state.dart';

/// Callback type for executing client-side tools.
typedef ToolExecutor = Future<String> Function(ag_ui.ToolCall call);

/// Delegate for SSE streaming via runAgent.
///
/// This allows the transport layer to intercept SSE calls for observability.
/// Uses SimpleRunAgentInput since that's what Thread creates internally.
typedef RunAgentDelegate =
    Stream<ag_ui.BaseEvent> Function(
      String endpoint,
      ag_ui.SimpleRunAgentInput input,
    );

/// Thread manages an AG-UI conversation thread.
///
/// Handles:
/// - Message history
/// - State snapshots and deltas
/// - Tool call registration and execution
/// - Event streaming
class Thread {
  final String id;
  final RunAgentDelegate _runAgentDelegate;
  final List<ag_ui.Tool> _tools;
  final Map<String, ToolExecutor> _toolExecutors;
  final Set<String> _fireAndForgetTools = {};
  final List<ag_ui.Run> _runs = [];
  final StreamController<ag_ui.Message> _messagesController;
  final StreamController<ag_ui.State> _statesController;
  final StreamController<ag_ui.BaseEvent> _stepsController;

  /// Track if thread has been disposed to prevent adding to closed streams.
  bool _disposed = false;
  bool get isDisposed => _disposed;

  ag_ui.State? currentState;
  final List<ag_ui.Message> messageHistory = [];

  // Per-message text buffers to support concurrent message streams
  final Map<String, TextMessageBuffer> _textBuffers = {};

  /// Creates a Thread with a runAgent delegate.
  ///
  /// The delegate allows SSE to flow through NetworkTransportLayer
  /// for observability via NetworkInspector.
  Thread({
    required this.id,
    required RunAgentDelegate runAgent,
    List<ag_ui.Tool>? tools,
    Map<String, ToolExecutor>? toolExecutors,
  }) : _runAgentDelegate = runAgent,
       _tools = tools != null ? List.from(tools) : <ag_ui.Tool>[],
       _toolExecutors = toolExecutors != null
           ? Map.from(toolExecutors)
           : <String, ToolExecutor>{},
       _messagesController = StreamController.broadcast(),
       _statesController = StreamController.broadcast(),
       _stepsController = StreamController.broadcast() {
    stateStream.forEach((s) => currentState = s);
  }

  /// Get the SSE stream for runAgent via delegate.
  Stream<ag_ui.BaseEvent> _getRunAgentStream(
    String endpoint,
    ag_ui.SimpleRunAgentInput input,
  ) {
    return _runAgentDelegate(endpoint, input);
  }

  Iterable<ag_ui.Run> get runs => _runs;

  final Map<String, ToolCallReceptionBuffer> _toolCallReceptions = {};
  final _toolRegistry = ToolCallRegistry();

  /// Stream of messages (user and assistant).
  Stream<ag_ui.Message> get messageStream => _messagesController.stream;

  /// Stream of state updates.
  Stream<ag_ui.State> get stateStream => _statesController.stream;

  /// Stream of all AG-UI events (for UI updates).
  Stream<ag_ui.BaseEvent> get stepsStream => _stepsController.stream;

  /// List of registered tools.
  List<ag_ui.Tool> get tools => List.unmodifiable(_tools);

  /// Stream of tool call state changes for UI notifications.
  Stream<ToolCallStateChange> get toolStateChanges =>
      _toolRegistry.stateChanges;

  /// Add a tool dynamically.
  ///
  /// If a tool with the same name already exists, it will be replaced.
  /// This is idempotent - calling with the same tool name multiple times
  /// will update the executor and tool definition.
  ///
  /// If [fireAndForget] is true, the tool will be executed but its result
  /// will NOT be sent back to the server. Use this for UI-only tools like
  /// genui_render and canvas_render that don't need a follow-up response.
  void addTool(
    ag_ui.Tool tool,
    ToolExecutor executor, {
    bool fireAndForget = false,
  }) {
    // Remove existing tool with same name to prevent duplicates
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
  void removeTool(String toolName) {
    _tools.removeWhere((t) => t.name == toolName);
    _toolExecutors.remove(toolName);
  }

  /// Safely add to steps stream (checks if disposed).
  void _addStep(ag_ui.BaseEvent event) {
    if (!_disposed) _stepsController.add(event);
  }

  /// Safely add to messages stream (checks if disposed).
  void _addMessage(ag_ui.Message message) {
    if (!_disposed) _messagesController.add(message);
  }

  /// Safely add to states stream (checks if disposed).
  void _addState(ag_ui.State state) {
    if (!_disposed) _statesController.add(state);
  }

  /// Start a run and process events.
  ///
  /// Returns list of tool messages if client tools were executed
  /// (caller should call again with these results).
  ///
  /// [cancelToken] can be used to cancel the run mid-stream.
  Future<List<ag_ui.ToolMessage>> startRun({
    required String endpoint,
    required String runId,
    List<ag_ui.Message>? messages,
    dynamic state,
    CancelToken? cancelToken,
  }) async {
    // Check if disposed before starting
    if (_disposed) {
      DebugLog.thread(' startRun called on disposed thread, ignoring');
      return [];
    }

    // Check if already cancelled
    cancelToken?.throwIfCancelled();

    final run = ag_ui.Run(threadId: id, runId: runId);
    _runs.add(run);

    // Add any new messages to history
    messageHistory.addAll(messages ?? []);
    (messages ?? []).forEach(_addMessage);

    final agentInput = ag_ui.SimpleRunAgentInput(
      threadId: id,
      runId: runId,
      messages: messageHistory,
      state: state,
      tools: _tools,
    );

    try {
      DebugLog.thread(' Starting await for loop on SSE stream');
      final stream = _getRunAgentStream(endpoint, agentInput);
      await for (final event in stream) {
        DebugLog.thread(' Received event: ${event.runtimeType}');
        // Check if disposed during streaming
        if (_disposed) {
          DebugLog.thread(' disposed during event stream, stopping');
          break;
        }
        // Check if cancelled during streaming
        if (cancelToken?.isCancelled == true) {
          DebugLog.thread(' cancelled during event stream, stopping');
          throw CancelledException(cancelToken!.cancelReason);
        }
        _addStep(event);

        switch (event) {
          case ag_ui.TextMessageChunkEvent(
            messageId: final msgId,
            delta: final text,
          ):
            final message = ag_ui.AssistantMessage(id: msgId, content: text);
            messageHistory.add(message);
            _addMessage(message);

          case ag_ui.TextMessageStartEvent(messageId: final msgId):
            _textBuffers[msgId] = TextMessageBuffer(msgId);

          case ag_ui.TextMessageContentEvent(
            messageId: final msgId,
            delta: final text,
          ):
            _textBuffers[msgId]?.add(msgId, text);

          case ag_ui.TextMessageEndEvent(messageId: final msgId):
            final buffer = _textBuffers.remove(msgId);
            final message = ag_ui.AssistantMessage(
              id: msgId,
              content: buffer?.content ?? '',
            );
            messageHistory.add(message);
            _addMessage(message);

          case ag_ui.StepStartedEvent():
            // Already added to stepsController above
            break;

          case ag_ui.StepFinishedEvent():
            // Already added to stepsController above
            break;

          case ag_ui.ToolCallStartEvent(
            toolCallId: final id,
            toolCallName: final name,
          ):
            _toolCallReceptions[id] = ToolCallReceptionBuffer(id, name);

          case ag_ui.ToolCallArgsEvent(
            toolCallId: final id,
            delta: final delta,
          ):
            _toolCallReceptions[id]?.appendArgs(delta);

          case ag_ui.ToolCallEndEvent(toolCallId: final id):
            final receivedToolCall = _toolCallReceptions.remove(id);

            if (receivedToolCall == null) break;

            messageHistory.add(receivedToolCall.message);

            final toolCall = receivedToolCall.toolCall;
            final isClientTool = _tools.any(
              (t) => t.name == toolCall.function.name,
            );
            if (isClientTool) {
              _toolRegistry.register(toolCall);
            }

          case ag_ui.ToolCallResultEvent(
            messageId: final msgId,
            toolCallId: final id,
            content: final content,
          ):
            final result = ag_ui.ToolMessage(
              id: msgId,
              toolCallId: id,
              content: content,
            );

            messageHistory.add(result);
            _toolRegistry.markCompleted(id, result);

          case ag_ui.StateSnapshotEvent(snapshot: final snapshot):
            _addState(snapshot);

          case ag_ui.StateDeltaEvent(delta: final deltas):
            // Simple merge for now (full JSON patch would require json_patch package)
            if (currentState is Map<String, dynamic>) {
              final current = currentState as Map<String, dynamic>;
              for (final delta in deltas) {
                if (delta is Map<String, dynamic>) {
                  current.addAll(delta);
                }
              }
              _addState(current);
            }

          case ag_ui.ActivitySnapshotEvent():
            // Activity snapshot - already forwarded to stepsStream above
            // Processing handled by UI layer
            break;

          // Thinking events - forwarded to stepsStream, handled by UI layer
          case ag_ui.ThinkingStartEvent():
          case ag_ui.ThinkingContentEvent():
          case ag_ui.ThinkingEndEvent():
          case ag_ui.ThinkingTextMessageStartEvent():
          case ag_ui.ThinkingTextMessageContentEvent():
          case ag_ui.ThinkingTextMessageEndEvent():
            break;

          // Run lifecycle events - forwarded to stepsStream
          case ag_ui.RunStartedEvent():
          case ag_ui.RunFinishedEvent():
            break;

          case ag_ui.RunErrorEvent(
            message: final errorMessage,
            code: final errorCode,
          ):
            final message = ag_ui.AssistantMessage(
              id: 'run-event-error-${event.timestamp ?? DateTime.now()}',
              content:
                  'Error${errorCode != null ? ' (Code $errorCode)' : ''}: $errorMessage',
            );
            messageHistory.add(message);
            _addMessage(message);

          default:
            break; // Ignore unknown events
        }
      }
    } catch (e) {
      // Handle decoding errors from ag_ui package gracefully
      final errorStr = e.toString();
      if (errorStr.contains('DecodingError') ||
          errorStr.contains('Invalid event type')) {
        DebugLog.thread('Decoding error (continuing): $e');
      } else {
        rethrow;
      }
    }

    DebugLog.thread(' SSE stream completed, checking for pending tool calls');

    // Execute any pending client tools
    final pendingToolCalls = _toolRegistry.pendingCalls;
    if (pendingToolCalls.isEmpty) {
      return [];
    }

    // _executeClientTools handles state transitions internally via tryStartExecution
    final results = await _executeClientTools(pendingToolCalls.toList());
    return results;
  }

  Future<List<ag_ui.ToolMessage>> _executeClientTools(
    List<ag_ui.ToolCall> toolCalls,
  ) async {
    final toolMessages = <ag_ui.ToolMessage>[];
    final futures = <Future<void>>[];

    for (final toolCall in toolCalls) {
      // Atomically try to start execution - prevents double execution
      final callToExecute = _toolRegistry.tryStartExecution(toolCall.id);
      if (callToExecute == null) {
        continue; // Already executing or completed
      }
      futures.add(_executeAndTrack(callToExecute, toolMessages));
    }

    await Future.wait(futures);
    return toolMessages;
  }

  /// Execute a tool call and track its result.
  Future<void> _executeAndTrack(
    ag_ui.ToolCall toolCall,
    List<ag_ui.ToolMessage> results,
  ) async {
    final toolName = toolCall.function.name;
    final isFireAndForget = _fireAndForgetTools.contains(toolName);

    try {
      final result = await _executeClientTool(toolCall);
      final message = ag_ui.ToolMessage(
        id: 'msg-${toolCall.id}',
        toolCallId: toolCall.id,
        content: result,
      );

      // Only add to results if NOT fire-and-forget
      // Fire-and-forget tools execute but don't send results back to server
      if (!isFireAndForget) {
        results.add(message);
      } else {
        DebugLog.thread(
          ' Fire-and-forget tool $toolName executed, not sending result back',
        );
      }
      _toolRegistry.markCompleted(toolCall.id, message);
    } catch (e) {
      DebugLog.thread(' Tool execution failed for $toolName: $e');
      _toolRegistry.markFailed(toolCall.id, e.toString());
      // Still add an error result so the conversation can continue (unless fire-and-forget)
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

  Future<String> _executeClientTool(ag_ui.ToolCall toolCall) async {
    final executor = _toolExecutors[toolCall.function.name];

    if (executor == null) {
      throw StateError(
        'No executor registered for client tool: ${toolCall.function.name}',
      );
    }

    try {
      return await executor(toolCall);
    } catch (e) {
      return 'ERROR: ${e.toString()}';
    }
  }

  /// Send tool results and continue the run.
  Future<List<ag_ui.ToolMessage>> sendToolResults({
    required String endpoint,
    required String runId,
    required List<ag_ui.ToolMessage> toolMessages,
    CancelToken? cancelToken,
  }) async {
    return startRun(
      endpoint: endpoint,
      runId: runId,
      messages: toolMessages,
      cancelToken: cancelToken,
    );
  }

  /// Clear all state for a new conversation.
  void reset() {
    messageHistory.clear();
    _runs.clear();
    _toolCallReceptions.clear();
    _toolRegistry.clear();
    _textBuffers.clear();
    currentState = null;
  }

  void dispose() {
    _disposed = true;
    _messagesController.close();
    _statesController.close();
    _stepsController.close();
    _toolRegistry.dispose();
  }
}
