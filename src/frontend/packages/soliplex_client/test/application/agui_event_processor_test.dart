import 'package:ag_ui/ag_ui.dart';
import 'package:soliplex_client/src/application/agui_event_processor.dart';
import 'package:soliplex_client/src/application/streaming_state.dart'
    as app_streaming;
import 'package:soliplex_client/src/domain/chat_message.dart';
import 'package:soliplex_client/src/domain/conversation.dart';
import 'package:test/test.dart';

void main() {
  group('processEvent', () {
    late Conversation conversation;
    late app_streaming.StreamingState streaming;

    setUp(() {
      conversation = Conversation.empty(threadId: 'thread-1');
      streaming = const app_streaming.NotStreaming();
    });

    group('run lifecycle events', () {
      test('RunStartedEvent sets status to Running', () {
        const event = RunStartedEvent(
          threadId: 'thread-1',
          runId: 'run-1',
        );

        final result = processEvent(conversation, streaming, event);

        expect(result.conversation.status, isA<Running>());
        expect((result.conversation.status as Running).runId, equals('run-1'));
        expect(result.streaming, isA<app_streaming.NotStreaming>());
      });

      test('RunFinishedEvent sets status to Completed', () {
        final runningConversation = conversation.withStatus(
          const Running(runId: 'run-1'),
        );
        const event = RunFinishedEvent(
          threadId: 'thread-1',
          runId: 'run-1',
        );

        final result = processEvent(runningConversation, streaming, event);

        expect(result.conversation.status, isA<Completed>());
        expect(result.streaming, isA<app_streaming.NotStreaming>());
      });

      test('RunErrorEvent sets status to Failed with message', () {
        final runningConversation = conversation.withStatus(
          const Running(runId: 'run-1'),
        );
        const event = RunErrorEvent(
          message: 'Something went wrong',
          code: 'ERROR_CODE',
        );

        final result = processEvent(runningConversation, streaming, event);

        expect(result.conversation.status, isA<Failed>());
        expect(
          (result.conversation.status as Failed).error,
          equals('Something went wrong'),
        );
        expect(result.streaming, isA<app_streaming.NotStreaming>());
      });
    });

    group('text message streaming', () {
      test('TextMessageStartEvent begins streaming', () {
        const event = TextMessageStartEvent(messageId: 'msg-1');

        final result = processEvent(conversation, streaming, event);

        expect(result.streaming, isA<app_streaming.Streaming>());
        final streamingState = result.streaming as app_streaming.Streaming;
        expect(streamingState.messageId, equals('msg-1'));
        expect(streamingState.text, isEmpty);
      });

      test('TextMessageContentEvent is ignored when NotStreaming', () {
        const event = TextMessageContentEvent(
          messageId: 'msg-1',
          delta: 'Hello',
        );

        final result = processEvent(conversation, streaming, event);

        expect(result.streaming, isA<app_streaming.NotStreaming>());
        expect(result.conversation.messages, isEmpty);
      });

      test('TextMessageContentEvent appends delta to streaming text', () {
        const streamingState = app_streaming.Streaming(
          messageId: 'msg-1',
          text: 'Hello',
        );
        const event = TextMessageContentEvent(
          messageId: 'msg-1',
          delta: ' world',
        );

        final result = processEvent(conversation, streamingState, event);

        expect(result.streaming, isA<app_streaming.Streaming>());
        final newStreaming = result.streaming as app_streaming.Streaming;
        expect(newStreaming.messageId, equals('msg-1'));
        expect(newStreaming.text, equals('Hello world'));
      });

      test(
        'TextMessageContentEvent ignores delta if messageId does not match',
        () {
          const streamingState = app_streaming.Streaming(
            messageId: 'msg-1',
            text: 'Hello',
          );
          const event = TextMessageContentEvent(
            messageId: 'msg-other',
            delta: ' world',
          );

          final result = processEvent(conversation, streamingState, event);

          expect(result.streaming, equals(streamingState));
        },
      );

      test('TextMessageEndEvent finalizes message and resets streaming', () {
        const streamingState = app_streaming.Streaming(
          messageId: 'msg-1',
          text: 'Hello world',
        );
        const event = TextMessageEndEvent(messageId: 'msg-1');

        final result = processEvent(conversation, streamingState, event);

        expect(result.streaming, isA<app_streaming.NotStreaming>());
        expect(result.conversation.messages, hasLength(1));
        final message = result.conversation.messages.first;
        expect(message.id, equals('msg-1'));
      });

      test(
        'TextMessageEndEvent ignores if messageId does not match streaming',
        () {
          const streamingState = app_streaming.Streaming(
            messageId: 'msg-1',
            text: 'Hello',
          );
          const event = TextMessageEndEvent(messageId: 'msg-other');

          final result = processEvent(conversation, streamingState, event);

          expect(result.streaming, equals(streamingState));
          expect(result.conversation.messages, isEmpty);
        },
      );
    });

    group('tool call events', () {
      test('ToolCallStartEvent adds tool call to conversation', () {
        const event = ToolCallStartEvent(
          toolCallId: 'tool-1',
          toolCallName: 'search',
        );

        final result = processEvent(conversation, streaming, event);

        expect(result.conversation.toolCalls, hasLength(1));
        expect(result.conversation.toolCalls.first.id, equals('tool-1'));
        expect(result.conversation.toolCalls.first.name, equals('search'));
      });

      test('ToolCallEndEvent removes tool call from active list', () {
        final conversationWithTool = conversation.withToolCall(
          const ToolCallInfo(id: 'tool-1', name: 'search'),
        );
        const event = ToolCallEndEvent(toolCallId: 'tool-1');

        final result = processEvent(conversationWithTool, streaming, event);

        expect(result.conversation.toolCalls, isEmpty);
      });
    });

    group('passthrough events', () {
      test('StateSnapshotEvent passes through unchanged', () {
        const event = StateSnapshotEvent(snapshot: {'key': 'value'});

        final result = processEvent(conversation, streaming, event);

        expect(result.conversation, equals(conversation));
        expect(result.streaming, equals(streaming));
      });

      test('CustomEvent passes through unchanged', () {
        const event = CustomEvent(name: 'custom', value: {'data': 123});

        final result = processEvent(conversation, streaming, event);

        expect(result.conversation, equals(conversation));
        expect(result.streaming, equals(streaming));
      });
    });
  });
}
