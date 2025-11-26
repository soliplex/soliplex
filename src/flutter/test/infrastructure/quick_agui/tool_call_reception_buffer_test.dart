import 'package:flutter_test/flutter_test.dart';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import 'package:soliplex_client/infrastructure/quick_agui/tool_call_reception_buffer.dart';

void main() {
  group('ToolCallReceptionBuffer class', () {
    test('should accept an id and a name parameter and expose them', () {
      // Arrange & Act
      final buffer = ToolCallReceptionBuffer('tool-call-id', 'tool-call-name');

      // Assert
      expect(buffer.name, equals('tool-call-id'));
      expect(buffer.name, equals('tool-call-name'));
    });

    test('args initially empty, can be appended', () {
      // Arrange
      final buffer = ToolCallReceptionBuffer('tool-call-id', 'add-numbers');
      expect(buffer.args, equals(''));

      // Act
      buffer.appendArgs("{'arg1':");
      buffer.appendArgs(" 1, '");
      buffer.appendArgs("arg2'");
      buffer.appendArgs(": 2}");

      // Assert
      expect(buffer.args, equals("{'arg1': 1, 'arg2': 2}"));
    });

    test('generate an assistant message with proper values', () {
      // Arrange
      const toolCallId = 'tool-call-id';
      const toolCallName = 'add-numbers';
      final buffer = ToolCallReceptionBuffer(toolCallId, toolCallName);
      expect(buffer.args, equals(''));

      // Act
      buffer.appendArgs("{'arg1':");
      buffer.appendArgs(" 1, '");
      buffer.appendArgs("arg2'");
      buffer.appendArgs(": 2}");

      // Assert
      final message = buffer.toMessage;
      expect(
        message,
        isA<ag_ui.AssistantMessage>().having(
          (m) => m.toJson(),
          'entire message in json',
          equals(message.toJson()),
        ),
      );

      expect(message.id, equals('msg_$toolCallId'));
      expect(message.toolCalls?.length ?? 0, equals(1));

      final [toolCall] = message.toolCalls!;

      expect(toolCall.id, equals(toolCallId));

      final functionCall = toolCall.function;

      expect(functionCall.name, toolCallName);
      expect(functionCall.arguments, "{'arg1': 1, 'arg2': 2}");
    });
  });
}
