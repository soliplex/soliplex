import 'package:soliplex_flutter/client/models/chat_message.dart';
import 'package:test/test.dart';

void main() {
  group('ChatMessage', () {
    group('text factory', () {
      test('creates text message with required fields', () {
        final message = ChatMessage.text(
          user: ChatUser.user,
          text: 'Hello',
        );

        expect(message.user, equals(ChatUser.user));
        expect(message.text, equals('Hello'));
        expect(message.type, equals(MessageType.text));
        expect(message.isStreaming, isFalse);
        expect(message.id, isNotEmpty);
      });

      test('creates text message with all fields', () {
        final message = ChatMessage.text(
          user: ChatUser.assistant,
          text: 'Response',
          id: 'custom-id',
          isStreaming: true,
        );

        expect(message.id, equals('custom-id'));
        expect(message.user, equals(ChatUser.assistant));
        expect(message.text, equals('Response'));
        expect(message.isStreaming, isTrue);
      });
    });

    group('error factory', () {
      test('creates error message', () {
        final message = ChatMessage.error(message: 'Something went wrong');

        expect(message.user, equals(ChatUser.system));
        expect(message.type, equals(MessageType.error));
        expect(message.errorMessage, equals('Something went wrong'));
      });

      test('creates error message with custom id', () {
        final message = ChatMessage.error(
          message: 'Error',
          id: 'error-id',
        );

        expect(message.id, equals('error-id'));
      });
    });

    group('toolCall factory', () {
      test('creates tool call message', () {
        final message = ChatMessage.toolCall(
          toolCalls: [
            const ToolCallInfo(id: 'tc1', name: 'search'),
          ],
        );

        expect(message.user, equals(ChatUser.assistant));
        expect(message.type, equals(MessageType.toolCall));
        expect(message.toolCalls, hasLength(1));
        expect(message.toolCalls!.first.name, equals('search'));
      });
    });

    group('genUi factory', () {
      test('creates genUi message', () {
        final message = ChatMessage.genUi(
          widgetName: 'Chart',
          data: {'value': 42},
        );

        expect(message.user, equals(ChatUser.assistant));
        expect(message.type, equals(MessageType.genUi));
        expect(message.data!['widget_name'], equals('Chart'));
        expect(message.data!['value'], equals(42));
      });
    });

    group('copyWith', () {
      test('creates copy with modified text', () {
        final original = ChatMessage.text(
          user: ChatUser.user,
          text: 'Original',
        );

        final copy = original.copyWith(text: 'Modified');

        expect(copy.text, equals('Modified'));
        expect(copy.user, equals(original.user));
        expect(copy.id, equals(original.id));
      });

      test('creates copy with modified streaming', () {
        final original = ChatMessage.text(
          user: ChatUser.assistant,
          text: 'Test',
          isStreaming: true,
        );

        final copy = original.copyWith(isStreaming: false);

        expect(copy.isStreaming, isFalse);
        expect(copy.text, equals(original.text));
      });

      test('creates copy with thinking text', () {
        final original = ChatMessage.text(
          user: ChatUser.assistant,
          text: 'Response',
        );

        final copy = original.copyWith(
          thinkingText: 'Thinking...',
          isThinkingStreaming: true,
        );

        expect(copy.thinkingText, equals('Thinking...'));
        expect(copy.isThinkingStreaming, isTrue);
      });

      test('creates copy with tool calls', () {
        final original = ChatMessage.text(
          user: ChatUser.assistant,
          text: 'Test',
        );

        final copy = original.copyWith(
          toolCalls: [const ToolCallInfo(id: 'tc1', name: 'search')],
        );

        expect(copy.toolCalls, hasLength(1));
      });
    });

    group('equality', () {
      test('equal by id', () {
        final msg1 = ChatMessage.text(
          id: 'same-id',
          user: ChatUser.user,
          text: 'Hello',
        );
        final msg2 = ChatMessage.text(
          id: 'same-id',
          user: ChatUser.assistant,
          text: 'Different',
        );

        expect(msg1, equals(msg2));
      });

      test('not equal with different id', () {
        final msg1 = ChatMessage.text(
          id: 'id1',
          user: ChatUser.user,
          text: 'Hello',
        );
        final msg2 = ChatMessage.text(
          id: 'id2',
          user: ChatUser.user,
          text: 'Hello',
        );

        expect(msg1, isNot(equals(msg2)));
      });
    });

    test('hashCode based on id', () {
      final msg1 = ChatMessage.text(
        id: 'same-id',
        user: ChatUser.user,
        text: 'Hello',
      );
      final msg2 = ChatMessage.text(
        id: 'same-id',
        user: ChatUser.assistant,
        text: 'Different',
      );

      expect(msg1.hashCode, equals(msg2.hashCode));
    });

    test('toString includes type, user, and id', () {
      final message = ChatMessage.text(
        id: 'test-id',
        user: ChatUser.user,
        text: 'Hello',
      );

      final str = message.toString();

      expect(str, contains('test-id'));
      expect(str, contains('text'));
      expect(str, contains('user'));
    });
  });

  group('ToolCallInfo', () {
    test('creates with required fields', () {
      const info = ToolCallInfo(id: 'tc1', name: 'search');

      expect(info.id, equals('tc1'));
      expect(info.name, equals('search'));
      expect(info.arguments, isNull);
      expect(info.status, equals(ToolCallStatus.pending));
      expect(info.result, isNull);
    });

    test('creates with all fields', () {
      final now = DateTime.now();
      final info = ToolCallInfo(
        id: 'tc1',
        name: 'search',
        arguments: '{"query": "test"}',
        status: ToolCallStatus.completed,
        result: '{"results": []}',
        startedAt: now,
        completedAt: now,
      );

      expect(info.arguments, equals('{"query": "test"}'));
      expect(info.status, equals(ToolCallStatus.completed));
      expect(info.result, equals('{"results": []}'));
      expect(info.startedAt, equals(now));
      expect(info.completedAt, equals(now));
    });

    test('copyWith creates modified copy', () {
      const original = ToolCallInfo(id: 'tc1', name: 'search');

      final copy = original.copyWith(
        status: ToolCallStatus.executing,
        result: 'done',
      );

      expect(copy.id, equals('tc1'));
      expect(copy.name, equals('search'));
      expect(copy.status, equals(ToolCallStatus.executing));
      expect(copy.result, equals('done'));
    });

    test('toString includes key fields', () {
      const info = ToolCallInfo(
        id: 'tc1',
        name: 'search',
        status: ToolCallStatus.executing,
      );

      final str = info.toString();

      expect(str, contains('tc1'));
      expect(str, contains('search'));
      expect(str, contains('executing'));
    });
  });

  group('ChatUser', () {
    test('has expected values', () {
      expect(ChatUser.values, contains(ChatUser.user));
      expect(ChatUser.values, contains(ChatUser.assistant));
      expect(ChatUser.values, contains(ChatUser.system));
    });
  });

  group('MessageType', () {
    test('has expected values', () {
      expect(MessageType.values, contains(MessageType.text));
      expect(MessageType.values, contains(MessageType.error));
      expect(MessageType.values, contains(MessageType.toolCall));
      expect(MessageType.values, contains(MessageType.genUi));
      expect(MessageType.values, contains(MessageType.loading));
    });
  });

  group('ToolCallStatus', () {
    test('has expected values', () {
      expect(ToolCallStatus.values, contains(ToolCallStatus.pending));
      expect(ToolCallStatus.values, contains(ToolCallStatus.executing));
      expect(ToolCallStatus.values, contains(ToolCallStatus.completed));
      expect(ToolCallStatus.values, contains(ToolCallStatus.failed));
    });
  });
}
