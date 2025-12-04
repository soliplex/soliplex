import 'dart:async';

import 'package:flutter/foundation.dart';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:json_patch/json_patch.dart';

import 'text_message_buffer.dart';
import 'tool_call_reception_buffer.dart';
import 'tool_call_registry.dart';

class Thread {
  final String id;
  final ag_ui.AgUiClient client;
  final List<ag_ui.Tool> _tools;
  final Map<String, Future<String> Function(ag_ui.ToolCall)> _toolExecutors;
  final List<ag_ui.Run> _runs = [];
  final StreamController<ag_ui.Message> _messagesController;
  final StreamController<ag_ui.State> _statesController;
  final StreamController<ag_ui.BaseEvent> _stepsController;

  ag_ui.State? currentState;
  final List<ag_ui.Message> messageHistory = [];

  var _textBuffer = TextMessageBuffer('');

  Thread({
    required this.id,
    required this.client,
    List<ag_ui.Tool> tools = const <ag_ui.Tool>[],
    Map<String, Future<String> Function(ag_ui.ToolCall)> toolExecutors =
        const <String, Future<String> Function(ag_ui.ToolCall)>{},
  }) : _tools = tools,
       _toolExecutors = toolExecutors,
       _messagesController = StreamController.broadcast(),
       _statesController = StreamController.broadcast(),
       _stepsController = StreamController.broadcast() {
    stateStream.forEach((s) => currentState = s);
  }

  Iterable<ag_ui.Run> get runs => _runs;

  final Map<String, ToolCallReceptionBuffer> _toolCallReceptions = {};
  final _toolRegistry = ToolCallRegistry();

  Stream<ag_ui.Message> get messageStream => _messagesController.stream;

  Stream<ag_ui.State> get stateStream => _statesController.stream;

  Stream<ag_ui.BaseEvent> get stepsStream => _stepsController.stream;

  Future<List<ag_ui.ToolMessage>> startRun({
    required String endpoint,
    required String runId,
    List<ag_ui.Message>? messages,
    dynamic state,
  }) async {
    final run = ag_ui.Run(threadId: id, runId: runId);
    _runs.add(run);

    // TODO: should we synchronise the `messageHistory` iterable by listening to the message stream?
    messageHistory.addAll(messages ?? []);
    (messages ?? []).forEach(_messagesController.add);

    final agentInput = ag_ui.SimpleRunAgentInput(
      threadId: id,
      runId: runId,
      messages: messageHistory,
      state: state,
      tools: _tools,      
    );

    await for (final event in client.runAgent(endpoint, agentInput)) {
      switch (event) {
        case ag_ui.TextMessageChunkEvent(
          messageId: final msgId,
          delta: final text,
        ):
          final message = ag_ui.AssistantMessage(id: msgId, content: text);
          messageHistory.add(message);
          _messagesController.add(message);

        case ag_ui.TextMessageStartEvent(messageId: final msgId):
          _textBuffer = TextMessageBuffer(msgId);

        case ag_ui.TextMessageContentEvent(
          messageId: final msgId,
          delta: final text,
        ):
          _textBuffer.add(msgId, text);

        case ag_ui.TextMessageEndEvent(messageId: final msgId):
          final message = ag_ui.AssistantMessage(
            id: msgId,
            content: _textBuffer.content,
          );
          messageHistory.add(message);
          _messagesController.add(message);

        case ag_ui.StepStartedEvent():
          _stepsController.add(event);

        case ag_ui.StepFinishedEvent():
          _stepsController.add(event);

        case ag_ui.ToolCallStartEvent(
          toolCallId: final id,
          toolCallName: final name,
        ):
          _toolCallReceptions[id] = ToolCallReceptionBuffer(id, name);

        case ag_ui.ToolCallArgsEvent(toolCallId: final id, delta: final delta):
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
          _statesController.add(snapshot);

        case ag_ui.StateDeltaEvent(delta: final deltas):
          _statesController.add(
            JsonPatch.apply(currentState, deltas.cast<Map<String, dynamic>>()),
          );

        default:
          debugPrint("Ignored $event");
      }
    }

    final pendingToolCalls = _toolRegistry.pendingCalls;
    if (pendingToolCalls.isEmpty) {
      return [];
    }
    final results = await _executeClientTools(pendingToolCalls.toList());
    return results;
  }

  Future<List<ag_ui.ToolMessage>> _executeClientTools(
    List<ag_ui.ToolCall> toolCalls,
  ) async {
    final results = await Future.wait(
      toolCalls.map((toolCall) => _executeClientTool(toolCall)),
    );

    final toolMessages = <ag_ui.ToolMessage>[];
    for (int i = 0; i < results.length; i++) {
      final toolCallId = toolCalls[i].id;
      final result = results[i];

      toolMessages.add(
        ag_ui.ToolMessage(
          // TODO: may need to get msg some other way (generate it or retrieve it from server).
          id: 'msg-$toolCallId',
          toolCallId: toolCallId,
          content: result,
        ),
      );
    }

    return toolMessages;
  }

  Future<String> _executeClientTool(ag_ui.ToolCall toolCall) async {
    final executor = _toolExecutors[toolCall.function.name];

    if (executor == null) {
      throw StateError(
        'No executor registered for client tool: ${toolCall.function.name}',
      );
    }

    try {
      final result = await executor(toolCall);
      return result;
    } catch (e) {
      return 'ERROR: ${e.toString()}';
    }
  }

  Future<List<ag_ui.ToolMessage>> sendToolResults({
    required String endpoint,
    required String runId,
    required List<ag_ui.ToolMessage> toolMessages,
  }) async {
    return startRun(endpoint: endpoint, runId: runId, messages: toolMessages);
  }
}
