import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:soliplex_client/infrastructure/quick_agui/thread.dart';

class AgUiClientMock extends Mock implements ag_ui.AgUiClient {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      ag_ui.SimpleRunAgentInput(
        threadId: '--irrelevant-thread-id--',
        runId: '--irrelevant-run-id--',
        messages: [],
      ),
    );
  });

  const threadId = '--irrelevant-thread-id--';
  const runId = '--irrelevant-run-id--';

  late ag_ui.AgUiClient client;
  late Thread thread;

  setUp(() {
    client = AgUiClientMock();
    thread = Thread(id: threadId, client: client);
  });

  group('Initialised Thread', () {
    test('exposes an empty iterable of Run objects', () {
      expect(thread.runs, isNotNull);
      expect(thread.runs, isA<Iterable<ag_ui.Run>>());
    });

    group('First run', () {
      test('startRun tracks the first run', () {
        when(
          () => client.runAgent(any(), any()),
        ).thenAnswer((_) => Stream.empty());

        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
        );

        final [ag_ui.Run(runId: capturedRunId)] = thread.runs.toList();
        expect(capturedRunId, runId);
      });

      test('one text message chunk', () async {
        when(() => client.runAgent(any(), any())).thenAnswer(
          (_) => Stream.fromIterable([
            ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
            ag_ui.TextMessageChunkEvent(
              messageId: 'msg-id-2',
              delta: 'hi! What can I do?',
            ),
            ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
          ]),
        );

        final publishedMessages = thread.messageStream.take(2).toList();
        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
        );

        final [msg1, msg2] = await publishedMessages;
        expect(
          msg1,
          isA<ag_ui.UserMessage>()
              .having((m) => m.content, 'content', equals('hi!'))
              .having((m) => m.id, 'message id', equals('msg-id-1')),
        );
        expect(
          msg2,
          isA<ag_ui.AssistantMessage>()
              .having((m) => m.content, 'content', equals('hi! What can I do?'))
              .having((m) => m.id, 'message id', equals('msg-id-2')),
        );
      }, timeout: Timeout(Duration(seconds: 2)));

      test('text message contents', () async {
        when(() => client.runAgent(any(), any())).thenAnswer(
          (_) => Stream.fromIterable([
            ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
            ag_ui.TextMessageStartEvent(messageId: 'msg-id-2'),
            ag_ui.TextMessageContentEvent(messageId: 'msg-id-2', delta: 'he'),
            ag_ui.TextMessageContentEvent(messageId: 'msg-id-2', delta: 'll'),
            ag_ui.TextMessageContentEvent(messageId: 'msg-id-2', delta: 'o'),
            ag_ui.TextMessageContentEvent(messageId: 'msg-id-2', delta: '!'),
            ag_ui.TextMessageContentEvent(messageId: 'msg-id-2', delta: ' '),
            ag_ui.TextMessageContentEvent(
              messageId: 'msg-id-2',
              delta: 'what can I',
            ),
            ag_ui.TextMessageContentEvent(messageId: 'msg-id-2', delta: ' do?'),
            ag_ui.TextMessageEndEvent(messageId: 'msg-id-2'),
            ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
          ]),
        );

        final publishedMessages = thread.messageStream.take(2).toList();
        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
        );

        final [msg1, msg2] = await publishedMessages;
        expect(
          msg1,
          isA<ag_ui.UserMessage>()
              .having((m) => m.content, 'content', equals('hi!'))
              .having((m) => m.id, 'message id', equals('msg-id-1')),
        );
        expect(
          msg2,
          isA<ag_ui.AssistantMessage>()
              .having(
                (m) => m.content,
                'content',
                equals('hello! what can I do?'),
              )
              .having((m) => m.id, 'message id', equals('msg-id-2')),
        );
      }, timeout: Timeout(Duration(seconds: 2)));
    });

    group('Second run starting with user message', () {
      test('sends message history along the new user message', () async {
        final (msgId1, msgId2, msgId3, msgId4) = (
          'msg-1',
          'msg-2',
          'msg-3',
          'msg-4',
        );

        clientWillReceive(client, [
          ag_ui.RunStartedEvent(threadId: threadId, runId: 'run-id-1'),
          ag_ui.TextMessageChunkEvent(messageId: msgId2, delta: 'hello'),
          ag_ui.RunFinishedEvent(threadId: threadId, runId: 'run-id-1'),
        ]);

        await thread.startRun(
          endpoint: 'agent',
          runId: 'run-id-1',
          message: ag_ui.UserMessage(id: msgId1, content: "hi"),
        );

        clientWillReceive(client, [
          ag_ui.RunStartedEvent(threadId: threadId, runId: 'run-id-2'),
          ag_ui.TextMessageChunkEvent(messageId: msgId4, delta: 'No problem'),
          ag_ui.RunFinishedEvent(threadId: threadId, runId: 'run-id-2'),
        ]);

        await thread.startRun(
          endpoint: 'agent',
          runId: 'run-id-2',
          message: ag_ui.UserMessage(id: msgId3, content: "Thanks"),
        );

        final captured = captureRunAgentInput(client);

        expect(captured.messages![0], isUserMessage(msgId1));
        expect(captured.messages![1], isAssistantMessage(msgId2));
        expect(captured.messages![2], isUserMessage(msgId3));
      });
    });
  });

  group('Parse all events', () {
    setUp(() {
      thread = Thread(id: threadId, client: client);
    });

    test('step events', () async {
      when(() => client.runAgent(any(), any())).thenAnswer(
        (_) => Stream.fromIterable([
          ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
          ag_ui.StepStartedEvent(stepName: 'task a'),
          ag_ui.StepFinishedEvent(stepName: 'task a'),
          ag_ui.StepStartedEvent(stepName: 'task b'),
          ag_ui.StepFinishedEvent(stepName: 'task b'),
          ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
        ]),
      );

      final publishedStates = thread.stateStream.take(2).toList();
      thread.startRun(
        endpoint: 'agent',
        runId: runId,
        message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
      );

      final [{'step': step1}, {'step': step2}] = await publishedStates;
      expect(step1, equals('task a'));
      expect(step2, equals('task b'));
    }, timeout: Timeout(Duration(seconds: 2)));
    
    test('interleaving step events', () async {
      when(() => client.runAgent(any(), any())).thenAnswer(
        (_) => Stream.fromIterable([
          ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
          ag_ui.StepStartedEvent(stepName: 'task a'),
          ag_ui.StepStartedEvent(stepName: 'task b'),
          ag_ui.StepFinishedEvent(stepName: 'task a'),
          ag_ui.StepFinishedEvent(stepName: 'task b'),
          ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
        ]),
      );

      final publishedStates = thread.stateStream.take(2).toList();
      thread.startRun(
        endpoint: 'agent',
        runId: runId,
        message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
      );

      final [{'step': step1}, {'step': step2}] = await publishedStates;
      expect(step1, equals('task a'));
      expect(step2, equals('task b'));
    }, timeout: Timeout(Duration(seconds: 2)));

    test('tool call events', () async {
      const toolCallId = 'tool-call-id';
      const toolCallName = 'add-numbers';
      when(() => client.runAgent(any(), any())).thenAnswer(
        (_) => Stream.fromIterable([
          ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
          ag_ui.ToolCallStartEvent(
            toolCallId: toolCallId,
            toolCallName: toolCallName,
          ),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: "{'arg1':"),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: " 1, '"),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: "arg2'"),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: ": 2}"),
          ag_ui.ToolCallEndEvent(toolCallId: toolCallId),
          ag_ui.ToolCallResultEvent(
            messageId: 'result_$toolCallId',
            toolCallId: toolCallId,
            content: "{'sum': 3}",
          ),
          ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
        ]),
      );

      final publishedMessages = thread.messageStream.take(3).toList();
      thread.startRun(
        endpoint: 'agent',
        runId: runId,
        message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
      );

      final [_, msg1, msg2] = await publishedMessages;
      expect(
        msg1,
        isA<ag_ui.AssistantMessage>().having(
          (m) => m.toJson(),
          'entire message in json',
          equals(msg1.toJson()),
        ),
      );

      final assistantMessage = msg1 as ag_ui.AssistantMessage;

      expect(assistantMessage.id, equals('msg_$toolCallId'));
      expect(assistantMessage.toolCalls?.length ?? 0, equals(1));

      final [toolCall] = assistantMessage.toolCalls!;

      expect(toolCall.id, equals(toolCallId));

      final functionCall = toolCall.function;

      expect(functionCall.name, toolCallName);
      expect(functionCall.arguments, "{'arg1': 1, 'arg2': 2}");

      expect(
        msg2,
        isA<ag_ui.ToolMessage>()
            .having((m) => m.content, 'content', equals("{'sum': 3}"))
            .having((m) => m.id, 'message id', equals('result_$toolCallId')),
      );
    }, timeout: Timeout(Duration(seconds: 2)));
  });
}

void clientWillReceive(ag_ui.AgUiClient client, List<ag_ui.BaseEvent> events) {
  when(
    () => client.runAgent(any(), any()),
  ).thenAnswer((_) => Stream.fromIterable(events));
}

ag_ui.SimpleRunAgentInput captureRunAgentInput(ag_ui.AgUiClient client) {
  return verify(() => client.runAgent('agent', captureAny())).captured.last
      as ag_ui.SimpleRunAgentInput;
}

TypeMatcher<ag_ui.UserMessage> isUserMessage(String id) =>
    isA<ag_ui.UserMessage>().having((m) => m.id, "id", equals(id));

TypeMatcher<ag_ui.AssistantMessage> isAssistantMessage(String id) =>
    isA<ag_ui.AssistantMessage>().having((m) => m.id, "id", equals(id));
