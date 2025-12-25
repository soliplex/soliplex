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
      test('preserves unmodified fields', () {
        final withMessage = conversation.withAppendedMessage(
          TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hi'),
        );
        final updated = withMessage.copyWith(
          status: const Running(runId: 'run-1'),
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
          .withStatus(const Running(runId: 'run-1'));

      final str = conv.toString();

      expect(str, contains('thread-1'));
      expect(str, contains('messages: 1'));
      expect(str, contains('toolCalls: 1'));
      expect(str, contains('Running'));
    });

    test('identical conversations return true for equality', () {
      final conv = Conversation.empty(threadId: 'thread-1');
      expect(conv == conv, isTrue);
    });
  });
}
