import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/infrastructure/quick_agui/thread.dart';

void main() {
  group('Thread', () {
    test('creates thread with delegate', () {
      var delegateCalled = false;

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) {
          delegateCalled = true;
          return const Stream.empty();
        },
      );

      expect(thread.id, equals('test-thread'));
      expect(delegateCalled, isFalse); // Not called until startRun

      thread.dispose();
    });

    test('delegate receives correct parameters during startRun', () async {
      String? receivedEndpoint;
      ag_ui.SimpleRunAgentInput? receivedInput;

      final thread = Thread(
        id: 'thread-123',
        runAgent: (endpoint, input) {
          receivedEndpoint = endpoint;
          receivedInput = input;
          return Stream.fromIterable([
            const ag_ui.RunStartedEvent(threadId: 'thread-123', runId: 'run-1'),
            const ag_ui.RunFinishedEvent(
              threadId: 'thread-123',
              runId: 'run-1',
            ),
          ]);
        },
      );

      await thread.startRun(
        endpoint: '/api/v1/agent',
        runId: 'run-1',
        messages: [const ag_ui.UserMessage(id: 'msg-1', content: 'Hello')],
        state: {'key': 'value'},
      );

      expect(receivedEndpoint, equals('/api/v1/agent'));
      expect(receivedInput, isNotNull);
      expect(receivedInput!.threadId, equals('thread-123'));
      expect(receivedInput!.runId, equals('run-1'));

      thread.dispose();
    });

    test('streams events through delegate', () async {
      final events = <ag_ui.BaseEvent>[];

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) => Stream.fromIterable([
          const ag_ui.RunStartedEvent(threadId: 'test-thread', runId: 'run-1'),
          const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          ),
          const ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Hello'),
          const ag_ui.TextMessageEndEvent(messageId: 'm1'),
          const ag_ui.RunFinishedEvent(threadId: 'test-thread', runId: 'run-1'),
        ]),
      );

      thread.stepsStream.listen(events.add);

      await thread.startRun(endpoint: '/agent', runId: 'run-1');

      expect(events.length, equals(5));
      expect(events[0], isA<ag_ui.RunStartedEvent>());
      expect(events[1], isA<ag_ui.TextMessageStartEvent>());
      expect(events[2], isA<ag_ui.TextMessageContentEvent>());
      expect(events[3], isA<ag_ui.TextMessageEndEvent>());
      expect(events[4], isA<ag_ui.RunFinishedEvent>());

      thread.dispose();
    });

    test('accumulates messages from text events', () async {
      final messages = <ag_ui.Message>[];

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) => Stream.fromIterable([
          const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          ),
          const ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Hello '),
          const ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'world!'),
          const ag_ui.TextMessageEndEvent(messageId: 'm1'),
        ]),
      );

      thread.messageStream.listen(messages.add);

      await thread.startRun(endpoint: '/agent', runId: 'run-1');

      // Should have one accumulated message
      final assistantMessages = messages
          .whereType<ag_ui.AssistantMessage>()
          .toList();
      expect(assistantMessages.length, equals(1));
      expect(assistantMessages[0].content, equals('Hello world!'));

      thread.dispose();
    });

    test('passes tools to delegate input', () async {
      ag_ui.SimpleRunAgentInput? receivedInput;

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) {
          receivedInput = input;
          return const Stream.empty();
        },
        tools: [
          const ag_ui.Tool(
            name: 'test_tool',
            description: 'A test tool',
            parameters: {'type': 'object'},
          ),
        ],
      );

      await thread.startRun(endpoint: '/agent', runId: 'run-1');

      expect(receivedInput!.tools, isNotNull);
      expect(receivedInput!.tools!.length, equals(1));
      expect(receivedInput!.tools![0].name, equals('test_tool'));

      thread.dispose();
    });

    test('delegate errors propagate correctly', () async {
      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) =>
            Stream.error(Exception('Connection failed')),
      );

      await expectLater(
        thread.startRun(endpoint: '/agent', runId: 'run-1'),
        throwsException,
      );

      thread.dispose();
    });

    test('disposed thread ignores startRun calls', () async {
      var delegateCalled = false;

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) {
          delegateCalled = true;
          return const Stream.empty();
        },
      );

      thread.dispose();

      final result = await thread.startRun(endpoint: '/agent', runId: 'run-1');

      expect(delegateCalled, isFalse);
      expect(result, isEmpty);
    });

    test('addTool adds tools that are sent with requests', () async {
      ag_ui.SimpleRunAgentInput? receivedInput;

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) {
          receivedInput = input;
          return const Stream.empty();
        },
      );

      thread.addTool(
        const ag_ui.Tool(
          name: 'dynamic_tool',
          description: 'Added dynamically',
          parameters: {'type': 'object'},
        ),
        (call) async => 'result',
      );

      await thread.startRun(endpoint: '/agent', runId: 'run-1');

      expect(
        receivedInput!.tools!.any((t) => t.name == 'dynamic_tool'),
        isTrue,
      );

      thread.dispose();
    });

    test('reset clears message history', () async {
      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) => Stream.fromIterable([
          const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          ),
          const ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Hello'),
          const ag_ui.TextMessageEndEvent(messageId: 'm1'),
        ]),
      );

      await thread.startRun(endpoint: '/agent', runId: 'run-1');
      expect(thread.messageHistory.isNotEmpty, isTrue);

      thread.reset();
      expect(thread.messageHistory.isEmpty, isTrue);

      thread.dispose();
    });
  });

  group('Thread _getRunAgentStream', () {
    test('uses delegate', () async {
      var delegateUsed = false;

      final thread = Thread(
        id: 'test',
        runAgent: (endpoint, input) {
          delegateUsed = true;
          return const Stream.empty();
        },
      );

      await thread.startRun(endpoint: '/agent', runId: 'run-1');
      expect(delegateUsed, isTrue);

      thread.dispose();
    });
  });
}
