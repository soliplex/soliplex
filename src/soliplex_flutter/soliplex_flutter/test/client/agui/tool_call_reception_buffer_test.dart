import 'package:soliplex_flutter/client/agui/tool_call_reception_buffer.dart';
import 'package:test/test.dart';

void main() {
  group('ToolCallReceptionBuffer', () {
    test('creates with id and name', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'search');

      expect(buffer.id, equals('tc1'));
      expect(buffer.name, equals('search'));
      expect(buffer.args, isEmpty);
    });

    test('appendArgs accumulates arguments', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'search');

      buffer.appendArgs('{"query":');
      expect(buffer.args, equals('{"query":'));

      buffer.appendArgs(' "test"}');
      expect(buffer.args, equals('{"query": "test"}'));
    });

    test('toolCall returns AG-UI ToolCall with empty args', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'search');

      final toolCall = buffer.toolCall;

      expect(toolCall.id, equals('tc1'));
      expect(toolCall.function.name, equals('search'));
      expect(toolCall.function.arguments, equals('{}'));
    });

    test('toolCall returns AG-UI ToolCall with accumulated args', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'search');
      buffer.appendArgs('{"query": "hello"}');

      final toolCall = buffer.toolCall;

      expect(toolCall.id, equals('tc1'));
      expect(toolCall.function.name, equals('search'));
      expect(toolCall.function.arguments, equals('{"query": "hello"}'));
    });

    test('message returns AssistantMessage with tool call', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'search');
      buffer.appendArgs('{"query": "test"}');

      final message = buffer.message;

      expect(message.id, equals('msg_tc1'));
      expect(message.toolCalls, hasLength(1));
      expect(message.toolCalls!.first.id, equals('tc1'));
      expect(message.toolCalls!.first.function.name, equals('search'));
    });

    test('toString includes id and name', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'search');

      final str = buffer.toString();

      expect(str, contains('tc1'));
      expect(str, contains('search'));
    });

    test('multiple appends work correctly', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'complex_tool');

      buffer.appendArgs('{');
      buffer.appendArgs('"key1":');
      buffer.appendArgs(' "value1",');
      buffer.appendArgs(' "key2": 42');
      buffer.appendArgs('}');

      expect(buffer.args, equals('{"key1": "value1", "key2": 42}'));
    });

    test('args getter returns empty string for new buffer', () {
      final buffer = ToolCallReceptionBuffer('tc1', 'test_tool');

      expect(buffer.args, equals(''));
    });

    test('works with different tool names', () {
      final buffer1 = ToolCallReceptionBuffer('tc1', 'search');
      final buffer2 = ToolCallReceptionBuffer('tc2', 'fetch_data');

      expect(buffer1.name, equals('search'));
      expect(buffer2.name, equals('fetch_data'));

      expect(buffer1.toolCall.function.name, equals('search'));
      expect(buffer2.toolCall.function.name, equals('fetch_data'));
    });
  });
}
