import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';

class Thread {
  final String id;
  final ag_ui.AgUiClient client;
  final List<ag_ui.Run> _runs = [];
  final StreamController<ag_ui.Message> _messagesController;

  Thread({required this.id, required this.client})
    : _messagesController = StreamController.broadcast();

  Iterable<ag_ui.Run> get runs => _runs;

  Stream<ag_ui.Message> get messageStream => _messagesController.stream;

  Future<void> startRun({
    required String runId,
    required ag_ui.UserMessage message,
  }) async {
    final run = ag_ui.Run(threadId: id, runId: runId);
    _runs.add(run);

    _messagesController.add(message);

    final agentInput = ag_ui.SimpleRunAgentInput(
      threadId: id,
      runId: runId,
      messages: [message],
    );

    await for (final event in client.runAgent('endpoint', agentInput)) {
      switch (event) {
        case ag_ui.TextMessageChunkEvent(
          messageId: final msgId,
          delta: final text,
        ):
          final message = ag_ui.AssistantMessage(id: msgId, content: text);
          _messagesController.add(message);

        default:
          debugPrint("Ignore $event");
      }
    }
  }
}
