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
      final toolCall = ag_ui.ToolCall(
        id: toolCallId,
        function: ag_ui.FunctionCall(
          name: 'tool-call-name',
          arguments: 'any-argument',
        ),
      );

      registry.register(toolCall);

      expect(registry.pendingCalls.length, equals(1));
      expect(registry.pendingCalls.first.toJson(), equals(toolCall.toJson()));

      registry.markCompleted(toolCallId);

      expect(registry.pendingCalls, isEmpty);
    });
  });
}
