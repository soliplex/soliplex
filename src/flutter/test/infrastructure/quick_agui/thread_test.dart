import 'dart:convert';

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
        clientWillReceive(client, []);

        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
        );

        final [ag_ui.Run(runId: capturedRunId)] = thread.runs.toList();
        expect(capturedRunId, runId);
      });

      test('one text message chunk', () async {
        clientWillReceive(
          client,
          aRunWithEvents(threadId, runId, [
            ag_ui.TextMessageChunkEvent(
              messageId: 'msg-id-2',
              delta: 'hi! What can I do?',
            ),
          ]),
        );

        final publishedMessages = thread.messageStream.take(2).toList();
        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
        );

        final [msg1, msg2] = await publishedMessages;
        expect(msg1, isUserMsg(id: 'msg-id-1', msg: 'hi!'));
        expect(msg2, isAssistantMsg(id: 'msg-id-2', msg: 'hi! What can I do?'));
      }, timeout: Timeout(Duration(seconds: 2)));

      test('text message contents', () async {
        clientWillReceive(
          client,
          aRunWithEvents(threadId, runId, [
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
          ]),
        );

        final publishedMessages = thread.messageStream.take(2).toList();
        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
        );

        final [msg1, msg2] = await publishedMessages;
        expect(msg1, isUserMsg(id: 'msg-id-1', msg: 'hi!'));
        expect(
          msg2,
          isAssistantMsg(id: 'msg-id-2', msg: 'hello! what can I do?'),
        );
      }, timeout: Timeout(Duration(seconds: 2)));

      test('one full state snapshot', () async {
        clientWillReceive(
          client,
          aRunWithEvents(threadId, runId, [
            ag_ui.StateSnapshotEvent(
              snapshot: {'firstName': 'Tony', 'lastName': 'Stark'},
            ),
          ]),
        );

        final upcomingStateUpdate = thread.stateStream.first;
        thread.startRun(
          endpoint: 'agent',
          runId: runId,
          messages: [
            ag_ui.UserMessage(
              id: '--irrelevant-msg-id--',
              content: '--irrelevant-content--',
            ),
          ],
        );

        final stateUpdate = await upcomingStateUpdate;
        expect(
          stateUpdate,
          isMap
              .having((m) => m['firstName'], 'firstName', 'Tony')
              .having((m) => m['lastName'], 'lastName', 'Stark'),
        );
      }, timeout: Timeout(Duration(seconds: 2)));

      test(
        'thread tracks last received state snapshot',
        () async {
          clientWillReceive(
            client,
            aRunWithEvents(threadId, runId, [
              ag_ui.StateSnapshotEvent(
                snapshot: {'firstName': 'Tony', 'lastName': 'Stark'},
              ),
            ]),
          );
          final upcomingStateUpdate = thread.stateStream.first;
          thread.startRun(
            endpoint: 'agent',
            runId: runId,
            messages: [
              ag_ui.UserMessage(
                id: '--irrelevant-msg-id--',
                content: '--irrelevant-content--',
              ),
            ],
          );
          final stateUpdate = await upcomingStateUpdate;
          expect(thread.currentState, equals(stateUpdate));
        },
        timeout: Timeout(Duration(seconds: 2)),
      );
    });

    group('Second run', () {
      group('starting with user message', () {
        setUp(() async {
          clientWillReceive(
            client,
            aRunWithEvents(threadId, 'run-id-1', [
              ag_ui.TextMessageChunkEvent(messageId: 'msg-2', delta: 'hello'),
            ]),
          );

          await thread.startRun(
            endpoint: 'agent',
            runId: 'run-id-1',
            messages: [ag_ui.UserMessage(id: 'msg-1', content: "hi")],
          );
        });

        test('sends message history along the new user message', () async {
          clientWillReceive(
            client,
            aRunWithEvents(threadId, 'run-id-2', [
              ag_ui.TextMessageChunkEvent(
                messageId: 'msg-4',
                delta: 'No problem',
              ),
            ]),
          );

          await thread.startRun(
            endpoint: 'agent',
            runId: 'run-id-2',
            messages: [ag_ui.UserMessage(id: 'msg-3', content: "Thanks")],
          );

          final captured = captureRunAgentInput(client);
          final [msg0, msg1, msg2, ...] = captured.messages!;
          expect(msg0, isUserMsg(id: 'msg-1', msg: 'hi'));
          expect(msg1, isAssistantMsg(id: 'msg-2', msg: 'hello'));
          expect(msg2, isUserMsg(id: 'msg-3', msg: 'Thanks'));
        });

        test(
          'patch current state upon receiving state delta event',
          () async {
            clientWillReceive(
              client,
              aRunWithEvents(threadId, runId, [
                ag_ui.StateSnapshotEvent(
                  snapshot: {"firstName": "Tony", "lastName": "Stark"},
                ),
                ag_ui.StateDeltaEvent(
                  delta: [
                    {
                      "op": "replace",
                      "path": "/lastName",
                      "value": "Not Stark",
                    },
                  ],
                ),
              ]),
            );

            final upcomingStateUpdate = thread.stateStream.take(2).last;
            thread.startRun(
              endpoint: '--irrelevant--',
              runId: '--irrelevant--',
              messages: [
                ag_ui.UserMessage(
                  id: '--irrelevant--',
                  content: '--irrelevant--',
                ),
              ],
            );

            await upcomingStateUpdate;
            expect(thread.currentState['firstName'], 'Tony');
            expect(thread.currentState['lastName'], 'Not Stark');
          },
          timeout: Timeout(Duration(seconds: 2)),
        );
      });

      group("starts with a patched state", () {
        test("the patched state is sent to the agent", () async {
          clientWillReceive(
            client,
            aRunWithEvents(threadId, '--irrelevant-run-id--', []),
          );
          thread.startRun(
            endpoint: '--irrelevant-endpoint--',
            runId: '--irrelevant-run-id--',
            messages: [],
            state: {'firstName': 'Tony', 'lastName': 'Stark'},
          );
          final submittedState = captureRunAgentInput(client).state;
          expect(
            submittedState,
            equals({'firstName': 'Tony', 'lastName': 'Stark'}),
          );
        });
      });
    });
  });

  group('Parse all events', () {
    setUp(() {
      thread = Thread(id: threadId, client: client);
    });

    test('step events', () async {
      final steps = [
        ag_ui.StepStartedEvent(stepName: 'task a'),
        ag_ui.StepFinishedEvent(stepName: 'task a'),
        ag_ui.StepStartedEvent(stepName: 'task b'),
        ag_ui.StepFinishedEvent(stepName: 'task b'),
      ];
      clientWillReceive(client, aRunWithEvents(threadId, runId, steps));

      final upcomingSteps = thread.stepsStream.take(4).toList();
      thread.startRun(
        endpoint: 'agent',
        runId: runId,
        messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
      );

      final publishedSteps = await upcomingSteps;
      expect(publishedSteps, equals(steps));
    }, timeout: Timeout(Duration(seconds: 2)));

    test('interleaving step events', () async {
      final interleavedSteps = [
        ag_ui.StepStartedEvent(stepName: 'task a'),
        ag_ui.StepStartedEvent(stepName: 'task b'),
        ag_ui.StepFinishedEvent(stepName: 'task a'),
        ag_ui.StepFinishedEvent(stepName: 'task b'),
      ];
      clientWillReceive(
        client,
        aRunWithEvents(threadId, runId, interleavedSteps),
      );

      final upcomingSteps = thread.stepsStream.take(4).toList();
      thread.startRun(
        endpoint: 'agent',
        runId: runId,
        messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
      );

      final publishedSteps = await upcomingSteps;
      expect(publishedSteps, equals(interleavedSteps));
    }, timeout: Timeout(Duration(seconds: 2)));

    test('tool call events', () async {
      const toolCallId = 'tool-call-id';
      const toolCallName = 'add-numbers';
      clientWillReceive(
        client,
        aRunWithEvents(threadId, runId, [
          ag_ui.ToolCallStartEvent(
            toolCallId: toolCallId,
            toolCallName: toolCallName,
          ),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: '{"arg1":'),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: ' 1, "'),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: 'arg2"'),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: ': 2}'),
          ag_ui.ToolCallEndEvent(toolCallId: toolCallId),
          ag_ui.ToolCallResultEvent(
            messageId: 'result_$toolCallId',
            toolCallId: toolCallId,
            content: "{'sum': 3}",
          ),
        ]),
      );

      await thread.startRun(
        endpoint: 'agent',
        runId: runId,
        messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
      );

      final [_, msg1, msg2] = thread.messageHistory;
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
      expect(functionCall.arguments, '{"arg1": 1, "arg2": 2}');

      expect(
        msg2,
        isA<ag_ui.ToolMessage>()
            .having((m) => m.content, 'content', equals("{'sum': 3}"))
            .having((m) => m.id, 'message id', equals('result_$toolCallId')),
      );
    }, timeout: Timeout(Duration(seconds: 2)));
  });

  group('Tool call interactions', () {
    const toolCallName = 'add-numbers';

    setUp(() {
      thread = Thread(
        id: threadId,
        client: client,
        tools: [
          ag_ui.Tool(
            name: toolCallName,
            parameters: {
              'schema': 'json-schema.org',
              'title': 'Two Integer Inputs',
              'description':
                  'A schema for an object containing two integer inputs.',
              'type': 'object',
              'required': ['input1', 'input2'],
              'properties': {
                'input1': {
                  'type': 'integer',
                  'description': 'The first integer input.',
                  'minimum': -2147483648,
                  'maximum': 2147483647,
                },
                'input2': {
                  'type': 'integer',
                  'description': 'The second integer input.',
                  'minimum': -2147483648,
                  'maximum': 2147483647,
                },
              },
              'additionalProperties': false,
            },
            description: 'add two numbers',
          ),
        ],
        toolExecutors: {
          toolCallName: (toolCall) async {
            final arguments = jsonDecode(toolCall.function.arguments);
            return '{"sum":${arguments['input1'] + arguments['input2']}}';
          },
        },
      );
    });

    test('Client side tool call', () async {
      const toolCallId = 'tool-call-id';
      const toolCallName = 'add-numbers';

      clientWillReceive(
        client,
        aRunWithEvents(threadId, runId, [
          ag_ui.ToolCallStartEvent(
            toolCallId: toolCallId,
            toolCallName: toolCallName,
          ),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: '{"input1":'),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: ' 1, "'),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: 'input2"'),
          ag_ui.ToolCallArgsEvent(toolCallId: toolCallId, delta: ': 2}'),
          ag_ui.ToolCallEndEvent(toolCallId: toolCallId),
        ]),
      );

      final [result] = await thread.startRun(
        endpoint: 'agent',
        runId: runId,
        messages: [ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!')],
      );

      expect(result.content, equals('{"sum":3}'));

      clientWillReceive(
        client,
        aRunWithEvents(threadId, runId, [
          ag_ui.TextMessageChunkEvent(
            messageId: 'msg-3',
            delta: 'The sum is 3.',
          ),
        ]),
      );

      final result2 = await thread.startRun(
        endpoint: 'agent',
        runId: '$runId-2',
        messages: [result],
      );
      expect(result2, isEmpty);
    });
  });
}

void clientWillReceive(ag_ui.AgUiClient client, List<ag_ui.BaseEvent> events) {
  when(
    () => client.runAgent(any(), any()),
  ).thenAnswer((_) => Stream.fromIterable(events));
}

List<ag_ui.BaseEvent> aRunWithEvents(
  String threadId,
  String runId,
  List<ag_ui.BaseEvent> events,
) {
  return [
    ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
    ...events,
    ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
  ];
}

ag_ui.SimpleRunAgentInput captureRunAgentInput(ag_ui.AgUiClient client) {
  return verify(() => client.runAgent(any(), captureAny())).captured.last
      as ag_ui.SimpleRunAgentInput;
}

TypeMatcher<ag_ui.UserMessage> isUserMsg({
  required String id,
  required String msg,
}) => isA<ag_ui.UserMessage>()
    .having((m) => m.id, "id", equals(id))
    .having((m) => m.content, 'content', equals(msg));

TypeMatcher<ag_ui.AssistantMessage> isAssistantMsg({
  required String id,
  required String msg,
}) => isA<ag_ui.AssistantMessage>()
    .having((m) => m.id, "id", equals(id))
    .having((m) => m.content, 'content', equals(msg));
