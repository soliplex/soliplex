import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';

void main() {
  group('RunContext', () {
    test('empty creates context with empty collections', () {
      const context = RunContext.empty;

      expect(context.messages, isEmpty);
      expect(context.rawEvents, isEmpty);
      expect(context.state, isEmpty);
      expect(context.activeToolCalls, isEmpty);
    });

    test('copyWith creates new instance with updated fields', () {
      const original = RunContext.empty;
      final message = TextMessage.create(
        id: 'msg-1',
        user: ChatUser.user,
        text: 'Hello',
      );

      final updated = original.copyWith(
        messages: [message],
      );

      expect(updated.messages, [message]);
      expect(updated.rawEvents, isEmpty);
      expect(original.messages, isEmpty);
    });

    test('equality based on all fields', () {
      const context1 = RunContext.empty;
      const context2 = RunContext.empty;
      final context3 = RunContext(
        messages: [
          TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hi'),
        ],
      );

      expect(context1, equals(context2));
      expect(context1, isNot(equals(context3)));
    });
  });

  group('TextStreaming', () {
    test('NotStreaming instances are equal', () {
      const streaming1 = NotStreaming();
      const streaming2 = NotStreaming();

      expect(streaming1, equals(streaming2));
    });

    test('Streaming equality based on messageId and text', () {
      const streaming1 = Streaming(messageId: 'msg-1', text: 'Hello');
      const streaming2 = Streaming(messageId: 'msg-1', text: 'Hello');
      const streaming3 = Streaming(messageId: 'msg-2', text: 'Hello');
      const streaming4 = Streaming(messageId: 'msg-1', text: 'World');

      expect(streaming1, equals(streaming2));
      expect(streaming1, isNot(equals(streaming3)));
      expect(streaming1, isNot(equals(streaming4)));
    });

    test('NotStreaming is not equal to Streaming', () {
      const notStreaming = NotStreaming();
      const streaming = Streaming(messageId: 'msg-1', text: 'Hello');

      expect(notStreaming, isNot(equals(streaming)));
    });
  });

  group('ActiveRunState', () {
    group('IdleState', () {
      test('creates with empty context by default', () {
        const state = IdleState();

        expect(state.context, equals(RunContext.empty));
        expect(state.messages, isEmpty);
        expect(state.isRunning, isFalse);
      });

      test('creates with provided context', () {
        final message = TextMessage.create(
          id: 'msg-1',
          user: ChatUser.user,
          text: 'Previous message',
        );
        final context = RunContext(messages: [message]);

        final state = IdleState(context: context);

        expect(state.messages, [message]);
      });

      test('equality based on context', () {
        const state1 = IdleState();
        const state2 = IdleState();
        final state3 = IdleState(
          context: RunContext(
            messages: [
              TextMessage.create(id: 'msg-1', user: ChatUser.user, text: 'Hi'),
            ],
          ),
        );

        expect(state1, equals(state2));
        expect(state1, isNot(equals(state3)));
      });
    });

    group('RunningState', () {
      test('creates with required fields', () {
        const state = RunningState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
        );

        expect(state.threadId, 'thread-1');
        expect(state.runId, 'run-1');
        expect(state.textStreaming, isA<NotStreaming>());
        expect(state.isRunning, isTrue);
        expect(state.isTextStreaming, isFalse);
      });

      test('isTextStreaming returns true when streaming', () {
        const state = RunningState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          textStreaming: Streaming(messageId: 'msg-1', text: 'Hello'),
        );

        expect(state.isTextStreaming, isTrue);
      });

      test('copyWith creates new instance with updated fields', () {
        const original = RunningState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
        );

        final updated = original.copyWith(
          textStreaming: const Streaming(messageId: 'msg-1', text: 'Hi'),
        );

        expect(updated.textStreaming, isA<Streaming>());
        expect(original.textStreaming, isA<NotStreaming>());
        expect(updated.threadId, 'thread-1');
      });

      test('equality based on all fields', () {
        const state1 = RunningState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
        );
        const state2 = RunningState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
        );
        const state3 = RunningState(
          threadId: 'thread-2',
          runId: 'run-1',
          context: RunContext.empty,
        );

        expect(state1, equals(state2));
        expect(state1, isNot(equals(state3)));
      });
    });

    group('CompletedState', () {
      test('creates with Success result', () {
        const state = CompletedState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          result: Success(),
        );

        expect(state.result, isA<Success>());
        expect(state.isRunning, isFalse);
      });

      test('creates with Failed result', () {
        const state = CompletedState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          result: Failed(errorMessage: 'Something went wrong'),
        );

        expect(state.result, isA<Failed>());
        expect((state.result as Failed).errorMessage, 'Something went wrong');
      });

      test('creates with Cancelled result', () {
        const state = CompletedState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          result: Cancelled(reason: 'User cancelled'),
        );

        expect(state.result, isA<Cancelled>());
        expect((state.result as Cancelled).reason, 'User cancelled');
      });

      test('equality based on all fields including result', () {
        const state1 = CompletedState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          result: Success(),
        );
        const state2 = CompletedState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          result: Success(),
        );
        const state3 = CompletedState(
          threadId: 'thread-1',
          runId: 'run-1',
          context: RunContext.empty,
          result: Failed(errorMessage: 'Error'),
        );

        expect(state1, equals(state2));
        expect(state1, isNot(equals(state3)));
      });
    });

    group('pattern matching', () {
      test('exhaustive switch on ActiveRunState', () {
        const states = <ActiveRunState>[
          IdleState(),
          RunningState(
            threadId: 't',
            runId: 'r',
            context: RunContext.empty,
          ),
          CompletedState(
            threadId: 't',
            runId: 'r',
            context: RunContext.empty,
            result: Success(),
          ),
        ];

        for (final state in states) {
          final description = switch (state) {
            IdleState() => 'idle',
            RunningState() => 'running',
            CompletedState() => 'completed',
          };
          expect(description, isNotEmpty);
        }
      });

      test('pattern matching on CompletedState result', () {
        const results = <CompletionResult>[
          Success(),
          Failed(errorMessage: 'Error'),
          Cancelled(reason: 'Cancelled'),
        ];

        for (final result in results) {
          final description = switch (result) {
            Success() => 'success',
            Failed(:final errorMessage) => 'failed: $errorMessage',
            Cancelled(:final reason) => 'cancelled: $reason',
          };
          expect(description, isNotEmpty);
        }
      });

      test('nested pattern matching for error handling', () {
        const state = CompletedState(
          threadId: 't',
          runId: 'r',
          context: RunContext.empty,
          result: Failed(errorMessage: 'Network error'),
        );

        final errorMessage = switch (state) {
          CompletedState(result: Failed(:final errorMessage)) => errorMessage,
          _ => null,
        };

        expect(errorMessage, 'Network error');
      });
    });

    group('different state types are not equal', () {
      test('IdleState is not equal to RunningState', () {
        const idle = IdleState();
        const running = RunningState(
          threadId: 't',
          runId: 'r',
          context: RunContext.empty,
        );

        expect(idle, isNot(equals(running)));
      });

      test('RunningState is not equal to CompletedState', () {
        const running = RunningState(
          threadId: 't',
          runId: 'r',
          context: RunContext.empty,
        );
        const completed = CompletedState(
          threadId: 't',
          runId: 'r',
          context: RunContext.empty,
          result: Success(),
        );

        expect(running, isNot(equals(completed)));
      });
    });
  });

  group('CompletionResult', () {
    test('Success instances are equal', () {
      const success1 = Success();
      const success2 = Success();

      expect(success1, equals(success2));
    });

    test('Failed equality based on errorMessage', () {
      const failed1 = Failed(errorMessage: 'Error A');
      const failed2 = Failed(errorMessage: 'Error A');
      const failed3 = Failed(errorMessage: 'Error B');

      expect(failed1, equals(failed2));
      expect(failed1, isNot(equals(failed3)));
    });

    test('Cancelled equality based on reason', () {
      const cancelled1 = Cancelled(reason: 'Reason A');
      const cancelled2 = Cancelled(reason: 'Reason A');
      const cancelled3 = Cancelled(reason: 'Reason B');

      expect(cancelled1, equals(cancelled2));
      expect(cancelled1, isNot(equals(cancelled3)));
    });

    test('different result types are not equal', () {
      const success = Success();
      const failed = Failed(errorMessage: 'Error');
      const cancelled = Cancelled(reason: 'Reason');

      expect(success, isNot(equals(failed)));
      expect(success, isNot(equals(cancelled)));
      expect(failed, isNot(equals(cancelled)));
    });
  });
}
