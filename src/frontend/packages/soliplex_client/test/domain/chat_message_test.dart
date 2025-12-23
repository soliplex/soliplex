import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('TextMessage', () {
    test('create with required fields', () {
      final message = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.user,
        text: 'Hello',
      );

      expect(message.user, equals(ChatUser.user));
      expect(message.text, equals('Hello'));
      expect(message.isStreaming, isFalse);
      expect(message.id, equals('msg-1'));
      expect(message.createdAt, isNotNull);
    });

    test('create with all fields', () {
      final message = TextMessage.create(
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

    test('copyWith modifies text', () {
      final original = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.user,
        text: 'Original',
      );
      final copy = original.copyWith(text: 'Modified');

      expect(copy.text, equals('Modified'));
      expect(copy.user, equals(original.user));
      expect(copy.id, equals(original.id));
    });

    test('copyWith modifies streaming', () {
      final original = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.assistant,
        text: 'Test',
        isStreaming: true,
      );
      final copy = original.copyWith(isStreaming: false);

      expect(copy.isStreaming, isFalse);
      expect(copy.text, equals(original.text));
    });

    test('copyWith modifies thinking text', () {
      final original = TextMessage.create(
        id: 'msg-1',
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

    test('copyWith modifies id', () {
      final original =
          TextMessage.create(id: 'old-id', user: ChatUser.user, text: 'Hello');
      final copy = original.copyWith(id: 'new-id');

      expect(copy.id, equals('new-id'));
      expect(copy.text, equals(original.text));
      expect(copy.user, equals(original.user));
    });

    test('copyWith modifies user', () {
      final original = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.user,
        text: 'Hello',
      );
      final copy = original.copyWith(user: ChatUser.assistant);

      expect(copy.user, equals(ChatUser.assistant));
      expect(copy.text, equals(original.text));
    });

    test('copyWith modifies createdAt', () {
      final original = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.user,
        text: 'Hello',
      );
      final newTime = DateTime(2025, 6, 15);
      final copy = original.copyWith(createdAt: newTime);

      expect(copy.createdAt, equals(newTime));
      expect(copy.text, equals(original.text));
    });

    test('equality by id', () {
      final msg1 =
          TextMessage.create(id: 'same-id', user: ChatUser.user, text: 'Hello');
      final msg2 = TextMessage.create(
        id: 'same-id',
        user: ChatUser.assistant,
        text: 'Different',
      );

      expect(msg1, equals(msg2));
    });

    test('not equal with different id', () {
      final msg1 =
          TextMessage.create(id: 'id1', user: ChatUser.user, text: 'Hello');
      final msg2 =
          TextMessage.create(id: 'id2', user: ChatUser.user, text: 'Hello');

      expect(msg1, isNot(equals(msg2)));
    });

    test('hashCode based on id', () {
      final msg1 =
          TextMessage.create(id: 'same-id', user: ChatUser.user, text: 'Hello');
      final msg2 = TextMessage.create(
        id: 'same-id',
        user: ChatUser.assistant,
        text: 'Different',
      );

      expect(msg1.hashCode, equals(msg2.hashCode));
    });

    test('toString includes id and user', () {
      final message =
          TextMessage.create(id: 'test-id', user: ChatUser.user, text: 'Hello');
      final str = message.toString();

      expect(str, contains('test-id'));
      expect(str, contains('user'));
    });

    test('hasThinkingText returns true when thinking text is present', () {
      final message = TextMessage(
        id: 'test-id',
        user: ChatUser.assistant,
        createdAt: DateTime.now(),
        text: 'Response',
        thinkingText: 'I am thinking...',
      );

      expect(message.hasThinkingText, isTrue);
    });

    test('hasThinkingText returns false when thinking text is empty', () {
      final message = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.assistant,
        text: 'Response',
      );

      expect(message.hasThinkingText, isFalse);
    });
  });

  group('ErrorMessage', () {
    test('create with message', () {
      final message = ErrorMessage.create(
        id: 'error-1',
        message: 'Something went wrong',
      );

      expect(message.user, equals(ChatUser.system));
      expect(message.errorText, equals('Something went wrong'));
      expect(message.id, equals('error-1'));
    });

    test('create with custom id', () {
      final message = ErrorMessage.create(id: 'error-id', message: 'Error');

      expect(message.id, equals('error-id'));
    });

    test('equality by id', () {
      final msg1 = ErrorMessage.create(id: 'same-id', message: 'Error 1');
      final msg2 = ErrorMessage.create(id: 'same-id', message: 'Error 2');

      expect(msg1, equals(msg2));
    });

    test('toString includes id and error', () {
      final message = ErrorMessage.create(
        id: 'error-id',
        message: 'Test error',
      );
      final str = message.toString();

      expect(str, contains('error-id'));
      expect(str, contains('Test error'));
    });
  });

  group('ToolCallMessage', () {
    test('create with tool calls', () {
      final message = ToolCallMessage.create(
        id: 'tc-msg-1',
        toolCalls: const [ToolCallInfo(id: 'tc1', name: 'search')],
      );

      expect(message.user, equals(ChatUser.assistant));
      expect(message.toolCalls, hasLength(1));
      expect(message.toolCalls.first.name, equals('search'));
      expect(message.id, equals('tc-msg-1'));
    });

    test('create with custom id', () {
      final message = ToolCallMessage.create(
        id: 'tc-msg-id',
        toolCalls: const [ToolCallInfo(id: 'tc1', name: 'search')],
      );

      expect(message.id, equals('tc-msg-id'));
    });

    test('toString includes id and call count', () {
      final message = ToolCallMessage.create(
        id: 'tc-msg-id',
        toolCalls: const [
          ToolCallInfo(id: 'tc1', name: 'search'),
          ToolCallInfo(id: 'tc2', name: 'read'),
        ],
      );
      final str = message.toString();

      expect(str, contains('tc-msg-id'));
      expect(str, contains('2'));
    });
  });

  group('GenUiMessage', () {
    test('create with widget and data', () {
      final message = GenUiMessage.create(
        id: 'genui-1',
        widgetName: 'Chart',
        data: const {'value': 42},
      );

      expect(message.user, equals(ChatUser.assistant));
      expect(message.widgetName, equals('Chart'));
      expect(message.data['value'], equals(42));
      expect(message.id, equals('genui-1'));
    });

    test('create with custom id', () {
      final message = GenUiMessage.create(
        id: 'genui-id',
        widgetName: 'Chart',
        data: const {'value': 42},
      );

      expect(message.id, equals('genui-id'));
    });

    test('toString includes id and widget name', () {
      final message = GenUiMessage.create(
        id: 'genui-id',
        widgetName: 'Chart',
        data: const {'value': 42},
      );
      final str = message.toString();

      expect(str, contains('genui-id'));
      expect(str, contains('Chart'));
    });
  });

  group('LoadingMessage', () {
    test('create', () {
      final message = LoadingMessage.create(id: 'loading-1');

      expect(message.user, equals(ChatUser.assistant));
      expect(message.id, equals('loading-1'));
    });

    test('create with custom id', () {
      final message = LoadingMessage.create(id: 'loading-id');

      expect(message.id, equals('loading-id'));
    });

    test('toString includes id', () {
      final message = LoadingMessage.create(id: 'loading-id');
      final str = message.toString();

      expect(str, contains('loading-id'));
    });
  });

  group('ChatMessage sealed class', () {
    test('different message types with same id are not equal', () {
      final textMsg =
          TextMessage.create(id: 'same-id', user: ChatUser.user, text: 'Hello');
      final errorMsg = ErrorMessage.create(id: 'same-id', message: 'Error');
      final loadingMsg = LoadingMessage.create(id: 'same-id');

      expect(textMsg, isNot(equals(errorMsg)));
      expect(textMsg, isNot(equals(loadingMsg)));
      expect(errorMsg, isNot(equals(loadingMsg)));
    });

    test('pattern matching on message types', () {
      final messages = <ChatMessage>[
        TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hello'),
        ErrorMessage.create(id: 'err-1', message: 'Error'),
        ToolCallMessage.create(
          id: 'tc-1',
          toolCalls: const [ToolCallInfo(id: 'tc1', name: 'tool')],
        ),
        GenUiMessage.create(
          id: 'genui-1',
          widgetName: 'Widget',
          data: const {},
        ),
        LoadingMessage.create(id: 'loading-1'),
      ];

      final types = messages.map((m) {
        return switch (m) {
          TextMessage() => 'text',
          ErrorMessage() => 'error',
          ToolCallMessage() => 'toolCall',
          GenUiMessage() => 'genUi',
          LoadingMessage() => 'loading',
        };
      }).toList();

      expect(types, equals(['text', 'error', 'toolCall', 'genUi', 'loading']));
    });

    test('extract text from different message types', () {
      final textMsg =
          TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hello');
      final errorMsg =
          ErrorMessage.create(id: 'err-1', message: 'Error occurred');

      String getText(ChatMessage msg) {
        return switch (msg) {
          TextMessage(:final text) => text,
          ErrorMessage(:final errorText) => errorText,
          _ => '',
        };
      }

      expect(getText(textMsg), equals('Hello'));
      expect(getText(errorMsg), equals('Error occurred'));
    });
  });

  group('ToolCallInfo', () {
    test('creates with required fields', () {
      const info = ToolCallInfo(id: 'tc1', name: 'search');

      expect(info.id, equals('tc1'));
      expect(info.name, equals('search'));
      expect(info.arguments, isEmpty);
      expect(info.status, equals(ToolCallStatus.pending));
      expect(info.result, isEmpty);
    });

    test('creates with all fields', () {
      const info = ToolCallInfo(
        id: 'tc1',
        name: 'search',
        arguments: '{"query": "test"}',
        status: ToolCallStatus.completed,
        result: '{"results": []}',
      );

      expect(info.arguments, equals('{"query": "test"}'));
      expect(info.status, equals(ToolCallStatus.completed));
      expect(info.result, equals('{"results": []}'));
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

    test('copyWith preserves status and result when not passed', () {
      const original = ToolCallInfo(
        id: 'tc1',
        name: 'search',
        status: ToolCallStatus.completed,
        result: 'done',
      );
      final copy = original.copyWith(name: 'new-search');

      expect(copy.status, equals(ToolCallStatus.completed));
      expect(copy.result, equals('done'));
    });

    test('copyWith with all fields', () {
      const original = ToolCallInfo(id: 'tc1', name: 'search');
      final copy = original.copyWith(
        id: 'tc2',
        name: 'new-tool',
        arguments: '{"arg": 1}',
        status: ToolCallStatus.completed,
        result: 'result',
      );

      expect(copy.id, equals('tc2'));
      expect(copy.name, equals('new-tool'));
      expect(copy.arguments, equals('{"arg": 1}'));
      expect(copy.status, equals(ToolCallStatus.completed));
      expect(copy.result, equals('result'));
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

    test('equality by id', () {
      const info1 = ToolCallInfo(id: 'tc1', name: 'search');
      const info2 = ToolCallInfo(
        id: 'tc1',
        name: 'different',
        status: ToolCallStatus.completed,
      );

      expect(info1, equals(info2));
    });

    test('not equal with different id', () {
      const info1 = ToolCallInfo(id: 'tc1', name: 'search');
      const info2 = ToolCallInfo(id: 'tc2', name: 'search');

      expect(info1, isNot(equals(info2)));
    });

    test('hashCode based on id', () {
      const info1 = ToolCallInfo(id: 'tc1', name: 'search');
      const info2 = ToolCallInfo(
        id: 'tc1',
        name: 'different',
        status: ToolCallStatus.completed,
      );

      expect(info1.hashCode, equals(info2.hashCode));
    });

    test('hasArguments returns true when arguments are present', () {
      const info = ToolCallInfo(
        id: 'tc1',
        name: 'search',
        arguments: '{"query": "test"}',
      );

      expect(info.hasArguments, isTrue);
    });

    test('hasArguments returns false when arguments are empty', () {
      const info = ToolCallInfo(id: 'tc1', name: 'search');

      expect(info.hasArguments, isFalse);
    });

    test('hasResult returns true when result is present', () {
      const info = ToolCallInfo(
        id: 'tc1',
        name: 'search',
        result: '{"data": []}',
      );

      expect(info.hasResult, isTrue);
    });

    test('hasResult returns false when result is empty', () {
      const info = ToolCallInfo(id: 'tc1', name: 'search');

      expect(info.hasResult, isFalse);
    });
  });

  group('ChatUser', () {
    test('has expected values', () {
      expect(ChatUser.values, contains(ChatUser.user));
      expect(ChatUser.values, contains(ChatUser.assistant));
      expect(ChatUser.values, contains(ChatUser.system));
      expect(ChatUser.values, hasLength(3));
    });
  });

  group('ToolCallStatus', () {
    test('has expected values', () {
      expect(ToolCallStatus.values, contains(ToolCallStatus.pending));
      expect(ToolCallStatus.values, contains(ToolCallStatus.executing));
      expect(ToolCallStatus.values, contains(ToolCallStatus.completed));
      expect(ToolCallStatus.values, contains(ToolCallStatus.failed));
      expect(ToolCallStatus.values, hasLength(4));
    });
  });
}
