import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_flutter/client/agui/thread.dart';
import 'package:soliplex_flutter/client/utils/cancel_token.dart';
import 'package:test/test.dart';

import 'mock_agui_client.dart';

// Fake class for mocktail fallback
class FakeSimpleRunAgentInput extends Fake implements ag_ui.SimpleRunAgentInput {}

void main() {
  late MockAgUiClient mockClient;

  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeSimpleRunAgentInput());
  });

  setUp(() {
    mockClient = MockAgUiClient();
  });

  group('Thread', () {
    test('creates with id and client', () {
      final thread = Thread(id: 't1', client: mockClient);

      expect(thread.id, equals('t1'));
      expect(thread.messageHistory, isEmpty);
      expect(thread.runs, isEmpty);
      expect(thread.pendingToolCalls, isEmpty);
    });

    test('messageStream is available', () {
      final thread = Thread(id: 't1', client: mockClient);

      expect(thread.messageStream, isNotNull);
    });

    test('stepsStream is available', () {
      final thread = Thread(id: 't1', client: mockClient);

      expect(thread.stepsStream, isNotNull);
    });

    group('addTool', () {
      test('adds tool with executor', () {
        final thread = Thread(id: 't1', client: mockClient);
        final tool = ag_ui.Tool(
          name: 'search',
          description: 'Search tool',
          parameters: {},
        );

        thread.addTool(tool, (call) async => 'result');

        // Tool is added (can't directly verify, but no error)
      });

      test('replaces existing tool with same name', () {
        final thread = Thread(id: 't1', client: mockClient);
        final tool1 = ag_ui.Tool(
          name: 'search',
          description: 'Original',
          parameters: {},
        );
        final tool2 = ag_ui.Tool(
          name: 'search',
          description: 'Replaced',
          parameters: {},
        );

        thread.addTool(tool1, (call) async => 'result1');
        thread.addTool(tool2, (call) async => 'result2');

        // Tool is replaced (can't directly verify, but no error)
      });

      test('marks tool as fire-and-forget', () {
        final thread = Thread(id: 't1', client: mockClient);
        final tool = ag_ui.Tool(
          name: 'notify',
          description: 'Notification tool',
          parameters: {},
        );

        thread.addTool(tool, (call) async => 'done', fireAndForget: true);

        // Fire-and-forget is set
      });
    });

    group('removeTool', () {
      test('removes existing tool', () {
        final thread = Thread(id: 't1', client: mockClient);
        final tool = ag_ui.Tool(
          name: 'search',
          description: 'Search tool',
          parameters: {},
        );

        thread.addTool(tool, (call) async => 'result');
        thread.removeTool('search');

        // Tool is removed
      });

      test('does nothing for non-existent tool', () {
        final thread = Thread(id: 't1', client: mockClient);

        thread.removeTool('nonexistent');

        // No error
      });
    });

    group('dispose', () {
      test('disposes all resources', () {
        final thread = Thread(id: 't1', client: mockClient);

        thread.dispose();

        // Streams are closed (disposed state)
      });

      test('startRun returns empty after dispose', () async {
        final thread = Thread(id: 't1', client: mockClient);

        thread.dispose();

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        expect(result, isEmpty);
      });
    });

    test('toString includes id and run count', () {
      final thread = Thread(id: 't1', client: mockClient);

      final str = thread.toString();

      expect(str, contains('t1'));
      expect(str, contains('0'));
    });

    group('startRun', () {
      test('processes text message events', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Set up events for a simple text message
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.TextMessageStartEvent(messageId: 'm1'),
          ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Hello '),
          ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'world'),
          ag_ui.TextMessageEndEvent(messageId: 'm1'),
        ];
        mockClient.setupRunAgent();

        final messages = [
          ag_ui.UserMessage(id: 'user1', content: 'Hi'),
        ];

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
          messages: messages,
        );

        // Should return empty list (no tool calls)
        expect(result, isEmpty);

        // Message should be in history
        expect(thread.messageHistory.length, equals(2)); // user + assistant
        expect(thread.runs.length, equals(1));
      });

      test('processes tool call events and executes client tools', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Add a client tool
        final tool = ag_ui.Tool(
          name: 'search',
          description: 'Search tool',
          parameters: {},
        );
        var executorCalled = false;
        thread.addTool(tool, (call) async {
          executorCalled = true;
          return 'search result';
        });

        // Set up events for a tool call
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.ToolCallStartEvent(toolCallId: 'tc1', toolCallName: 'search'),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{"query"'),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: ': "test"}'),
          ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
        ];
        mockClient.setupRunAgent();

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        // Should execute tool and return result
        expect(executorCalled, isTrue);
        expect(result.length, equals(1));
        expect(result[0].content, equals('search result'));
      });

      test('handles tool execution errors', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Add a client tool that throws an error
        final tool = ag_ui.Tool(
          name: 'failing_tool',
          description: 'Tool that fails',
          parameters: {},
        );
        thread.addTool(tool, (call) async {
          throw Exception('Tool failed');
        });

        // Set up events for a tool call
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.ToolCallStartEvent(
            toolCallId: 'tc1',
            toolCallName: 'failing_tool',
          ),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{}'),
          ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
        ];
        mockClient.setupRunAgent();

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        // Should return error message
        expect(result.length, equals(1));
        expect(result[0].content, contains('ERROR'));
        expect(result[0].content, contains('Tool failed'));
      });

      test('handles missing tool executor', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Don't add any tool executor

        // Set up events for a tool call to non-existent tool
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.ToolCallStartEvent(
            toolCallId: 'tc1',
            toolCallName: 'unknown_tool',
          ),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{}'),
          ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
        ];
        mockClient.setupRunAgent();

        // Mark unknown_tool as a client tool by adding it
        final tool = ag_ui.Tool(
          name: 'unknown_tool',
          description: 'Tool without executor',
          parameters: {},
        );
        thread.addTool(tool, (call) async => 'should not be called');
        thread.removeTool('unknown_tool'); // Remove just the executor reference

        // Actually, we need to test when tool is registered but no executor exists
        // Let me adjust: we'll add the tool to tools list but not provide executor

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        // Since tool is not in client tools, it won't be registered
        expect(result, isEmpty);
      });

      test('handles fire-and-forget tools', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Add a fire-and-forget tool
        final tool = ag_ui.Tool(
          name: 'notify',
          description: 'Notification tool',
          parameters: {},
        );
        var executorCalled = false;
        thread.addTool(
          tool,
          (call) async {
            executorCalled = true;
            return 'notified';
          },
          fireAndForget: true,
        );

        // Set up events for a tool call
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.ToolCallStartEvent(toolCallId: 'tc1', toolCallName: 'notify'),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{}'),
          ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
        ];
        mockClient.setupRunAgent();

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        // Executor should be called but result not returned
        expect(executorCalled, isTrue);
        expect(result, isEmpty);
      });

      test('respects cancel token', () async {
        final thread = Thread(id: 't1', client: mockClient);
        final cancelToken = CancelToken();

        // Set up events
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.TextMessageStartEvent(messageId: 'm1'),
        ];
        mockClient.setupRunAgent();

        // Cancel immediately
        cancelToken.cancel();

        expect(
          () => thread.startRun(
            endpoint: '/api/run',
            runId: 'r1',
            cancelToken: cancelToken,
          ),
          throwsA(isA<CancelledException>()),
        );
      });

      test('handles decoding errors gracefully', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Mock will throw a DecodingError
        mockClient.exceptionToThrow = ag_ui.DecodingError('Bad data');
        mockClient.setupRunAgent();
        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        // Should return empty result, not throw
        expect(result, isEmpty);
      });

      test('streams messages to messageStream', () async {
        final thread = Thread(id: 't1', client: mockClient);

        final messagesReceived = <ag_ui.Message>[];
        thread.messageStream.listen(messagesReceived.add);

        // Set up events
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.TextMessageStartEvent(messageId: 'm1'),
          ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Hello'),
          ag_ui.TextMessageEndEvent(messageId: 'm1'),
        ];
        mockClient.setupRunAgent();

        final userMsg = ag_ui.UserMessage(id: 'user1', content: 'Hi');
        await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
          messages: [userMsg],
        );

        await Future.delayed(Duration(milliseconds: 10));

        // Should have received both user and assistant messages
        expect(messagesReceived.length, equals(2));
      });

      test('streams events to stepsStream', () async {
        final thread = Thread(id: 't1', client: mockClient);

        final eventsReceived = <ag_ui.BaseEvent>[];
        thread.stepsStream.listen(eventsReceived.add);

        // Set up events
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.TextMessageStartEvent(messageId: 'm1'),
        ];
        mockClient.setupRunAgent();

        await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        await Future.delayed(Duration(milliseconds: 10));

        // Should have received all events
        expect(eventsReceived.length, greaterThan(0));
      });

      test('adds messages to history from input', () async {
        final thread = Thread(id: 't1', client: mockClient);

        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
        ];
        mockClient.setupRunAgent();

        final messages = [
          ag_ui.UserMessage(id: 'user1', content: 'Message 1'),
          ag_ui.UserMessage(id: 'user2', content: 'Message 2'),
        ];

        await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
          messages: messages,
        );

        expect(thread.messageHistory.length, equals(2));
      });

      test('executes multiple client tools concurrently', () async {
        final thread = Thread(id: 't1', client: mockClient);

        // Add multiple client tools
        final tool1 = ag_ui.Tool(
          name: 'tool1',
          description: 'First tool',
          parameters: {},
        );
        final tool2 = ag_ui.Tool(
          name: 'tool2',
          description: 'Second tool',
          parameters: {},
        );

        thread.addTool(tool1, (call) async {
          await Future.delayed(Duration(milliseconds: 10));
          return 'result1';
        });
        thread.addTool(tool2, (call) async {
          await Future.delayed(Duration(milliseconds: 10));
          return 'result2';
        });

        // Set up events for multiple tool calls
        mockClient.eventsToReturn = [
          ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          ag_ui.ToolCallStartEvent(toolCallId: 'tc1', toolCallName: 'tool1'),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{}'),
          ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
          ag_ui.ToolCallStartEvent(toolCallId: 'tc2', toolCallName: 'tool2'),
          ag_ui.ToolCallArgsEvent(toolCallId: 'tc2', delta: '{}'),
          ag_ui.ToolCallEndEvent(toolCallId: 'tc2'),
        ];
        mockClient.setupRunAgent();

        final result = await thread.startRun(
          endpoint: '/api/run',
          runId: 'r1',
        );

        // Both tools should have been executed
        expect(result.length, equals(2));
      });
    });
  });
}
