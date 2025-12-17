import 'package:soliplex_client/src/agui/agui_event.dart';
import 'package:test/test.dart';

void main() {
  group('AgUiEventType', () {
    test('fromString parses SCREAMING_SNAKE_CASE to camelCase', () {
      expect(
        AgUiEventType.fromString('RUN_STARTED'),
        equals(AgUiEventType.runStarted),
      );
      expect(
        AgUiEventType.fromString('RUN_FINISHED'),
        equals(AgUiEventType.runFinished),
      );
      expect(
        AgUiEventType.fromString('RUN_ERROR'),
        equals(AgUiEventType.runError),
      );
      expect(
        AgUiEventType.fromString('STEP_STARTED'),
        equals(AgUiEventType.stepStarted),
      );
      expect(
        AgUiEventType.fromString('STEP_FINISHED'),
        equals(AgUiEventType.stepFinished),
      );
      expect(
        AgUiEventType.fromString('TEXT_MESSAGE_START'),
        equals(AgUiEventType.textMessageStart),
      );
      expect(
        AgUiEventType.fromString('TEXT_MESSAGE_CONTENT'),
        equals(AgUiEventType.textMessageContent),
      );
      expect(
        AgUiEventType.fromString('TEXT_MESSAGE_END'),
        equals(AgUiEventType.textMessageEnd),
      );
      expect(
        AgUiEventType.fromString('TOOL_CALL_START'),
        equals(AgUiEventType.toolCallStart),
      );
      expect(
        AgUiEventType.fromString('TOOL_CALL_ARGS'),
        equals(AgUiEventType.toolCallArgs),
      );
      expect(
        AgUiEventType.fromString('TOOL_CALL_END'),
        equals(AgUiEventType.toolCallEnd),
      );
      expect(
        AgUiEventType.fromString('TOOL_CALL_RESULT'),
        equals(AgUiEventType.toolCallResult),
      );
      expect(
        AgUiEventType.fromString('STATE_SNAPSHOT'),
        equals(AgUiEventType.stateSnapshot),
      );
      expect(
        AgUiEventType.fromString('STATE_DELTA'),
        equals(AgUiEventType.stateDelta),
      );
      expect(
        AgUiEventType.fromString('ACTIVITY_SNAPSHOT'),
        equals(AgUiEventType.activitySnapshot),
      );
      expect(
        AgUiEventType.fromString('ACTIVITY_DELTA'),
        equals(AgUiEventType.activityDelta),
      );
      expect(
        AgUiEventType.fromString('MESSAGES_SNAPSHOT'),
        equals(AgUiEventType.messagesSnapshot),
      );
      expect(
        AgUiEventType.fromString('CUSTOM'),
        equals(AgUiEventType.custom),
      );
    });

    test('fromString returns unknown for unrecognized types', () {
      expect(
        AgUiEventType.fromString('UNKNOWN_TYPE'),
        equals(AgUiEventType.unknown),
      );
      expect(
        AgUiEventType.fromString(''),
        equals(AgUiEventType.unknown),
      );
      expect(
        AgUiEventType.fromString('INVALID_EVENT'),
        equals(AgUiEventType.unknown),
      );
    });

    test('toJsonString converts camelCase to SCREAMING_SNAKE_CASE', () {
      expect(
        AgUiEventType.runStarted.toJsonString(),
        equals('RUN_STARTED'),
      );
      expect(
        AgUiEventType.textMessageContent.toJsonString(),
        equals('TEXT_MESSAGE_CONTENT'),
      );
      expect(
        AgUiEventType.toolCallStart.toJsonString(),
        equals('TOOL_CALL_START'),
      );
    });
  });

  group('AgUiEvent.fromJson', () {
    test('parses RunStartedEvent', () {
      final json = {
        'type': 'RUN_STARTED',
        'thread_id': 'thread-123',
        'run_id': 'run-456',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<RunStartedEvent>());
      final runStarted = event as RunStartedEvent;
      expect(runStarted.type, equals(AgUiEventType.runStarted));
      expect(runStarted.threadId, equals('thread-123'));
      expect(runStarted.runId, equals('run-456'));
    });

    test('parses RunFinishedEvent', () {
      final json = {
        'type': 'RUN_FINISHED',
        'thread_id': 'thread-123',
        'run_id': 'run-456',
        'result': {'status': 'ok'},
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<RunFinishedEvent>());
      final runFinished = event as RunFinishedEvent;
      expect(runFinished.threadId, equals('thread-123'));
      expect(runFinished.runId, equals('run-456'));
      expect(runFinished.result, equals({'status': 'ok'}));
    });

    test('parses RunFinishedEvent without result', () {
      final json = {
        'type': 'RUN_FINISHED',
        'thread_id': 'thread-123',
        'run_id': 'run-456',
      };

      final event = AgUiEvent.fromJson(json) as RunFinishedEvent;
      expect(event.result, isNull);
    });

    test('parses RunErrorEvent', () {
      final json = {
        'type': 'RUN_ERROR',
        'thread_id': 'thread-123',
        'run_id': 'run-456',
        'message': 'Something went wrong',
        'code': 'ERR_001',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<RunErrorEvent>());
      final runError = event as RunErrorEvent;
      expect(runError.threadId, equals('thread-123'));
      expect(runError.runId, equals('run-456'));
      expect(runError.message, equals('Something went wrong'));
      expect(runError.code, equals('ERR_001'));
    });

    test('parses RunErrorEvent without code', () {
      final json = {
        'type': 'RUN_ERROR',
        'thread_id': 'thread-123',
        'run_id': 'run-456',
        'message': 'Error occurred',
      };

      final event = AgUiEvent.fromJson(json) as RunErrorEvent;
      expect(event.code, isNull);
    });

    test('parses StepStartedEvent', () {
      final json = {
        'type': 'STEP_STARTED',
        'step_name': 'processing',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<StepStartedEvent>());
      final stepStarted = event as StepStartedEvent;
      expect(stepStarted.stepName, equals('processing'));
    });

    test('parses StepFinishedEvent', () {
      final json = {
        'type': 'STEP_FINISHED',
        'step_name': 'processing',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<StepFinishedEvent>());
      final stepFinished = event as StepFinishedEvent;
      expect(stepFinished.stepName, equals('processing'));
    });

    test('parses TextMessageStartEvent', () {
      final json = {
        'type': 'TEXT_MESSAGE_START',
        'message_id': 'msg-123',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<TextMessageStartEvent>());
      final textStart = event as TextMessageStartEvent;
      expect(textStart.messageId, equals('msg-123'));
    });

    test('parses TextMessageContentEvent', () {
      final json = {
        'type': 'TEXT_MESSAGE_CONTENT',
        'message_id': 'msg-123',
        'delta': 'Hello, ',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<TextMessageContentEvent>());
      final textContent = event as TextMessageContentEvent;
      expect(textContent.messageId, equals('msg-123'));
      expect(textContent.delta, equals('Hello, '));
    });

    test('parses TextMessageEndEvent', () {
      final json = {
        'type': 'TEXT_MESSAGE_END',
        'message_id': 'msg-123',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<TextMessageEndEvent>());
      final textEnd = event as TextMessageEndEvent;
      expect(textEnd.messageId, equals('msg-123'));
    });

    test('parses ToolCallStartEvent', () {
      final json = {
        'type': 'TOOL_CALL_START',
        'tool_call_id': 'tc-123',
        'tool_call_name': 'search',
        'parent_message_id': 'msg-456',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<ToolCallStartEvent>());
      final toolStart = event as ToolCallStartEvent;
      expect(toolStart.toolCallId, equals('tc-123'));
      expect(toolStart.toolCallName, equals('search'));
      expect(toolStart.parentMessageId, equals('msg-456'));
    });

    test('parses ToolCallStartEvent without parentMessageId', () {
      final json = {
        'type': 'TOOL_CALL_START',
        'tool_call_id': 'tc-123',
        'tool_call_name': 'search',
      };

      final event = AgUiEvent.fromJson(json) as ToolCallStartEvent;
      expect(event.parentMessageId, isNull);
    });

    test('parses ToolCallArgsEvent', () {
      final json = {
        'type': 'TOOL_CALL_ARGS',
        'tool_call_id': 'tc-123',
        'delta': '{"query": "test"}',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<ToolCallArgsEvent>());
      final toolArgs = event as ToolCallArgsEvent;
      expect(toolArgs.toolCallId, equals('tc-123'));
      expect(toolArgs.delta, equals('{"query": "test"}'));
    });

    test('parses ToolCallEndEvent', () {
      final json = {
        'type': 'TOOL_CALL_END',
        'tool_call_id': 'tc-123',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<ToolCallEndEvent>());
      final toolEnd = event as ToolCallEndEvent;
      expect(toolEnd.toolCallId, equals('tc-123'));
    });

    test('parses ToolCallResultEvent', () {
      final json = {
        'type': 'TOOL_CALL_RESULT',
        'message_id': 'msg-789',
        'tool_call_id': 'tc-123',
        'content': 'Search results here',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<ToolCallResultEvent>());
      final toolResult = event as ToolCallResultEvent;
      expect(toolResult.messageId, equals('msg-789'));
      expect(toolResult.toolCallId, equals('tc-123'));
      expect(toolResult.content, equals('Search results here'));
    });

    test('parses StateSnapshotEvent', () {
      final json = {
        'type': 'STATE_SNAPSHOT',
        'snapshot': {'key': 'value', 'count': 42},
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<StateSnapshotEvent>());
      final stateSnapshot = event as StateSnapshotEvent;
      expect(stateSnapshot.snapshot, equals({'key': 'value', 'count': 42}));
    });

    test('parses StateSnapshotEvent with null snapshot', () {
      final json = {
        'type': 'STATE_SNAPSHOT',
      };

      final event = AgUiEvent.fromJson(json) as StateSnapshotEvent;
      expect(event.snapshot, isEmpty);
    });

    test('parses StateDeltaEvent', () {
      final json = {
        'type': 'STATE_DELTA',
        'delta': [
          {'op': 'add', 'path': '/key', 'value': 'newValue'},
          {'op': 'remove', 'path': '/oldKey'},
        ],
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<StateDeltaEvent>());
      final stateDelta = event as StateDeltaEvent;
      expect(stateDelta.delta, hasLength(2));
      expect(stateDelta.delta[0]['op'], equals('add'));
      expect(stateDelta.delta[1]['op'], equals('remove'));
    });

    test('parses StateDeltaEvent with null delta', () {
      final json = {
        'type': 'STATE_DELTA',
      };

      final event = AgUiEvent.fromJson(json) as StateDeltaEvent;
      expect(event.delta, isEmpty);
    });

    test('parses ActivitySnapshotEvent', () {
      final json = {
        'type': 'ACTIVITY_SNAPSHOT',
        'message_id': 'msg-123',
        'activity_type': 'thinking',
        'content': {'progress': 50},
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<ActivitySnapshotEvent>());
      final activitySnapshot = event as ActivitySnapshotEvent;
      expect(activitySnapshot.messageId, equals('msg-123'));
      expect(activitySnapshot.activityType, equals('thinking'));
      expect(activitySnapshot.content, equals({'progress': 50}));
    });

    test('parses ActivityDeltaEvent', () {
      final json = {
        'type': 'ACTIVITY_DELTA',
        'message_id': 'msg-123',
        'activity_type': 'thinking',
        'patch': [
          {'op': 'replace', 'path': '/progress', 'value': 75},
        ],
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<ActivityDeltaEvent>());
      final activityDelta = event as ActivityDeltaEvent;
      expect(activityDelta.messageId, equals('msg-123'));
      expect(activityDelta.activityType, equals('thinking'));
      expect(activityDelta.patch, hasLength(1));
      expect(activityDelta.patch[0]['op'], equals('replace'));
    });

    test('parses ActivityDeltaEvent with null patch', () {
      final json = {
        'type': 'ACTIVITY_DELTA',
        'message_id': 'msg-123',
        'activity_type': 'thinking',
      };

      final event = AgUiEvent.fromJson(json) as ActivityDeltaEvent;
      expect(event.patch, isEmpty);
    });

    test('parses MessagesSnapshotEvent', () {
      final json = {
        'type': 'MESSAGES_SNAPSHOT',
        'messages': [
          {'id': 'msg-1', 'text': 'Hello'},
          {'id': 'msg-2', 'text': 'World'},
        ],
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<MessagesSnapshotEvent>());
      final messagesSnapshot = event as MessagesSnapshotEvent;
      expect(messagesSnapshot.messages, hasLength(2));
      expect(messagesSnapshot.messages[0]['id'], equals('msg-1'));
      expect(messagesSnapshot.messages[1]['text'], equals('World'));
    });

    test('parses MessagesSnapshotEvent with null messages', () {
      final json = {
        'type': 'MESSAGES_SNAPSHOT',
      };

      final event = AgUiEvent.fromJson(json) as MessagesSnapshotEvent;
      expect(event.messages, isEmpty);
    });

    test('parses CustomEvent', () {
      final json = {
        'type': 'CUSTOM',
        'name': 'my_custom_event',
        'data': {'foo': 'bar'},
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<CustomEvent>());
      final customEvent = event as CustomEvent;
      expect(customEvent.name, equals('my_custom_event'));
      expect(customEvent.data, equals({'foo': 'bar'}));
    });

    test('parses UnknownEvent for unrecognized types', () {
      final json = {
        'type': 'FUTURE_EVENT_TYPE',
        'some_field': 'some_value',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<UnknownEvent>());
      final unknownEvent = event as UnknownEvent;
      expect(unknownEvent.rawType, equals('FUTURE_EVENT_TYPE'));
      expect(unknownEvent.rawJson, equals(json));
    });

    test('handles missing type field', () {
      final json = <String, dynamic>{
        'some_field': 'some_value',
      };

      final event = AgUiEvent.fromJson(json);

      expect(event, isA<UnknownEvent>());
      final unknownEvent = event as UnknownEvent;
      expect(unknownEvent.rawType, equals(''));
    });
  });

  group('Event toString', () {
    test('RunStartedEvent toString', () {
      const event = RunStartedEvent(threadId: 't1', runId: 'r1');
      expect(event.toString(), contains('RunStartedEvent'));
      expect(event.toString(), contains('t1'));
      expect(event.toString(), contains('r1'));
    });

    test('RunFinishedEvent toString', () {
      const event = RunFinishedEvent(threadId: 't1', runId: 'r1');
      expect(event.toString(), contains('RunFinishedEvent'));
    });

    test('RunErrorEvent toString', () {
      const event = RunErrorEvent(
        threadId: 't1',
        runId: 'r1',
        message: 'error',
      );
      expect(event.toString(), contains('RunErrorEvent'));
      expect(event.toString(), contains('error'));
    });

    test('StepStartedEvent toString', () {
      const event = StepStartedEvent(stepName: 'step1');
      expect(event.toString(), contains('StepStartedEvent'));
      expect(event.toString(), contains('step1'));
    });

    test('StepFinishedEvent toString', () {
      const event = StepFinishedEvent(stepName: 'step1');
      expect(event.toString(), contains('StepFinishedEvent'));
    });

    test('TextMessageStartEvent toString', () {
      const event = TextMessageStartEvent(messageId: 'msg1');
      expect(event.toString(), contains('TextMessageStartEvent'));
      expect(event.toString(), contains('msg1'));
    });

    test('TextMessageContentEvent toString', () {
      const event = TextMessageContentEvent(messageId: 'msg1', delta: 'hi');
      expect(event.toString(), contains('TextMessageContentEvent'));
      expect(event.toString(), contains('hi'));
    });

    test('TextMessageEndEvent toString', () {
      const event = TextMessageEndEvent(messageId: 'msg1');
      expect(event.toString(), contains('TextMessageEndEvent'));
    });

    test('ToolCallStartEvent toString', () {
      const event = ToolCallStartEvent(
        toolCallId: 'tc1',
        toolCallName: 'search',
      );
      expect(event.toString(), contains('ToolCallStartEvent'));
      expect(event.toString(), contains('search'));
    });

    test('ToolCallArgsEvent toString', () {
      const event = ToolCallArgsEvent(toolCallId: 'tc1', delta: 'args');
      expect(event.toString(), contains('ToolCallArgsEvent'));
    });

    test('ToolCallEndEvent toString', () {
      const event = ToolCallEndEvent(toolCallId: 'tc1');
      expect(event.toString(), contains('ToolCallEndEvent'));
    });

    test('ToolCallResultEvent toString', () {
      const event = ToolCallResultEvent(
        messageId: 'msg1',
        toolCallId: 'tc1',
        content: 'result',
      );
      expect(event.toString(), contains('ToolCallResultEvent'));
    });

    test('StateSnapshotEvent toString', () {
      const event = StateSnapshotEvent(snapshot: {'key': 'value'});
      expect(event.toString(), contains('StateSnapshotEvent'));
      expect(event.toString(), contains('key'));
    });

    test('StateDeltaEvent toString', () {
      const event = StateDeltaEvent(
        delta: [
          {'op': 'add'},
        ],
      );
      expect(event.toString(), contains('StateDeltaEvent'));
      expect(event.toString(), contains('1'));
    });

    test('ActivitySnapshotEvent toString', () {
      const event = ActivitySnapshotEvent(
        messageId: 'msg1',
        activityType: 'thinking',
        content: {},
      );
      expect(event.toString(), contains('ActivitySnapshotEvent'));
      expect(event.toString(), contains('thinking'));
    });

    test('ActivityDeltaEvent toString', () {
      const event = ActivityDeltaEvent(
        messageId: 'msg1',
        activityType: 'thinking',
        patch: [],
      );
      expect(event.toString(), contains('ActivityDeltaEvent'));
    });

    test('MessagesSnapshotEvent toString', () {
      const event = MessagesSnapshotEvent(messages: [{}, {}]);
      expect(event.toString(), contains('MessagesSnapshotEvent'));
      expect(event.toString(), contains('2'));
    });

    test('CustomEvent toString', () {
      const event = CustomEvent(name: 'custom', data: {});
      expect(event.toString(), contains('CustomEvent'));
      expect(event.toString(), contains('custom'));
    });

    test('UnknownEvent toString', () {
      const event = UnknownEvent(rawType: 'UNKNOWN', rawJson: {});
      expect(event.toString(), contains('UnknownEvent'));
      expect(event.toString(), contains('UNKNOWN'));
    });
  });

  group('Event defaults with missing fields', () {
    test('RunStartedEvent handles missing fields', () {
      final event = RunStartedEvent.fromJson(const {'type': 'RUN_STARTED'});
      expect(event.threadId, equals(''));
      expect(event.runId, equals(''));
    });

    test('RunErrorEvent handles missing message', () {
      final event = RunErrorEvent.fromJson(const {'type': 'RUN_ERROR'});
      expect(event.message, equals('Unknown error'));
    });

    test('TextMessageContentEvent handles missing delta', () {
      final event = TextMessageContentEvent.fromJson(const {
        'type': 'TEXT_MESSAGE_CONTENT',
        'message_id': 'msg1',
      });
      expect(event.delta, equals(''));
    });

    test('ToolCallArgsEvent handles missing delta', () {
      final event = ToolCallArgsEvent.fromJson(const {
        'type': 'TOOL_CALL_ARGS',
        'tool_call_id': 'tc1',
      });
      expect(event.delta, equals(''));
    });

    test('CustomEvent handles missing data', () {
      final event = CustomEvent.fromJson(const {
        'type': 'CUSTOM',
        'name': 'test',
      });
      expect(event.data, isEmpty);
    });

    test('ActivitySnapshotEvent handles missing content', () {
      final event = ActivitySnapshotEvent.fromJson(const {
        'type': 'ACTIVITY_SNAPSHOT',
        'message_id': 'msg1',
        'activity_type': 'thinking',
      });
      expect(event.content, isEmpty);
    });
  });
}
