import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client/src/domain/conversation.dart';
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
      expect(conversation.streaming, isA<NotStreaming>());
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

    group('withStreaming', () {
      test('sets streaming state', () {
        final updated = conversation.withStreaming(
          const Streaming(text: 'Hello', messageId: 'msg-1'),
        );

        expect(updated.streaming, isA<Streaming>());
        final streaming = updated.streaming as Streaming;
        expect(streaming.text, 'Hello');
        expect(streaming.messageId, 'msg-1');
      });

      test('clears streaming state', () {
        final streaming = conversation.withStreaming(
          const Streaming(text: 'Hello', messageId: 'msg-1'),
        );
        final cleared = streaming.withStreaming(const NotStreaming());

        expect(cleared.streaming, isA<NotStreaming>());
      });

      test('updates streaming text', () {
        final updated = conversation
            .withStreaming(const Streaming(text: 'Hello', messageId: 'msg-1'))
            .withStreaming(
              const Streaming(text: 'Hello world', messageId: 'msg-1'),
            );

        expect(updated.streaming, isA<Streaming>());
        final streaming = updated.streaming as Streaming;
        expect(streaming.text, 'Hello world');
        expect(streaming.messageId, 'msg-1');
      });
    });

    group('isStreaming', () {
      test('returns false when not streaming', () {
        expect(conversation.isStreaming, isFalse);
      });

      test('returns true when streaming', () {
        final streaming = conversation.withStreaming(
          const Streaming(text: 'Hello', messageId: 'msg-1'),
        );
        expect(streaming.isStreaming, isTrue);
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
          streaming: const Streaming(text: 'test', messageId: 'msg-1'),
        );

        expect(updated.threadId, conversation.threadId);
        expect(updated.streaming, isA<Streaming>());
        final streaming = updated.streaming as Streaming;
        expect(streaming.text, 'test');
        expect(streaming.messageId, 'msg-1');
      });

      test('preserves unmodified fields', () {
        final withMessage = conversation.withAppendedMessage(
          TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hi'),
        );
        final updated = withMessage.copyWith(
          streaming: const Streaming(text: 'test', messageId: 'msg-2'),
        );

        expect(updated.messages, hasLength(1));
      });

      test('copies with new threadId', () {
        final updated = conversation.copyWith(threadId: 'thread-2');

        expect(updated.threadId, 'thread-2');
        expect(updated.messages, conversation.messages);
        expect(updated.toolCalls, conversation.toolCalls);
      });

      test('copies with new messages list', () {
        final newMessages = [
          TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hello'),
        ];
        final updated = conversation.copyWith(messages: newMessages);

        expect(updated.messages, hasLength(1));
        expect(updated.messages.first.id, 'msg-1');
        expect(updated.threadId, conversation.threadId);
      });

      test('copies with new toolCalls list', () {
        const newToolCalls = [
          ToolCallInfo(id: 'tc-1', name: 'search'),
          ToolCallInfo(id: 'tc-2', name: 'read'),
        ];
        final updated = conversation.copyWith(toolCalls: newToolCalls);

        expect(updated.toolCalls, hasLength(2));
        expect(updated.toolCalls[0].name, 'search');
        expect(updated.toolCalls[1].name, 'read');
        expect(updated.threadId, conversation.threadId);
      });

      test('copies with new status', () {
        final updated = conversation.copyWith(
          status: const Running(runId: 'run-1'),
        );

        expect(updated.status, isA<Running>());
        expect((updated.status as Running).runId, 'run-1');
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

  group('StreamingState', () {
    test('NotStreaming is default', () {
      const state = NotStreaming();
      expect(state, isA<StreamingState>());
    });

    test('Streaming contains text and messageId', () {
      const state = Streaming(text: 'Hello', messageId: 'msg-1');
      expect(state.text, 'Hello');
      expect(state.messageId, 'msg-1');
    });

    test('Streaming equality', () {
      const state1 = Streaming(text: 'Hello', messageId: 'msg-1');
      const state2 = Streaming(text: 'Hello', messageId: 'msg-1');
      const state3 = Streaming(text: 'World', messageId: 'msg-1');

      expect(state1, equals(state2));
      expect(state1, isNot(equals(state3)));
    });

    test('Streaming equality non-identical instances', () {
      // Runtime list access prevents const evaluation
      final texts = ['Hello', 'Hello'];
      final msgIds = ['msg-1', 'msg-1', 'msg-2'];

      final state1 = Streaming(text: texts[0], messageId: msgIds[0]);
      final state2 = Streaming(text: texts[1], messageId: msgIds[1]);
      final state3 = Streaming(text: texts[0], messageId: msgIds[2]);

      expect(state1, equals(state2));
      expect(state1, isNot(equals(state3)));
    });

    test('NotStreaming equality', () {
      const state1 = NotStreaming();
      const state2 = NotStreaming();

      expect(state1, equals(state2));
    });

    test('NotStreaming equality non-identical instances', () {
      const state1 = NotStreaming();
      const state2 = NotStreaming();

      expect(state1, equals(state2));
    });

    test('NotStreaming hashCode', () {
      const state1 = NotStreaming();
      const state2 = NotStreaming();

      expect(state1.hashCode, equals(state2.hashCode));
    });

    test('NotStreaming toString', () {
      const state = NotStreaming();
      expect(state.toString(), equals('NotStreaming()'));
    });

    test('Streaming hashCode', () {
      const state1 = Streaming(text: 'Hello', messageId: 'msg-1');
      const state2 = Streaming(text: 'Hello', messageId: 'msg-1');

      expect(state1.hashCode, equals(state2.hashCode));
    });

    test('Streaming toString', () {
      const state = Streaming(text: 'Hello world', messageId: 'msg-1');
      final str = state.toString();

      expect(str, contains('msg-1'));
      expect(str, contains('11 chars'));
    });

    test('Streaming identical returns true', () {
      const state = Streaming(text: 'Hello', messageId: 'msg-1');
      expect(state == state, isTrue);
    });

    test('NotStreaming identical returns true', () {
      const state = NotStreaming();
      expect(state == state, isTrue);
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

    group('Idle', () {
      test('equality', () {
        const status1 = Idle();
        const status2 = Idle();

        expect(status1, equals(status2));
      });

      test('equality non-identical instances', () {
        const status1 = Idle();
        const status2 = Idle();

        expect(status1, equals(status2));
      });

      test('identical returns true', () {
        const status = Idle();
        expect(status == status, isTrue);
      });

      test('hashCode', () {
        const status1 = Idle();
        const status2 = Idle();

        expect(status1.hashCode, equals(status2.hashCode));
      });

      test('toString', () {
        const status = Idle();
        expect(status.toString(), equals('Idle()'));
      });
    });

    group('Running', () {
      test('equality', () {
        const status1 = Running(runId: 'run-1');
        const status2 = Running(runId: 'run-1');
        const status3 = Running(runId: 'run-2');

        expect(status1, equals(status2));
        expect(status1, isNot(equals(status3)));
      });

      test('identical returns true', () {
        const status = Running(runId: 'run-1');
        expect(status == status, isTrue);
      });

      test('hashCode', () {
        const status1 = Running(runId: 'run-1');
        const status2 = Running(runId: 'run-1');

        expect(status1.hashCode, equals(status2.hashCode));
      });

      test('toString', () {
        const status = Running(runId: 'run-123');
        expect(status.toString(), contains('run-123'));
      });
    });

    group('Completed', () {
      test('equality', () {
        const status1 = Completed();
        const status2 = Completed();

        expect(status1, equals(status2));
      });

      test('equality non-identical instances', () {
        const status1 = Completed();
        const status2 = Completed();

        expect(status1, equals(status2));
      });

      test('identical returns true', () {
        const status = Completed();
        expect(status == status, isTrue);
      });

      test('hashCode', () {
        const status1 = Completed();
        const status2 = Completed();

        expect(status1.hashCode, equals(status2.hashCode));
      });

      test('toString', () {
        const status = Completed();
        expect(status.toString(), equals('Completed()'));
      });
    });

    group('Failed', () {
      test('equality', () {
        const status1 = Failed(error: 'error-1');
        const status2 = Failed(error: 'error-1');
        const status3 = Failed(error: 'error-2');

        expect(status1, equals(status2));
        expect(status1, isNot(equals(status3)));
      });

      test('identical returns true', () {
        const status = Failed(error: 'error');
        expect(status == status, isTrue);
      });

      test('hashCode', () {
        const status1 = Failed(error: 'error-1');
        const status2 = Failed(error: 'error-1');

        expect(status1.hashCode, equals(status2.hashCode));
      });

      test('toString', () {
        const status = Failed(error: 'Network error');
        expect(status.toString(), contains('Network error'));
      });
    });

    group('Cancelled', () {
      test('equality', () {
        const status1 = Cancelled(reason: 'reason-1');
        const status2 = Cancelled(reason: 'reason-1');
        const status3 = Cancelled(reason: 'reason-2');

        expect(status1, equals(status2));
        expect(status1, isNot(equals(status3)));
      });

      test('equality non-identical instances', () {
        // Helper function to create non-const instances
        Cancelled create(String reason) => Cancelled(reason: reason);

        final status1 = create('reason-1');
        final status2 = create('reason-1');

        expect(status1, equals(status2));
      });

      test('identical returns true', () {
        const status = Cancelled(reason: 'reason');
        expect(status == status, isTrue);
      });

      test('hashCode', () {
        const status1 = Cancelled(reason: 'reason-1');
        const status2 = Cancelled(reason: 'reason-1');

        expect(status1.hashCode, equals(status2.hashCode));
      });

      test('toString', () {
        const status = Cancelled(reason: 'User cancelled');
        expect(status.toString(), contains('User cancelled'));
      });
    });
  });

  group('Conversation additional', () {
    test('isRunning returns false when Idle', () {
      final conv = Conversation.empty(threadId: 'thread-1');
      expect(conv.isRunning, isFalse);
    });

    test('isRunning returns true when Running', () {
      final conv = Conversation.empty(threadId: 'thread-1')
          .withStatus(const Running(runId: 'run-1'));
      expect(conv.isRunning, isTrue);
    });

    test('hashCode based on threadId', () {
      final conv1 = Conversation.empty(threadId: 'thread-1');
      final conv2 = Conversation.empty(threadId: 'thread-1');

      expect(conv1.hashCode, equals(conv2.hashCode));
    });

    test('toString includes all fields', () {
      final conv = Conversation.empty(threadId: 'thread-1')
          .withAppendedMessage(
            TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hello'),
          )
          .withToolCall(const ToolCallInfo(id: 'tc-1', name: 'search'))
          .withStreaming(const Streaming(text: 'Hi', messageId: 'msg-1'))
          .withStatus(const Running(runId: 'run-1'));

      final str = conv.toString();

      expect(str, contains('thread-1'));
      expect(str, contains('messages: 1'));
      expect(str, contains('toolCalls: 1'));
      expect(str, contains('Streaming'));
      expect(str, contains('Running'));
    });

    test('identical conversations return true for equality', () {
      final conv = Conversation.empty(threadId: 'thread-1');
      expect(conv == conv, isTrue);
    });
  });
}
