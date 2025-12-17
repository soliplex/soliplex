import 'dart:async';
import 'dart:convert';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/src/agui/agui_event.dart';
import 'package:soliplex_client/src/agui/thread.dart' show Thread, ThreadRunStatus;
import 'package:soliplex_client/src/agui/tool_registry.dart';
import 'package:soliplex_client/src/http/http_transport.dart';
import 'package:soliplex_client/src/models/chat_message.dart';
import 'package:soliplex_client/src/utils/cancel_token.dart';
import 'package:test/test.dart';

class MockHttpTransport extends Mock implements HttpTransport {}

void main() {
  group('Thread', () {
    late MockHttpTransport mockTransport;
    late Thread thread;

    setUp(() {
      mockTransport = MockHttpTransport();
      thread = Thread(
        transport: mockTransport,
        roomId: 'room-123',
        threadId: 'thread-456',
      );
    });

    setUpAll(() {
      registerFallbackValue(Uri.parse('http://example.com'));
      registerFallbackValue(CancelToken());
    });

    group('initial state', () {
      test('runStatus is idle', () {
        expect(thread.runStatus, equals(ThreadRunStatus.idle));
      });

      test('runId is null', () {
        expect(thread.runId, isNull);
      });

      test('messages is empty', () {
        expect(thread.messages, isEmpty);
      });

      test('state is empty', () {
        expect(thread.state, isEmpty);
      });

      test('isRunning is false', () {
        expect(thread.isRunning, isFalse);
      });

      test('errorMessage is null', () {
        expect(thread.errorMessage, isNull);
      });
    });

    group('processEvent', () {
      test('processes TextMessageStart event', () {
        thread.processEvent(
          const TextMessageStartEvent(messageId: 'msg-1'),
        );

        expect(thread.textBuffer.isActive, isTrue);
        expect(thread.textBuffer.messageId, equals('msg-1'));
      });

      test('processes TextMessageContent event', () {
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(messageId: 'msg-1', delta: 'Hello'),
          );

        expect(thread.textBuffer.currentContent, equals('Hello'));
      });

      test('processes TextMessageEnd event', () {
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(
              messageId: 'msg-1',
              delta: 'Hello, world!',
            ),
          )
          ..processEvent(const TextMessageEndEvent(messageId: 'msg-1'));

        expect(thread.messages, hasLength(1));
        expect(thread.messages.first.text, equals('Hello, world!'));
        expect(thread.textBuffer.isActive, isFalse);
      });

      test('processes full text message cycle', () {
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(
              messageId: 'msg-1',
              delta: 'Hello, ',
            ),
          )
          ..processEvent(
            const TextMessageContentEvent(messageId: 'msg-1', delta: 'world!'),
          )
          ..processEvent(const TextMessageEndEvent(messageId: 'msg-1'));

        expect(thread.messages, hasLength(1));
        expect(thread.messages.first.id, equals('msg-1'));
        expect(thread.messages.first.text, equals('Hello, world!'));
        expect(thread.messages.first.user, equals(ChatUser.assistant));
      });

      test('processes ToolCallStart event', () {
        thread.processEvent(
          const ToolCallStartEvent(
            toolCallId: 'tc-1',
            toolCallName: 'search',
          ),
        );

        expect(thread.toolCallBuffer.isActive('tc-1'), isTrue);
      });

      test('processes ToolCallArgs event', () {
        thread
          ..processEvent(
            const ToolCallStartEvent(
              toolCallId: 'tc-1',
              toolCallName: 'search',
            ),
          )
          ..processEvent(
            const ToolCallArgsEvent(
              toolCallId: 'tc-1',
              delta: '{"query": "test"}',
            ),
          );

        final toolCall = thread.toolCallBuffer.getToolCall('tc-1');
        expect(toolCall?.arguments, equals('{"query": "test"}'));
      });

      test('processes ToolCallEnd event', () {
        thread
          ..processEvent(
            const ToolCallStartEvent(
              toolCallId: 'tc-1',
              toolCallName: 'search',
            ),
          )
          ..processEvent(
            const ToolCallArgsEvent(
              toolCallId: 'tc-1',
              delta: '{"query": "test"}',
            ),
          )
          ..processEvent(const ToolCallEndEvent(toolCallId: 'tc-1'));

        expect(thread.toolCallBuffer.isComplete('tc-1'), isTrue);
      });

      test('processes ToolCallResult event', () {
        thread
          ..processEvent(
            const ToolCallStartEvent(
              toolCallId: 'tc-1',
              toolCallName: 'search',
            ),
          )
          ..processEvent(const ToolCallEndEvent(toolCallId: 'tc-1'))
          ..processEvent(
            const ToolCallResultEvent(
              messageId: 'msg-1',
              toolCallId: 'tc-1',
              content: 'Search results',
            ),
          );

        expect(thread.toolCallBuffer.hasResult('tc-1'), isTrue);
        expect(
          thread.toolCallBuffer.getToolCall('tc-1')?.result,
          equals('Search results'),
        );
      });

      test('processes StateSnapshot event', () {
        thread.processEvent(
          const StateSnapshotEvent(snapshot: {'key': 'value', 'count': 42}),
        );

        expect(thread.state['key'], equals('value'));
        expect(thread.state['count'], equals(42));
      });

      test('processes StateDelta event with add operation', () {
        thread
          ..processEvent(
            const StateSnapshotEvent(snapshot: {'existing': 'data'}),
          )
          ..processEvent(
            const StateDeltaEvent(delta: [
              {'op': 'add', 'path': '/newKey', 'value': 'newValue'},
            ],),
          );

        expect(thread.state['existing'], equals('data'));
        expect(thread.state['newKey'], equals('newValue'));
      });

      test('processes StateDelta event with replace operation', () {
        thread
          ..processEvent(
            const StateSnapshotEvent(snapshot: {'key': 'oldValue'}),
          )
          ..processEvent(
            const StateDeltaEvent(delta: [
              {'op': 'replace', 'path': '/key', 'value': 'newValue'},
            ],),
          );

        expect(thread.state['key'], equals('newValue'));
      });

      test('processes StateDelta event with remove operation', () {
        thread
          ..processEvent(
            const StateSnapshotEvent(
              snapshot: {'keep': 'this', 'remove': 'me'},
            ),
          )
          ..processEvent(
            const StateDeltaEvent(delta: [
              {'op': 'remove', 'path': '/remove'},
            ],),
          );

        expect(thread.state['keep'], equals('this'));
        expect(thread.state.containsKey('remove'), isFalse);
      });

      test('processes nested StateDelta operations', () {
        thread
          ..processEvent(
            const StateSnapshotEvent(snapshot: {}),
          )
          ..processEvent(
            const StateDeltaEvent(delta: [
              {
                'op': 'add',
                'path': '/nested/deep/value',
                'value': 'found',
              },
            ],),
          );

        final nested = thread.state['nested'] as Map<String, dynamic>;
        final deep = nested['deep'] as Map<String, dynamic>;
        expect(deep['value'], equals('found'));
      });

      test('processes MessagesSnapshot event', () {
        // Add initial message
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(messageId: 'msg-1', delta: 'First'),
          )
          ..processEvent(const TextMessageEndEvent(messageId: 'msg-1'));

        expect(thread.messages, hasLength(1));

        // Replace with snapshot
        thread.processEvent(
          const MessagesSnapshotEvent(messages: [
            {'id': 'new-1', 'text': 'New message 1', 'user': 'assistant'},
            {'id': 'new-2', 'text': 'New message 2', 'user': 'user'},
          ],),
        );

        expect(thread.messages, hasLength(2));
        expect(thread.messages[0].id, equals('new-1'));
        expect(thread.messages[1].id, equals('new-2'));
      });

      test('completes pending text message on RunFinished', () {
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(
              messageId: 'msg-1',
              delta: 'Incomplete',
            ),
          )
          // RunFinished should complete the pending message
          ..processEvent(
            const RunFinishedEvent(threadId: 'thread-456', runId: 'run-789'),
          );

        expect(thread.messages, hasLength(1));
        expect(thread.messages.first.text, equals('Incomplete'));
        expect(thread.textBuffer.isActive, isFalse);
      });

      test('completes pending text message on RunError', () {
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(
              messageId: 'msg-1',
              delta: 'Incomplete',
            ),
          )
          ..processEvent(
            const RunErrorEvent(
              threadId: 'thread-456',
              runId: 'run-789',
              message: 'Error occurred',
            ),
          );

        expect(thread.messages, hasLength(1));
        expect(thread.textBuffer.isActive, isFalse);
      });

      test('ignores TextMessageContent when no message active', () {
        // Should not throw
        thread.processEvent(
          const TextMessageContentEvent(
            messageId: 'msg-1',
            delta: 'Orphan content',
          ),
        );

        expect(thread.messages, isEmpty);
      });

      test('ignores TextMessageEnd when no message active', () {
        // Should not throw
        thread.processEvent(const TextMessageEndEvent(messageId: 'msg-1'));

        expect(thread.messages, isEmpty);
      });

      test('ignores ToolCallArgs for unknown tool call', () {
        // Should not throw
        thread.processEvent(
          const ToolCallArgsEvent(
            toolCallId: 'unknown',
            delta: 'args',
          ),
        );
      });

      test('ignores ToolCallEnd for unknown tool call', () {
        // Should not throw
        thread.processEvent(const ToolCallEndEvent(toolCallId: 'unknown'));
      });

      test('ignores ToolCallResult for unknown tool call', () {
        // Should not throw
        thread.processEvent(
          const ToolCallResultEvent(
            messageId: 'msg-1',
            toolCallId: 'unknown',
            content: 'result',
          ),
        );
      });

      test('handles CustomEvent without error', () {
        // Should not throw
        thread.processEvent(
          const CustomEvent(name: 'my_event', data: {'key': 'value'}),
        );

        // No state changes expected
        expect(thread.messages, isEmpty);
        expect(thread.state, isEmpty);
      });

      test('handles UnknownEvent without error', () {
        // Should not throw
        thread.processEvent(
          const UnknownEvent(
            rawType: 'FUTURE_EVENT',
            rawJson: {'type': 'FUTURE_EVENT', 'data': 'test'},
          ),
        );

        // No state changes expected
        expect(thread.messages, isEmpty);
        expect(thread.state, isEmpty);
      });

      test('StateDelta remove on non-existent path does nothing', () {
        thread
          ..processEvent(
            const StateSnapshotEvent(snapshot: {'key': 'value'}),
          )
          // Try to remove from a non-existent nested path
          ..processEvent(
            const StateDeltaEvent(delta: [
              {'op': 'remove', 'path': '/nonexistent/deep/path'},
            ],),
          );

        // Original state unchanged
        expect(thread.state['key'], equals('value'));
        expect(thread.state.containsKey('nonexistent'), isFalse);
      });

      test('MessagesSnapshot handles invalid message JSON gracefully', () {
        thread.processEvent(
          const MessagesSnapshotEvent(messages: [
            {'id': 'msg-1', 'text': 'Valid message'},
            {'invalid': 'no id field'}, // Should be skipped
            {'id': 'msg-2', 'text': 'Another valid'},
          ],),
        );

        // Should have 2 valid messages (invalid one skipped)
        expect(thread.messages.length, greaterThanOrEqualTo(2));
      });

      test('StateDelta remove with deeply nested existing path', () {
        // Set up nested state
        thread
          ..processEvent(
            const StateSnapshotEvent(snapshot: {
              'level1': {
                'level2': {
                  'level3': 'deep value',
                },
              },
            },),
          )
          // Remove the deeply nested value
          ..processEvent(
            const StateDeltaEvent(delta: [
              {'op': 'remove', 'path': '/level1/level2/level3'},
            ],),
          );

        // Verify nested structure exists but value is removed
        expect(thread.state['level1'], isNotNull);
        final level1 = thread.state['level1'] as Map<String, dynamic>;
        expect(level1['level2'], isNotNull);
        final level2 = level1['level2'] as Map<String, dynamic>;
        expect(level2.containsKey('level3'), isFalse);
      });

      test('MessagesSnapshot handles message that throws on parse', () {
        // Pass a message with a field that would cause type cast exception
        thread.processEvent(
          const MessagesSnapshotEvent(messages: [
            {'id': 'msg-1', 'text': 'Valid'},
            {'id': 123, 'text': 'Invalid - id should be string'}, // Type error
            {'id': 'msg-3', 'text': 'Valid'},
          ],),
        );

        // Should skip the invalid message
        expect(thread.messages.length, greaterThanOrEqualTo(2));
      });

      test('MessagesSnapshot defaults to assistant for unknown user type', () {
        thread.processEvent(
          const MessagesSnapshotEvent(messages: [
            {'id': 'msg-1', 'text': 'From unknown', 'user': 'unknown_role'},
          ],),
        );

        expect(thread.messages, hasLength(1));
        expect(thread.messages.first.user, equals(ChatUser.assistant));
      });
    });

    group('run', () {
      Stream<List<int>> createSSEStream(List<Map<String, dynamic>> events) {
        return Stream.fromIterable(
          events.map((e) => utf8.encode('data: ${jsonEncode(e)}\n\n')),
        );
      }

      test('streams events from SSE', () async {
        when(
          () => mockTransport.requestStream(
            any(),
            any(),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            cancelToken: any(named: 'cancelToken'),
          ),
        ).thenAnswer(
          (_) => createSSEStream([
            {'type': 'RUN_STARTED', 'thread_id': 'thread-456', 'run_id': 'r1'},
            {'type': 'TEXT_MESSAGE_START', 'message_id': 'msg-1'},
            {
              'type': 'TEXT_MESSAGE_CONTENT',
              'message_id': 'msg-1',
              'delta': 'Hi',
            },
            {'type': 'TEXT_MESSAGE_END', 'message_id': 'msg-1'},
            {'type': 'RUN_FINISHED', 'thread_id': 'thread-456', 'run_id': 'r1'},
          ]),
        );

        final events = await thread
            .run(runId: 'r1', userMessage: 'Hello')
            .toList();

        expect(events, hasLength(5));
        expect(events[0], isA<RunStartedEvent>());
        expect(events[4], isA<RunFinishedEvent>());
        expect(thread.messages, hasLength(1));
        expect(thread.messages.first.text, equals('Hi'));
        expect(thread.runStatus, equals(ThreadRunStatus.finished));
      });

      test('sets runStatus to running during execution', () async {
        final completer = Completer<void>();

        when(
          () => mockTransport.requestStream(
            any(),
            any(),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            cancelToken: any(named: 'cancelToken'),
          ),
        ).thenAnswer(
          (_) async* {
            yield utf8.encode(
              'data: {"type": "RUN_STARTED", '
              '"thread_id": "t", "run_id": "r"}\n\n',
            );
            await completer.future;
          },
        );

        var runningDuringStream = false;
        unawaited(
          thread.run(runId: 'r1', userMessage: 'Hello').forEach((event) {
            if (thread.isRunning) {
              runningDuringStream = true;
            }
          }),
        );

        // Give time for stream to start
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(thread.isRunning, isTrue);

        completer.complete();
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(runningDuringStream, isTrue);
      });

      test('sets runStatus to error on RunErrorEvent', () async {
        when(
          () => mockTransport.requestStream(
            any(),
            any(),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            cancelToken: any(named: 'cancelToken'),
          ),
        ).thenAnswer(
          (_) => createSSEStream([
            {'type': 'RUN_STARTED', 'thread_id': 't', 'run_id': 'r'},
            {
              'type': 'RUN_ERROR',
              'thread_id': 't',
              'run_id': 'r',
              'message': 'Something failed',
            },
          ]),
        );

        await thread.run(runId: 'r1', userMessage: 'Hello').toList();

        expect(thread.runStatus, equals(ThreadRunStatus.error));
        expect(thread.errorMessage, equals('Something failed'));
      });

      test('sets runStatus to error on stream exception', () async {
        when(
          () => mockTransport.requestStream(
            any(),
            any(),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            cancelToken: any(named: 'cancelToken'),
          ),
        ).thenAnswer(
          (_) async* {
            yield utf8.encode(
              'data: {"type": "RUN_STARTED", '
              '"thread_id": "t", "run_id": "r"}\n\n',
            );
            throw Exception('Network error');
          },
        );

        expect(
          () => thread.run(runId: 'r1', userMessage: 'Hello').toList(),
          throwsException,
        );

        // Wait for exception to be handled
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(thread.runStatus, equals(ThreadRunStatus.error));
      });

      test('handles SSE with [DONE] marker', () async {
        when(
          () => mockTransport.requestStream(
            any(),
            any(),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            cancelToken: any(named: 'cancelToken'),
          ),
        ).thenAnswer(
          (_) => Stream.fromIterable([
            utf8.encode(
              'data: {"type": "RUN_STARTED", '
              '"thread_id": "t", "run_id": "r"}\n\n',
            ),
            utf8.encode('data: [DONE]\n\n'),
          ]),
        );

        final events = await thread
            .run(runId: 'r1', userMessage: 'Hello')
            .toList();

        // Should only get RUN_STARTED, [DONE] is ignored
        expect(events, hasLength(1));
      });

      test('sends correct request to transport', () async {
        Uri? capturedUri;
        Object? capturedBody;
        Map<String, String>? capturedHeaders;

        when(
          () => mockTransport.requestStream(
            any(),
            any(),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            cancelToken: any(named: 'cancelToken'),
          ),
        ).thenAnswer((invocation) {
          capturedUri = invocation.positionalArguments[1] as Uri;
          capturedBody = invocation.namedArguments[#body];
          capturedHeaders =
              invocation.namedArguments[#headers] as Map<String, String>?;
          return const Stream.empty();
        });

        await thread
            .run(
              runId: 'run-123',
              userMessage: 'Test message',
              initialState: {'key': 'value'},
            )
            .toList();

        expect(
          capturedUri?.path,
          equals('/api/v1/rooms/room-123/agui/thread-456/run-123'),
        );
        expect(capturedBody, isA<Map<String, dynamic>>());
        final body = capturedBody! as Map<String, dynamic>;
        expect(body['message'], equals('Test message'));
        expect(body['state'], equals({'key': 'value'}));
        expect(capturedHeaders?['Accept'], equals('text/event-stream'));
      });
    });

    group('with ToolRegistry', () {
      test('executes registered tool on ToolCallEnd', () async {
        var toolExecuted = false;
        ToolCallInfo? receivedCall;

        final registry = ToolRegistry()
          ..register(
            name: 'test_tool',
            executor: (call) async {
              toolExecuted = true;
              receivedCall = call;
              return 'Tool result';
            },
          );

        Thread(
          transport: mockTransport,
          roomId: 'room-123',
          threadId: 'thread-456',
          toolRegistry: registry,
        )
          ..processEvent(
            const ToolCallStartEvent(
              toolCallId: 'tc-1',
              toolCallName: 'test_tool',
            ),
          )
          ..processEvent(
            const ToolCallArgsEvent(
              toolCallId: 'tc-1',
              delta: '{"arg": "value"}',
            ),
          )
          ..processEvent(
            const ToolCallEndEvent(toolCallId: 'tc-1'),
          );

        // Wait for async execution
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(toolExecuted, isTrue);
        expect(receivedCall?.name, equals('test_tool'));
        expect(receivedCall?.arguments, equals('{"arg": "value"}'));
      });

      test('does not execute unregistered tool', () async {
        var toolExecuted = false;

        final registry = ToolRegistry()
          ..register(
            name: 'other_tool',
            executor: (_) async {
              toolExecuted = true;
              return 'result';
            },
          );

        Thread(
          transport: mockTransport,
          roomId: 'room-123',
          threadId: 'thread-456',
          toolRegistry: registry,
        )
          ..processEvent(
            const ToolCallStartEvent(
              toolCallId: 'tc-1',
              toolCallName: 'unregistered_tool',
            ),
          )
          ..processEvent(
            const ToolCallEndEvent(toolCallId: 'tc-1'),
          );

        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(toolExecuted, isFalse);
      });
    });

    group('reset', () {
      test('clears all state', () {
        // Set up some state
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(
              messageId: 'msg-1',
              delta: 'content',
            ),
          )
          ..processEvent(const TextMessageEndEvent(messageId: 'msg-1'))
          ..processEvent(
            const StateSnapshotEvent(snapshot: {'key': 'value'}),
          );

        expect(thread.messages, isNotEmpty);
        expect(thread.state, isNotEmpty);

        thread.reset();

        expect(thread.messages, isEmpty);
        expect(thread.state, isEmpty);
        expect(thread.textBuffer.isActive, isFalse);
        expect(thread.toolCallBuffer.activeCount, equals(0));
        expect(thread.runStatus, equals(ThreadRunStatus.idle));
        expect(thread.runId, isNull);
        expect(thread.errorMessage, isNull);
      });
    });

    group('messages immutability', () {
      test('messages list is unmodifiable', () {
        thread
          ..processEvent(
            const TextMessageStartEvent(messageId: 'msg-1'),
          )
          ..processEvent(
            const TextMessageContentEvent(messageId: 'msg-1', delta: 'test'),
          )
          ..processEvent(const TextMessageEndEvent(messageId: 'msg-1'));

        expect(
          () => thread.messages.add(
            ChatMessage.text(user: ChatUser.user, text: 'test'),
          ),
          throwsUnsupportedError,
        );
      });
    });

    group('state immutability', () {
      test('state map is unmodifiable', () {
        thread.processEvent(
          const StateSnapshotEvent(snapshot: {'key': 'value'}),
        );

        expect(
          () => thread.state['new_key'] = 'new_value',
          throwsUnsupportedError,
        );
      });
    });
  });
}
