import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('TextMessage', () {
    test('create with required fields', () {
      final message = TextMessage.create(user: ChatUser.user, text: 'Hello');

      expect(message.user, equals(ChatUser.user));
      expect(message.text, equals('Hello'));
      expect(message.isStreaming, isFalse);
      expect(message.id, isNotEmpty);
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
      final original =
          TextMessage.create(user: ChatUser.user, text: 'Original');
      final copy = original.copyWith(text: 'Modified');

      expect(copy.text, equals('Modified'));
      expect(copy.user, equals(original.user));
      expect(copy.id, equals(original.id));
    });

    test('copyWith modifies streaming', () {
      final original = TextMessage.create(
        user: ChatUser.assistant,
        text: 'Test',
        isStreaming: true,
      );
      final copy = original.copyWith(isStreaming: false);

      expect(copy.isStreaming, isFalse);
      expect(copy.text, equals(original.text));
    });

    test('copyWith modifies thinking text', () {
      final original =
          TextMessage.create(user: ChatUser.assistant, text: 'Response');
      final copy = original.copyWith(
        thinkingText: 'Thinking...',
        isThinkingStreaming: true,
      );

      expect(copy.thinkingText, equals('Thinking...'));
      expect(copy.isThinkingStreaming, isTrue);
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
  });

  group('ErrorMessage', () {
    test('create with message', () {
      final message = ErrorMessage.create(message: 'Something went wrong');

      expect(message.user, equals(ChatUser.system));
      expect(message.errorText, equals('Something went wrong'));
      expect(message.id, isNotEmpty);
    });

    test('create with custom id', () {
      final message = ErrorMessage.create(message: 'Error', id: 'error-id');

      expect(message.id, equals('error-id'));
    });

    test('equality by id', () {
      final msg1 = ErrorMessage.create(id: 'same-id', message: 'Error 1');
      final msg2 = ErrorMessage.create(id: 'same-id', message: 'Error 2');

      expect(msg1, equals(msg2));
    });
  });

  group('ToolCallMessage', () {
    test('create with tool calls', () {
      final message = ToolCallMessage.create(
        toolCalls: const [ToolCallInfo(id: 'tc1', name: 'search')],
      );

      expect(message.user, equals(ChatUser.assistant));
      expect(message.toolCalls, hasLength(1));
      expect(message.toolCalls.first.name, equals('search'));
      expect(message.id, isNotEmpty);
    });

    test('create with custom id', () {
      final message = ToolCallMessage.create(
        toolCalls: const [ToolCallInfo(id: 'tc1', name: 'search')],
        id: 'tc-msg-id',
      );

      expect(message.id, equals('tc-msg-id'));
    });
  });

  group('GenUiMessage', () {
    test('create with widget and data', () {
      final message = GenUiMessage.create(
        widgetName: 'Chart',
        data: const {'value': 42},
      );

      expect(message.user, equals(ChatUser.assistant));
      expect(message.widgetName, equals('Chart'));
      expect(message.data['value'], equals(42));
      expect(message.id, isNotEmpty);
    });

    test('create with custom id', () {
      final message = GenUiMessage.create(
        widgetName: 'Chart',
        data: const {'value': 42},
        id: 'genui-id',
      );

      expect(message.id, equals('genui-id'));
    });
  });

  group('LoadingMessage', () {
    test('create', () {
      final message = LoadingMessage.create();

      expect(message.user, equals(ChatUser.assistant));
      expect(message.id, isNotEmpty);
    });

    test('create with custom id', () {
      final message = LoadingMessage.create(id: 'loading-id');

      expect(message.id, equals('loading-id'));
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
        TextMessage.create(user: ChatUser.user, text: 'Hello'),
        ErrorMessage.create(message: 'Error'),
        ToolCallMessage.create(
          toolCalls: const [ToolCallInfo(id: 'tc1', name: 'tool')],
        ),
        GenUiMessage.create(widgetName: 'Widget', data: const {}),
        LoadingMessage.create(),
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
      final textMsg = TextMessage.create(user: ChatUser.user, text: 'Hello');
      final errorMsg = ErrorMessage.create(message: 'Error occurred');

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
