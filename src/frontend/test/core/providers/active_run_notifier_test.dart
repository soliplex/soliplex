import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('ActiveRunNotifier', () {
    group('initial state', () {
      test('starts in IdleState', () {
        final notifier = createTestActiveRunNotifier();
        addTearDown(notifier.dispose);

        expect(notifier.state, isA<IdleState>());
      });

      test('isRunning is false initially', () {
        final notifier = createTestActiveRunNotifier();
        addTearDown(notifier.dispose);

        expect(notifier.state.isRunning, isFalse);
      });
    });

    group('reset', () {
      test('returns to IdleState', () {
        final notifier = createTestActiveRunNotifier();
        addTearDown(notifier.dispose);

        notifier.reset();

        expect(notifier.state, isA<IdleState>());
      });

      test('clears context', () {
        final notifier = createTestActiveRunNotifier();
        addTearDown(notifier.dispose);

        notifier.reset();

        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.rawEvents, isEmpty);
      });
    });

    group('state type checks', () {
      test('isRunning returns correct value for each state type', () {
        // IdleState
        expect(const IdleState().isRunning, isFalse);

        // RunningState
        expect(
          const RunningState(
            threadId: 't',
            runId: 'r',
            context: RunContext.empty,
          ).isRunning,
          isTrue,
        );

        // CompletedState with Success
        expect(
          const CompletedState(
            threadId: 't',
            runId: 'r',
            context: RunContext.empty,
            result: Success(),
          ).isRunning,
          isFalse,
        );

        // CompletedState with Failed
        expect(
          const CompletedState(
            threadId: 't',
            runId: 'r',
            context: RunContext.empty,
            result: Failed(errorMessage: 'Error'),
          ).isRunning,
          isFalse,
        );

        // CompletedState with Cancelled
        expect(
          const CompletedState(
            threadId: 't',
            runId: 'r',
            context: RunContext.empty,
            result: Cancelled(reason: 'User cancelled'),
          ).isRunning,
          isFalse,
        );
      });
    });

    group('convenience getters', () {
      test('messages returns context.messages', () {
        final message = TextMessage.create(
          user: ChatUser.user,
          text: 'Hello',
        );
        final state = IdleState(
          context: RunContext(messages: [message]),
        );

        expect(state.messages, [message]);
        expect(state.messages, equals(state.context.messages));
      });

      test('rawEvents returns context.rawEvents', () {
        const state = IdleState();

        expect(state.rawEvents, isEmpty);
        expect(state.rawEvents, equals(state.context.rawEvents));
      });

      test('state getter returns context.state', () {
        const runState = IdleState(
          context: RunContext(state: {'key': 'value'}),
        );

        expect(runState.state, {'key': 'value'});
        expect(runState.state, equals(runState.context.state));
      });

      test('activeToolCalls returns context.activeToolCalls', () {
        const toolCall = ToolCallInfo(id: 'tc-1', name: 'search');
        const state = IdleState(
          context: RunContext(activeToolCalls: [toolCall]),
        );

        expect(state.activeToolCalls, [toolCall]);
        expect(state.activeToolCalls, equals(state.context.activeToolCalls));
      });
    });
  });

  group('NotifierInternalState', () {
    test('IdleInternalState can be created', () {
      const state = IdleInternalState();
      expect(state, isA<NotifierInternalState>());
    });

    test('RunningInternalState holds resources', () {
      final transport = FakeHttpTransport();
      final urlBuilder = FakeUrlBuilder();
      final thread = Thread(
        transport: transport,
        urlBuilder: urlBuilder,
        roomId: 'room-1',
        threadId: 'thread-1',
      );
      final cancelToken = CancelToken();
      final controller = StreamController<AgUiEvent>();

      final state = RunningInternalState(
        thread: thread,
        cancelToken: cancelToken,
        subscription: controller.stream.listen((_) {}),
      );

      expect(state, isA<NotifierInternalState>());
      expect(state.thread, equals(thread));
      expect(state.cancelToken, equals(cancelToken));

      // Cleanup
      controller.close();
      state.dispose();
    });
  });
}
