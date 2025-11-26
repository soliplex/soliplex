import 'dart:async';

import 'package:flutter/foundation.dart';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import 'text_message_buffer.dart';
import 'tool_call_reception_buffer.dart';

class Thread {
  final String id;
  final ag_ui.AgUiClient client;
  final List<ag_ui.Run> _runs = [];
  final StreamController<ag_ui.Message> _messagesController;
  final StreamController<ag_ui.State> _statesController;
  final List<ag_ui.Message> messageHistory = [];

  var _textBuffer = TextMessageBuffer('');

  Thread({required this.id, required this.client})
    : _messagesController = StreamController.broadcast(),
      _statesController = StreamController.broadcast();

  Iterable<ag_ui.Run> get runs => _runs;

  final Map<String, ToolCallReceptionBuffer> _toolCallReceptions = {};

  Stream<ag_ui.Message> get messageStream => _messagesController.stream;

  Stream<ag_ui.State> get stateStream => _statesController.stream;

  Future<void> startRun({
    required String endpoint,
    required String runId,
    required ag_ui.UserMessage message,
  }) async {
    final run = ag_ui.Run(threadId: id, runId: runId);
    _runs.add(run);

    messageHistory.add(message);
    _messagesController.add(message);

    final agentInput = ag_ui.SimpleRunAgentInput(
      threadId: id,
      runId: runId,
      messages: messageHistory,
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

        case ag_ui.StepStartedEvent(stepName: final stepName):
          _statesController.add({'step': stepName});

        case ag_ui.ToolCallStartEvent(
          toolCallId: final id,
          toolCallName: final name,
        ):
          _toolCallReceptions[id] = ToolCallReceptionBuffer(name);

        case ag_ui.ToolCallArgsEvent(toolCallId: final id, delta: final delta):
          _toolCallReceptions[id]?.appendArgs(delta);

        case ag_ui.ToolCallEndEvent(toolCallId: final id):
          final receivedToolCall = _toolCallReceptions.remove(id);

          if (receivedToolCall == null) break;

          final toolCall = ag_ui.AssistantMessage(
            // TODO: may need to get msg some other way (generate it or retrieve it from server).
            id: 'msg_$id',
            toolCalls: [
              ag_ui.ToolCall(
                id: id,
                function: ag_ui.FunctionCall(
                  name: receivedToolCall.name,
                  arguments: receivedToolCall.args.isEmpty
                      ? '{}'
                      : receivedToolCall.args,
                ),
              ),
            ],
          );
          _messagesController.add(toolCall);

        case ag_ui.ToolCallResultEvent(
          messageId: final msgId,
          toolCallId: final id,
          content: final content,
        ):
          _messagesController.add(
            ag_ui.ToolMessage(id: msgId, toolCallId: id, content: content),
          );

        default:
          debugPrint("Ignored $event");
      }
    }
  }
}
