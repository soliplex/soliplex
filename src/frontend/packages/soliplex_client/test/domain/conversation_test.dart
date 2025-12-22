import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('Conversation', () {
    late Conversation conversation;

    setUp(() {
      conversation = Conversation.empty(threadId: 'thread-1');
    });

    test('empty creates conversation with defaults', () {
      expect(conversation.threadId, 'thread-1');
      expect(conversation.messages, isEmpty);
      expect(conversation.toolCalls, isEmpty);
      expect(conversation.streamingText, isNull);
      expect(conversation.streamingMessageId, isNull);
      expect(conversation.status, isA<Idle>());
    });

    group('withAppendedMessage', () {
      test('adds message to empty conversation', () {
        final message = TextMessage.create(
          id: 'msg-1',
          user: ChatUser.user,
          text: 'Hello',
        );

        final updated = conversation.withAppendedMessage(message);

        expect(updated.messages, hasLength(1));
        expect(updated.messages.first, message);
        expect(updated.threadId, conversation.threadId);
      });

      test('preserves existing messages', () {
        final message1 = TextMessage.create(
          id: 'msg-1',
          user: ChatUser.user,
          text: 'Hello',
        );
        final message2 = TextMessage.create(
          id: 'msg-2',
          user: ChatUser.assistant,
          text: 'Hi there',
        );

        final updated = conversation
            .withAppendedMessage(message1)
            .withAppendedMessage(message2);

        expect(updated.messages, hasLength(2));
        expect(updated.messages[0], message1);
        expect(updated.messages[1], message2);
      });
    });

    group('withStreamingText', () {
      test('sets streaming text and message id', () {
        final updated = conversation.withStreamingText('Hello', 'msg-1');

        expect(updated.streamingText, 'Hello');
        expect(updated.streamingMessageId, 'msg-1');
      });

      test('clears streaming when text is null', () {
        final streaming = conversation.withStreamingText('Hello', 'msg-1');
        final cleared = streaming.withStreamingText(null, null);

        expect(cleared.streamingText, isNull);
        expect(cleared.streamingMessageId, isNull);
      });

      test('appends to existing streaming text', () {
        final updated = conversation
            .withStreamingText('Hello', 'msg-1')
            .withStreamingText('Hello world', 'msg-1');

        expect(updated.streamingText, 'Hello world');
        expect(updated.streamingMessageId, 'msg-1');
      });
    });

    group('withToolCall', () {
      test('adds tool call to empty list', () {
        const toolCall = ToolCallInfo(id: 'tool-1', name: 'search');

        final updated = conversation.withToolCall(toolCall);

        expect(updated.toolCalls, hasLength(1));
        expect(updated.toolCalls.first, toolCall);
      });

      test('preserves existing tool calls', () {
        const toolCall1 = ToolCallInfo(id: 'tool-1', name: 'search');
        const toolCall2 = ToolCallInfo(id: 'tool-2', name: 'read');

        final updated =
            conversation.withToolCall(toolCall1).withToolCall(toolCall2);

        expect(updated.toolCalls, hasLength(2));
      });
    });

    group('withStatus', () {
      test('changes status to Running', () {
        final updated = conversation.withStatus(const Running(runId: 'run-1'));

        expect(updated.status, isA<Running>());
        expect((updated.status as Running).runId, 'run-1');
      });

      test('changes status to Completed', () {
        final running = conversation.withStatus(const Running(runId: 'run-1'));
        final completed = running.withStatus(const Completed());

        expect(completed.status, isA<Completed>());
      });

      test('changes status to Failed', () {
        final updated =
            conversation.withStatus(const Failed(error: 'Network error'));

        expect(updated.status, isA<Failed>());
        expect((updated.status as Failed).error, 'Network error');
      });

      test('changes status to Cancelled', () {
        final updated =
            conversation.withStatus(const Cancelled(reason: 'User cancelled'));

        expect(updated.status, isA<Cancelled>());
        expect((updated.status as Cancelled).reason, 'User cancelled');
      });
    });

    group('copyWith', () {
      test('creates copy with modified fields', () {
        final updated = conversation.copyWith(
          streamingText: 'test',
          streamingMessageId: 'msg-1',
        );

        expect(updated.threadId, conversation.threadId);
        expect(updated.streamingText, 'test');
        expect(updated.streamingMessageId, 'msg-1');
      });

      test('preserves unmodified fields', () {
        final withMessage = conversation.withAppendedMessage(
          TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hi'),
        );
        final updated = withMessage.copyWith(streamingText: 'test');

        expect(updated.messages, hasLength(1));
      });
    });

    group('equality', () {
      test('conversations with same threadId are equal', () {
        final other = Conversation.empty(threadId: 'thread-1');
        expect(conversation, equals(other));
      });

      test('conversations with different threadId are not equal', () {
        final other = Conversation.empty(threadId: 'thread-2');
        expect(conversation, isNot(equals(other)));
      });
    });
  });

  group('ConversationStatus', () {
    test('Idle is default status', () {
      const status = Idle();
      expect(status, isA<ConversationStatus>());
    });

    test('Running contains runId', () {
      const status = Running(runId: 'run-123');
      expect(status.runId, 'run-123');
    });

    test('Failed contains error message', () {
      const status = Failed(error: 'Something went wrong');
      expect(status.error, 'Something went wrong');
    });

    test('Cancelled contains reason', () {
      const status = Cancelled(reason: 'User requested');
      expect(status.reason, 'User requested');
    });

    test('Completed has no additional fields', () {
      const status = Completed();
      expect(status, isA<ConversationStatus>());
    });
  });
}
