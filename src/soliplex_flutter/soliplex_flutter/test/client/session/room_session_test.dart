import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:soliplex_flutter/client/models/chat_message.dart';
import 'package:soliplex_flutter/client/session/room_session.dart';
import 'package:soliplex_flutter/client/utils/cancel_token.dart';
import 'package:test/test.dart';

void main() {
  late ag_ui.AgUiClient mockClient;

  setUp(() {
    mockClient = ag_ui.AgUiClient(
      config: ag_ui.AgUiClientConfig(
        baseUrl: 'http://localhost:8000',
        defaultHeaders: {},
      ),
    );
  });

  group('RoomSession', () {
    test('creates with required fields', () {
      final session = RoomSession(
        roomId: 'room1',
        baseUrl: 'http://localhost:8000',
        agUiClient: mockClient,
      );

      expect(session.roomId, equals('room1'));
      expect(session.baseUrl, equals('http://localhost:8000'));
      expect(session.state, equals(SessionState.active));
      expect(session.threadId, isNull);
      expect(session.activeRunId, isNull);
      expect(session.isStreaming, isFalse);
      expect(session.messages, isEmpty);
    });

    group('initializeThread', () {
      test('creates thread with ID', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.initializeThread('thread1');

        expect(session.threadId, equals('thread1'));
        expect(session.thread, isNotNull);
      });
    });

    group('addUserMessage', () {
      test('adds user message to list', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.addUserMessage('Hello');

        expect(session.messages, hasLength(1));
        expect(session.messages.first.text, equals('Hello'));
        expect(session.messages.first.user, equals(ChatUser.user));
      });

      test('emits message update', () async {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messages = <List<ChatMessage>>[];
        session.messageStream.listen(messages.add);

        session.addUserMessage('Hello');

        await Future.delayed(Duration.zero);
        expect(messages, hasLength(1));
      });

      test('calls onContextUpdate callback', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        String? contextType;
        String? contextSummary;
        session.onContextUpdate = (type, {summary, data}) {
          contextType = type;
          contextSummary = summary;
        };

        session.addUserMessage('Hello');

        expect(contextType, equals('userMessage'));
        expect(contextSummary, equals('Hello'));
      });
    });

    group('startAgentMessage', () {
      test('creates streaming assistant message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.startAgentMessage();

        expect(session.messages, hasLength(1));
        expect(session.messages.first.id, equals(messageId));
        expect(session.messages.first.user, equals(ChatUser.assistant));
        expect(session.messages.first.isStreaming, isTrue);
        expect(session.messages.first.text, equals(''));
      });
    });

    group('appendToMessage', () {
      test('appends text to existing message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.startAgentMessage();
        session.appendToMessage(messageId, 'Hello');
        session.appendToMessage(messageId, ' World');

        expect(session.messages.first.text, equals('Hello World'));
      });

      test('does nothing for non-existent message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        // Should not throw
        session.appendToMessage('nonexistent', 'text');

        expect(session.messages, isEmpty);
      });
    });

    group('finalizeMessage', () {
      test('stops streaming for message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.startAgentMessage();
        expect(session.messages.first.isStreaming, isTrue);

        session.finalizeMessage(messageId);

        expect(session.messages.first.isStreaming, isFalse);
      });

      test('does nothing for non-existent message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        // Should not throw
        session.finalizeMessage('nonexistent');
      });
    });

    group('addErrorMessage', () {
      test('adds error message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.addErrorMessage('Something went wrong');

        expect(session.messages, hasLength(1));
        expect(session.messages.first.type, equals(MessageType.error));
        expect(session.messages.first.errorMessage, equals('Something went wrong'));
      });

      test('adds error message with code', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.addErrorMessage('Unauthorized', errorCode: '401');

        expect(session.messages.first.errorMessage, equals('[401] Unauthorized'));
      });
    });

    group('thinking', () {
      test('startThinking enables thinking for message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.startAgentMessage();
        session.startThinking(messageId);

        expect(session.messages.first.isThinkingStreaming, isTrue);
        expect(session.messages.first.thinkingText, equals(''));
      });

      test('appendThinking adds thinking text', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.startAgentMessage();
        session.startThinking(messageId);
        session.appendThinking(messageId, 'Thinking...');

        expect(session.messages.first.thinkingText, equals('Thinking...'));
      });

      test('finalizeThinking stops thinking streaming', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.startAgentMessage();
        session.startThinking(messageId);
        session.finalizeThinking(messageId);

        expect(session.messages.first.isThinkingStreaming, isFalse);
      });
    });

    group('tool calls', () {
      test('addToolCallMessage creates tool call message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.addToolCallMessage('search');

        expect(session.messages, hasLength(1));
        expect(session.messages.first.type, equals(MessageType.toolCall));
        expect(session.messages.first.id, equals(messageId));
        expect(session.messages.first.toolCalls, hasLength(1));
        expect(session.messages.first.toolCalls!.first.name, equals('search'));
      });

      test('updateToolCallStatus updates status to completed', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.addToolCallMessage('search');
        session.updateToolCallStatus(messageId, 'completed');

        expect(
          session.messages.first.toolCalls!.first.status,
          equals(ToolCallStatus.completed),
        );
      });

      test('updateToolCallStatus updates status to failed', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.addToolCallMessage('search');
        session.updateToolCallStatus(messageId, 'error: something');

        expect(
          session.messages.first.toolCalls!.first.status,
          equals(ToolCallStatus.failed),
        );
      });

      test('updateToolCallStatus updates status to executing', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final messageId = session.addToolCallMessage('search');
        session.updateToolCallStatus(messageId, 'running');

        expect(
          session.messages.first.toolCalls!.first.status,
          equals(ToolCallStatus.executing),
        );
      });
    });

    group('processEvent', () {
      test('RunStartedEvent sets streaming state', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.processEvent(ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'));

        expect(session.state, equals(SessionState.streaming));
        expect(session.isStreaming, isTrue);
      });

      test('RunStartedEvent calls onActivityUpdate', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        bool? isActive;
        session.onActivityUpdate = (active) => isActive = active;

        session.processEvent(ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'));

        expect(isActive, isTrue);
      });

      test('TextMessageStartEvent creates agent message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.processEvent(ag_ui.TextMessageStartEvent(messageId: 'msg1'));

        expect(session.messages, hasLength(1));
        expect(session.messages.first.user, equals(ChatUser.assistant));
        expect(session.messages.first.isStreaming, isTrue);
      });

      test('TextMessageContentEvent appends content', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.processEvent(ag_ui.TextMessageStartEvent(messageId: 'msg1'));
        session.processEvent(
          ag_ui.TextMessageContentEvent(messageId: 'msg1', delta: 'Hello'),
        );
        session.processEvent(
          ag_ui.TextMessageContentEvent(messageId: 'msg1', delta: ' World'),
        );

        expect(session.messages.first.text, equals('Hello World'));
      });

      test('TextMessageEndEvent finalizes message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.processEvent(ag_ui.TextMessageStartEvent(messageId: 'msg1'));
        session.processEvent(ag_ui.TextMessageEndEvent(messageId: 'msg1'));

        expect(session.messages.first.isStreaming, isFalse);
      });

      test('RunFinishedEvent resets state', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.processEvent(ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'));
        expect(session.isStreaming, isTrue);

        session.processEvent(ag_ui.RunFinishedEvent(threadId: 't1', runId: 'r1'));

        expect(session.state, equals(SessionState.active));
        expect(session.isStreaming, isFalse);
      });

      test('RunErrorEvent adds error message', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.processEvent(ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'));
        session.processEvent(
          ag_ui.RunErrorEvent(message: 'Error occurred', code: 'ERR001'),
        );

        expect(session.messages.last.type, equals(MessageType.error));
        expect(session.messages.last.errorMessage, contains('Error occurred'));
        expect(session.state, equals(SessionState.active));
      });

      test('StateSnapshotEvent calls canvas callback', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        Map<String, dynamic>? canvasData;
        session.onCanvasUpdate = (data) => canvasData = data;

        session.processEvent(
          ag_ui.StateSnapshotEvent(snapshot: {'key': 'value'}),
        );

        expect(canvasData, equals({'key': 'value'}));
      });

      test('ThinkingTextMessageStartEvent with pending thinking', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        // Start thinking before any message
        session.processEvent(ag_ui.ThinkingTextMessageStartEvent());
        session.processEvent(ag_ui.ThinkingTextMessageContentEvent(delta: 'Hmm'));
        session.processEvent(ag_ui.ThinkingTextMessageEndEvent());

        // Now start a message - should apply pending thinking
        session.processEvent(ag_ui.TextMessageStartEvent(messageId: 'msg1'));

        expect(session.messages.first.thinkingText, equals('Hmm'));
        expect(session.messages.first.isThinkingStreaming, isFalse);
      });
    });

    group('deduplication', () {
      test('markToolCallProcessed returns true first time', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        expect(session.markToolCallProcessed('tc1'), isTrue);
      });

      test('markToolCallProcessed returns false second time', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.markToolCallProcessed('tc1');
        expect(session.markToolCallProcessed('tc1'), isFalse);
      });

      test('markToolNotificationProcessed returns true first time', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        expect(session.markToolNotificationProcessed('key1'), isTrue);
      });
    });

    group('handleLocalToolExecution', () {
      test('creates tool call message on executing status', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.handleLocalToolExecution('tc1', 'search', 'executing');

        expect(session.messages, hasLength(1));
        expect(session.messages.first.type, equals(MessageType.toolCall));
      });

      test('updates status on completed', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.handleLocalToolExecution('tc1', 'search', 'executing');
        session.handleLocalToolExecution('tc1', 'search', 'completed');

        expect(
          session.messages.first.toolCalls!.first.status,
          equals(ToolCallStatus.completed),
        );
      });

      test('deduplicates notifications', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.handleLocalToolExecution('tc1', 'search', 'executing');
        session.handleLocalToolExecution('tc1', 'search', 'executing');

        expect(session.messages, hasLength(1));
      });
    });

    group('cancel token', () {
      test('setCancelToken and cancel', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        final token = CancelToken();
        session.setCancelToken(token);

        expect(token.isCancelled, isFalse);

        session.cancel('User cancelled');

        expect(token.isCancelled, isTrue);
      });
    });

    group('suspend and resume', () {
      test('suspend sets suspended state', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.suspend();

        expect(session.state, equals(SessionState.suspended));
      });

      test('resume from suspended state', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.suspend();
        session.resume();

        expect(session.state, equals(SessionState.active));
      });

      test('resume does nothing if not suspended', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.resume();

        expect(session.state, equals(SessionState.active));
      });
    });

    group('dispose', () {
      test('cleans up resources', () {
        final session = RoomSession(
          roomId: 'room1',
          baseUrl: 'http://localhost:8000',
          agUiClient: mockClient,
        );

        session.addUserMessage('test');
        session.dispose();

        expect(session.state, equals(SessionState.disposed));
        expect(session.messages, isEmpty);
      });
    });

    test('toString includes key info', () {
      final session = RoomSession(
        roomId: 'room1',
        baseUrl: 'http://localhost:8000',
        agUiClient: mockClient,
      );

      final str = session.toString();

      expect(str, contains('room1'));
    });
  });
}
