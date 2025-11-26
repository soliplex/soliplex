import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex_client/infrastructure/quick_agui/tool_call_reception_buffer.dart';

void main() {
  group('PendingToolCall class', () {
    test('should accept a name parameter and expose it', () {
      // Arrange & Act
      final buffer = ToolCallReceptionBuffer('tool-call-name');

      // Assert
      expect(buffer.name, equals('tool-call-name'));
    });

    test('args initially empty, can be appended', () {
      // Arrange
      final buffer = ToolCallReceptionBuffer('add-numbers');
      expect(buffer.args, equals(''));

      // Act
      buffer.appendArgs("{'arg1':");
      buffer.appendArgs(" 1, '");
      buffer.appendArgs("arg2'");
      buffer.appendArgs(": 2}");

      // Assert
      expect(buffer.args, equals("{'arg1': 1, 'arg2': 2}"));
    });
  });
}
