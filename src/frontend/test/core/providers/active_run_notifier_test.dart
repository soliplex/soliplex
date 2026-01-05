import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client/soliplex_client.dart' as domain
    show Cancelled, Completed, Conversation, Failed, Running;
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  late MockAgUiClient mockAgUiClient;
  late MockSoliplexApi mockApi;

  setUpAll(() {
    registerFallbackValue(
      const SimpleRunAgentInput(messages: []),
    );
    registerFallbackValue(CancelToken());
  });

  setUp(() {
    mockAgUiClient = MockAgUiClient();
    mockApi = MockSoliplexApi();
  });

  group('ActiveRunNotifier', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer(
        overrides: [
          agUiClientProvider.overrideWithValue(mockAgUiClient),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('initial state', () {
      test('starts in IdleState', () {
        final state = container.read(activeRunNotifierProvider);
        expect(state, isA<IdleState>());
      });

      test('isRunning is false initially', () {
        final state = container.read(activeRunNotifierProvider);
        expect(state.isRunning, isFalse);
      });

      test('IdleState has empty sentinel conversation', () {
        final state = container.read(activeRunNotifierProvider);
        expect(state.messages, isEmpty);
        expect(state.conversation.threadId, isEmpty);
      });
    });

    group('reset', () {
      test('returns to IdleState', () {
        container.read(activeRunNotifierProvider.notifier).reset();

        final state = container.read(activeRunNotifierProvider);
        expect(state, isA<IdleState>());
      });

      test('clears messages', () {
        container.read(activeRunNotifierProvider.notifier).reset();

        final state = container.read(activeRunNotifierProvider);
        expect(state.messages, isEmpty);
      });
    });

    group('state type checks', () {
      test('isRunning returns correct value for each state type', () {
        // IdleState
        expect(const IdleState().isRunning, isFalse);

        // RunningState
        const runningConversation = domain.Conversation(
          threadId: 't',
          status: domain.Running(runId: 'r'),
        );
        expect(
          const RunningState(conversation: runningConversation).isRunning,
          isTrue,
        );

        // CompletedState with Success
        const completedConversation = domain.Conversation(
          threadId: 't',
          status: domain.Completed(),
        );
        expect(
          const CompletedState(
            conversation: completedConversation,
            result: Success(),
          ).isRunning,
          isFalse,
        );

        // CompletedState with Failed
        const failedConversation = domain.Conversation(
          threadId: 't',
          status: domain.Failed(error: 'Error'),
        );
        expect(
          const CompletedState(
            conversation: failedConversation,
            result: FailedResult(errorMessage: 'Error'),
          ).isRunning,
          isFalse,
        );

        // CompletedState with Cancelled
        const cancelledConversation = domain.Conversation(
          threadId: 't',
          status: domain.Cancelled(reason: 'User cancelled'),
        );
        expect(
          const CompletedState(
            conversation: cancelledConversation,
            result: CancelledResult(reason: 'User cancelled'),
          ).isRunning,
          isFalse,
        );
      });
    });

    group('convenience getters', () {
      test('messages delegates to conversation.messages', () {
        final message = TextMessage.create(
          id: 'msg-1',
          user: ChatUser.user,
          text: 'Hello',
        );
        final conversation = domain.Conversation(
          threadId: 'thread-1',
          messages: [message],
          status: const domain.Running(runId: 'r'),
        );
        final state = RunningState(conversation: conversation);

        expect(state.messages, [message]);
      });

      test('activeToolCalls delegates to conversation.toolCalls', () {
        const toolCall = ToolCallInfo(id: 'tc-1', name: 'search');
        const conversation = domain.Conversation(
          threadId: 'thread-1',
          toolCalls: [toolCall],
          status: domain.Running(runId: 'r'),
        );
        const state = RunningState(conversation: conversation);

        expect(state.activeToolCalls, [toolCall]);
      });

      test('streaming defaults to NotStreaming', () {
        const conversation = domain.Conversation(
          threadId: 'thread-1',
          status: domain.Running(runId: 'r'),
        );
        const state = RunningState(conversation: conversation);

        expect(state.streaming, isA<NotStreaming>());
      });

      test('isStreaming returns true when Streaming', () {
        const conversation = domain.Conversation(
          threadId: 'thread-1',
          status: domain.Running(runId: 'r'),
        );
        const state = RunningState(
          conversation: conversation,
          streaming: Streaming(messageId: 'msg-1', text: 'Hello'),
        );

        expect(state.isStreaming, isTrue);
      });
    });
  });

  group('NotifierInternalState', () {
    test('IdleInternalState can be created', () {
      const state = IdleInternalState();
      expect(state, isA<NotifierInternalState>());
    });

    test('RunningInternalState holds resources', () {
      final cancelToken = CancelToken();
      final controller = StreamController<BaseEvent>();

      final state = RunningInternalState(
        cancelToken: cancelToken,
        subscription: controller.stream.listen((_) {}),
      );

      expect(state, isA<NotifierInternalState>());
      expect(state.cancelToken, equals(cancelToken));

      // Cleanup
      controller.close();
      state.dispose();
    });
  });

  group('startRun', () {
    late ProviderContainer container;
    late StreamController<BaseEvent> eventStreamController;

    setUp(() {
      eventStreamController = StreamController<BaseEvent>();

      // Mock createRun to return a run with backend-generated ID
      when(
        () => mockApi.createRun(
          any(),
          any(),
          cancelToken: any(named: 'cancelToken'),
        ),
      ).thenAnswer(
        (_) async => RunInfo(
          id: 'backend-run-id-123',
          threadId: 'thread-1',
          createdAt: DateTime.now(),
        ),
      );

      // Mock runAgent to return our controlled stream
      when(
        () => mockAgUiClient.runAgent(
          any(),
          any(),
          cancelToken: any(named: 'cancelToken'),
        ),
      ).thenAnswer((_) => eventStreamController.stream);

      container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
          agUiClientProvider.overrideWithValue(mockAgUiClient),
        ],
      );
    });

    tearDown(() {
      eventStreamController.close();
      container.dispose();
    });

    test('displays user message immediately when starting run', () async {
      const userMessage = 'Hello, world!';
      const roomId = 'room-1';
      const threadId = 'thread-1';

      // Start the run
      await container.read(activeRunNotifierProvider.notifier).startRun(
            roomId: roomId,
            threadId: threadId,
            userMessage: userMessage,
          );

      // Get the current state
      final state = container.read(activeRunNotifierProvider);

      // Verify state is running
      expect(state, isA<RunningState>());
      expect(state.isRunning, isTrue);

      // Verify user message is in the messages list
      expect(state.messages.length, 1);
      final message = state.messages.first;
      expect(message, isA<TextMessage>());
      expect(message.user, ChatUser.user);
      expect((message as TextMessage).text, userMessage);
    });

    test(
      'transitions to RunningState with correct thread and run IDs',
      () async {
        const roomId = 'room-1';
        const threadId = 'thread-1';

        await container.read(activeRunNotifierProvider.notifier).startRun(
              roomId: roomId,
              threadId: threadId,
              userMessage: 'Test',
            );

        final state = container.read(activeRunNotifierProvider);

        expect(state, isA<RunningState>());
        final runningState = state as RunningState;
        expect(runningState.threadId, threadId);
        expect(runningState.runId, 'backend-run-id-123');
      },
    );

    test('uses existingRunId when provided instead of creating new', () async {
      const roomId = 'room-1';
      const threadId = 'thread-1';
      const existingRunId = 'existing-run-456';

      await container.read(activeRunNotifierProvider.notifier).startRun(
            roomId: roomId,
            threadId: threadId,
            userMessage: 'Test',
            existingRunId: existingRunId,
          );

      final state = container.read(activeRunNotifierProvider);

      expect(state, isA<RunningState>());
      final runningState = state as RunningState;
      expect(runningState.runId, existingRunId);

      // Verify createRun was NOT called
      verifyNever(
        () => mockApi.createRun(
          any(),
          any(),
          cancelToken: any(named: 'cancelToken'),
        ),
      );
    });

    test('treats empty existingRunId same as null', () async {
      const roomId = 'room-1';
      const threadId = 'thread-1';

      await container.read(activeRunNotifierProvider.notifier).startRun(
            roomId: roomId,
            threadId: threadId,
            userMessage: 'Test',
            existingRunId: '',
          );

      final state = container.read(activeRunNotifierProvider);

      expect(state, isA<RunningState>());
      final runningState = state as RunningState;
      expect(runningState.runId, 'backend-run-id-123');

      // Verify createRun WAS called (empty string treated as null)
      verify(
        () => mockApi.createRun(
          any(),
          any(),
          cancelToken: any(named: 'cancelToken'),
        ),
      ).called(1);
    });

    test('throws StateError if run already active', () async {
      const roomId = 'room-1';
      const threadId = 'thread-1';

      // Start first run
      await container.read(activeRunNotifierProvider.notifier).startRun(
            roomId: roomId,
            threadId: threadId,
            userMessage: 'First',
          );

      // Attempt to start second run
      expect(
        () => container.read(activeRunNotifierProvider.notifier).startRun(
              roomId: roomId,
              threadId: threadId,
              userMessage: 'Second',
            ),
        throwsA(isA<StateError>()),
      );
    });
  });

  group('cancelRun', () {
    late ProviderContainer container;
    late StreamController<BaseEvent> eventStreamController;

    setUp(() {
      eventStreamController = StreamController<BaseEvent>();

      when(
        () => mockApi.createRun(
          any(),
          any(),
          cancelToken: any(named: 'cancelToken'),
        ),
      ).thenAnswer(
        (_) async => RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          createdAt: DateTime.now(),
        ),
      );

      when(
        () => mockAgUiClient.runAgent(
          any(),
          any(),
          cancelToken: any(named: 'cancelToken'),
        ),
      ).thenAnswer((_) => eventStreamController.stream);

      container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
          agUiClientProvider.overrideWithValue(mockAgUiClient),
        ],
      );
    });

    tearDown(() {
      eventStreamController.close();
      container.dispose();
    });

    test('transitions to CompletedState with Cancelled result', () async {
      // Start a run
      await container.read(activeRunNotifierProvider.notifier).startRun(
            roomId: 'room-1',
            threadId: 'thread-1',
            userMessage: 'Hello',
          );

      // Cancel the run
      await container.read(activeRunNotifierProvider.notifier).cancelRun();

      final state = container.read(activeRunNotifierProvider);
      expect(state, isA<CompletedState>());
      final completedState = state as CompletedState;
      expect(completedState.result, isA<CancelledResult>());
    });

    test('preserves messages after cancellation', () async {
      // Start a run
      await container.read(activeRunNotifierProvider.notifier).startRun(
            roomId: 'room-1',
            threadId: 'thread-1',
            userMessage: 'Hello',
          );

      // Cancel the run
      await container.read(activeRunNotifierProvider.notifier).cancelRun();

      final state = container.read(activeRunNotifierProvider);
      expect(state.messages.length, 1);
      expect((state.messages.first as TextMessage).text, 'Hello');
    });
  });
}
