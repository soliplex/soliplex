import 'package:flutter_test/flutter_test.dart';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import 'package:soliplex_client/infrastructure/quick_agui/tool_call_registry.dart';

void main() {
  group('ToolCallRegistry class', () {
    test('pending calls initially empty', () {
      final registry = ToolCallRegistry();
      expect(registry.pendingCalls, isEmpty);
    });

    test('registering a call adds to pending calls', () {
      final registry = ToolCallRegistry();

      final toolCall = ag_ui.ToolCall(
        id: 'tool-call-id',
        function: ag_ui.FunctionCall(
          name: 'tool-call-name',
          arguments: 'any-argument',
        ),
      );

      registry.register(toolCall);

      expect(registry.pendingCalls.length, equals(1));
      expect(registry.pendingCalls.first.toJson(), equals(toolCall.toJson()));
    });

    test('completing a call removes from pending calls', () {
      final registry = ToolCallRegistry();

      const toolCallId = 'tool-call-id';
      const toolCallName = 'tool-call-name';

      final toolCall = ag_ui.ToolCall(
        id: toolCallId,
        function: ag_ui.FunctionCall(
          name: toolCallName,
          arguments: 'any-argument',
        ),
      );

      registry.register(toolCall);

      expect(registry.pendingCalls.length, equals(1));
      expect(registry.pendingCalls.first.toJson(), equals(toolCall.toJson()));

      const resultMessageId = 'result-message-id';
      const resultMessage = 'any-result';

      final result = ag_ui.ToolMessage(
        id: resultMessageId,
        toolCallId: toolCall.id,
        content: resultMessage,
      );

      registry.markCompleted(toolCallId, result);

      expect(registry.pendingCalls, isEmpty);

      expect(registry.results.length, equals(1));
      expect(
        registry.results.first,
        equals(
          isToolResult(
            id: resultMessageId,
            toolCallId: toolCallId,
            msg: resultMessage,
          ),
        ),
      );
    });
  });
}

TypeMatcher<ag_ui.ToolMessage> isToolResult({
  required String id,
  required String toolCallId,
  required String msg,
}) => isA<ag_ui.ToolMessage>()
    .having((m) => m.id, "id", equals(id))
    .having((m) => m.toolCallId, "tool call id", equals(toolCallId))
    .having((m) => m.content, 'content', equals(msg));
