import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/event_processor.dart';
import 'package:soliplex/core/protocol/agui_event_types.dart'; // Import AgUiEventTypes

void main() {
  late EventProcessor processor;
  late EventProcessingState emptyState;

  setUp(() {
    processor = const EventProcessor();
    emptyState = EventProcessingState.empty();
  });

  group('EventProcessor', () {
    group('RunStartedEvent', () {
      test('clears thinking buffer and emits activity update', () {
        const event = ag_ui.RunStartedEvent(
          threadId: 'thread-1',
          runId: 'run-123',
        );

        final result = processor.process(emptyState, event);

        expect(result.thinkingBufferUpdate, isNotNull);
        expect(result.thinkingBufferUpdate!.isBuffering, isFalse);
        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.runStarted),
        );
        expect(result.contextUpdate?.summary, equals('run-123'));
        expect(result.activityUpdate?.isActive, isTrue);
      });

      test('sets clearDeduplication flag to clear tool call state', () {
        const event = ag_ui.RunStartedEvent(
          threadId: 'thread-1',
          runId: 'run-456',
        );

        final result = processor.process(emptyState, event);

        expect(result.clearDeduplication, isTrue);
        expect(result.hasChanges, isTrue);
      });
    });

    group('TextMessageStartEvent', () {
      test('creates new streaming message', () {
        const event = ag_ui.TextMessageStartEvent(messageId: 'agui-msg-1');

        final result = processor.process(emptyState, event);

        // Should add a new message
        expect(result.messageMutations.length, greaterThanOrEqualTo(1));
        final addMutation = result.messageMutations.first as AddMessage;
        expect(addMutation.message.isStreaming, isTrue);
        expect(addMutation.message.user.id, equals(ChatUser.agent.id));

        // Should update messageIdMap
        expect(result.messageIdMapUpdate, isNotNull);
        expect(
          result.messageIdMapUpdate!.puts.containsKey('agui-msg-1'),
          isTrue,
        );

        // Should create text buffer
        expect(result.textBuffersUpdate, isNotNull);
        expect(
          result.textBuffersUpdate!.puts.containsKey('agui-msg-1'),
          isTrue,
        );

        // Should emit activity update
        expect(result.activityUpdate?.isActive, isTrue);
        expect(
          result.activityUpdate?.eventType,
          equals(AgUiEventTypes.textMessageStart),
        );
      });

      test('applies buffered thinking to new message', () {
        const stateWithThinking = EventProcessingState(
          messages: [],
          messageIdMap: {},
          textBuffers: {},
          thinkingMessageIds: {},
          thinkingBuffer: ThinkingBufferState(
            bufferedText: 'buffered thinking text',
            isBuffering: true,
          ),
        );

        const event = ag_ui.TextMessageStartEvent(messageId: 'agui-msg-1');

        final result = processor.process(stateWithThinking, event);

        // Should have mutations for both add and update (for thinking)
        expect(result.messageMutations.length, equals(2));

        // First is add
        expect(result.messageMutations[0], isA<AddMessage>());

        // Second is update to apply thinking
        expect(result.messageMutations[1], isA<UpdateMessage>());

        // Should clear thinking buffer
        expect(result.thinkingBufferUpdate, isNotNull);
        expect(result.thinkingBufferUpdate!.isBuffering, isFalse);
      });

      test('applies finalized buffered thinking', () {
        const stateWithFinalizedThinking = EventProcessingState(
          messages: [],
          messageIdMap: {},
          textBuffers: {},
          thinkingMessageIds: {},
          thinkingBuffer: ThinkingBufferState(
            bufferedText: 'finalized thinking',
            isBuffering: true,
            isFinalized: true,
          ),
        );

        const event = ag_ui.TextMessageStartEvent(messageId: 'agui-msg-1');

        final result = processor.process(stateWithFinalizedThinking, event);

        // Should not track as current thinking (it's finalized)
        expect(
          result.thinkingMessageIdsUpdate?.puts.containsKey('current'),
          isNot(true),
        );
      });
    });

    group('TextMessageContentEvent', () {
      test('appends delta to existing message', () {
        final existingMessage = ChatMessage.text(
          user: ChatUser.agent,
          text: 'Hello ',
          isStreaming: true,
        );

        final state = EventProcessingState(
          messages: [existingMessage],
          messageIdMap: {'agui-msg-1': existingMessage.id},
          textBuffers: {'agui-msg-1': StringBuffer('Hello ')},
          thinkingMessageIds: const {},
          thinkingBuffer: ThinkingBufferState.empty(),
        );

        const event = ag_ui.TextMessageContentEvent(
          messageId: 'agui-msg-1',
          delta: 'world!',
        );

        final result = processor.process(state, event);

        expect(result.messageMutations.length, equals(1));
        final mutation = result.messageMutations[0] as UpdateMessage;
        expect(mutation.messageId, equals(existingMessage.id));

        // Apply the mutation to verify
        final updated = mutation.updater(existingMessage);
        expect(updated.text, equals('Hello world!'));
      });

      test('returns empty result for unmapped message', () {
        const event = ag_ui.TextMessageContentEvent(
          messageId: 'unknown-id',
          delta: 'text',
        );

        final result = processor.process(emptyState, event);

        expect(result, equals(EventProcessingResult.empty));
      });
    });

    group('TextMessageEndEvent', () {
      test('finalizes message and cleans up state', () {
        final existingMessage = ChatMessage.text(
          user: ChatUser.agent,
          text: 'Complete message',
          isStreaming: true,
        );

        final state = EventProcessingState(
          messages: [existingMessage],
          messageIdMap: {'agui-msg-1': existingMessage.id},
          textBuffers: {'agui-msg-1': StringBuffer('Complete message')},
          thinkingMessageIds: const {},
          thinkingBuffer: ThinkingBufferState.empty(),
        );

        const event = ag_ui.TextMessageEndEvent(messageId: 'agui-msg-1');

        final result = processor.process(state, event);

        // Should update message to not streaming
        expect(result.messageMutations.length, equals(1));
        final mutation = result.messageMutations[0] as UpdateMessage;
        final updated = mutation.updater(existingMessage);
        expect(updated.isStreaming, isFalse);

        // Should remove from messageIdMap
        expect(result.messageIdMapUpdate?.removes, contains('agui-msg-1'));

        // Should remove from textBuffers
        expect(result.textBuffersUpdate?.removes, contains('agui-msg-1'));

        // Should emit context update
        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.textMessage),
        );
      });

      test('returns empty result for unmapped message', () {
        const event = ag_ui.TextMessageEndEvent(messageId: 'unknown-id');

        final result = processor.process(emptyState, event);

        expect(result.messageMutations, isEmpty);
      });
    });

    group('ToolCallStartEvent', () {
      test('emits context and activity updates', () {
        const event = ag_ui.ToolCallStartEvent(
          toolCallId: 'tool-1',
          toolCallName: 'search_database',
        );

        final result = processor.process(emptyState, event);

        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.toolCallStart),
        );
        expect(
          result.activityUpdate?.eventType,
          equals(AgUiEventTypes.toolCallStart),
        );
        expect(result.activityUpdate?.toolName, equals('search_database'));
      });
    });

    group('ThinkingTextMessageStartEvent', () {
      test('attaches to existing streaming message', () {
        final streamingMessage = ChatMessage.text(
          user: ChatUser.agent,
          text: 'response',
          isStreaming: true,
        );

        final state = EventProcessingState(
          messages: [streamingMessage],
          messageIdMap: const {},
          textBuffers: const {},
          thinkingMessageIds: const {},
          thinkingBuffer: ThinkingBufferState.empty(),
        );

        const event = ag_ui.ThinkingTextMessageStartEvent();

        final result = processor.process(state, event);

        // Should update message with thinking
        expect(result.messageMutations.length, equals(1));
        final mutation = result.messageMutations[0] as UpdateMessage;
        expect(mutation.messageId, equals(streamingMessage.id));

        // Should track as current thinking
        expect(
          result.thinkingMessageIdsUpdate?.puts['current'],
          equals(streamingMessage.id),
        );
      });

      test('starts buffering when no message exists', () {
        const event = ag_ui.ThinkingTextMessageStartEvent();

        final result = processor.process(emptyState, event);

        expect(result.thinkingBufferUpdate, isNotNull);
        expect(result.thinkingBufferUpdate!.isBuffering, isTrue);
        expect(result.messageMutations, isEmpty);
      });
    });

    group('ThinkingTextMessageContentEvent', () {
      test('appends to tracked thinking message', () {
        final messageWithThinking = ChatMessage.text(
          user: ChatUser.agent,
          text: 'response',
          isStreaming: true,
        ).copyWith(thinkingText: 'existing ', isThinkingStreaming: true);

        final state = EventProcessingState(
          messages: [messageWithThinking],
          messageIdMap: const {},
          textBuffers: const {},
          thinkingMessageIds: {'current': messageWithThinking.id},
          thinkingBuffer: ThinkingBufferState.empty(),
        );

        const event = ag_ui.ThinkingTextMessageContentEvent(delta: 'new text');

        final result = processor.process(state, event);

        expect(result.messageMutations.length, equals(1));
        final mutation = result.messageMutations[0] as UpdateMessage;
        final updated = mutation.updater(messageWithThinking);
        expect(updated.thinkingText, equals('existing new text'));
      });

      test('appends to buffer when buffering', () {
        const state = EventProcessingState(
          messages: [],
          messageIdMap: {},
          textBuffers: {},
          thinkingMessageIds: {},
          thinkingBuffer: ThinkingBufferState(
            bufferedText: 'buffered ',
            isBuffering: true,
          ),
        );

        const event = ag_ui.ThinkingTextMessageContentEvent(delta: 'more');

        final result = processor.process(state, event);

        expect(result.thinkingBufferUpdate, isNotNull);
        expect(
          result.thinkingBufferUpdate!.bufferedText,
          equals('buffered more'),
        );
      });
    });

    group('ThinkingTextMessageEndEvent', () {
      test('finalizes thinking on tracked message', () {
        final messageWithThinking = ChatMessage.text(
          user: ChatUser.agent,
          text: 'response',
          isStreaming: true,
        ).copyWith(thinkingText: 'thinking', isThinkingStreaming: true);

        final state = EventProcessingState(
          messages: [messageWithThinking],
          messageIdMap: const {},
          textBuffers: const {},
          thinkingMessageIds: {'current': messageWithThinking.id},
          thinkingBuffer: ThinkingBufferState.empty(),
        );

        const event = ag_ui.ThinkingTextMessageEndEvent();

        final result = processor.process(state, event);

        // Should finalize thinking
        expect(result.messageMutations.length, equals(1));
        final mutation = result.messageMutations[0] as UpdateMessage;
        final updated = mutation.updater(messageWithThinking);
        expect(updated.isThinkingStreaming, isFalse);

        // Should remove from tracking
        expect(result.thinkingMessageIdsUpdate?.removes, contains('current'));
      });

      test('marks buffer as finalized when buffering', () {
        const state = EventProcessingState(
          messages: [],
          messageIdMap: {},
          textBuffers: {},
          thinkingMessageIds: {},
          thinkingBuffer: ThinkingBufferState(
            bufferedText: 'buffered thinking',
            isBuffering: true,
          ),
        );

        const event = ag_ui.ThinkingTextMessageEndEvent();

        final result = processor.process(state, event);

        expect(result.thinkingBufferUpdate, isNotNull);
        expect(result.thinkingBufferUpdate!.isFinalized, isTrue);
      });
    });

    group('RunFinishedEvent', () {
      test('emits context and activity updates', () {
        const event = ag_ui.RunFinishedEvent(
          threadId: 'thread-1',
          runId: 'run-123',
        );

        final result = processor.process(emptyState, event);

        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.runFinished),
        );
        expect(result.activityUpdate?.isActive, isFalse);
      });
    });

    group('RunErrorEvent', () {
      test('adds error message and emits updates', () {
        const event = ag_ui.RunErrorEvent(
          code: 'ERR_500',
          message: 'Internal server error',
        );

        final result = processor.process(emptyState, event);

        // Should add error message
        expect(result.messageMutations.length, equals(1));
        final addMutation = result.messageMutations[0] as AddMessage;
        expect(addMutation.message.type, equals(MessageType.error));

        // Should emit context update
        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.runError),
        );
        expect(result.contextUpdate?.summary, equals('Internal server error'));

        // Should stop activity
        expect(result.activityUpdate?.isActive, isFalse);
      });
    });

    group('StateSnapshotEvent', () {
      test('emits context update with state data', () {
        const event = ag_ui.StateSnapshotEvent(
          snapshot: {'key': 'value', 'count': 42},
        );

        final result = processor.process(emptyState, event);

        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.stateSnapshot),
        );
        expect(
          result.contextUpdate?.data,
          equals({'key': 'value', 'count': 42}),
        );
      });
    });

    group('ActivitySnapshotEvent', () {
      test('emits context and activity updates', () {
        const event = ag_ui.ActivitySnapshotEvent(
          activities: [
            {
              'type': AgUiEventTypes.toolCallStart,
              'toolCallName': 'get_location',
            },
          ],
        );

        final result = processor.process(emptyState, event);

        expect(
          result.contextUpdate?.eventType,
          equals(AgUiEventTypes.activitySnapshot),
        );
        expect(result.contextUpdate?.summary, equals('1 activities'));
        expect(result.activityUpdate?.isActive, isTrue);
        expect(
          result.activityUpdate?.eventType,
          equals(AgUiEventTypes.toolCallStart),
        );
        expect(result.activityUpdate?.toolName, equals('get_location'));
      });

      test('prioritizes toolCall over thinking', () {
        const event = ag_ui.ActivitySnapshotEvent(
          activities: [
            {'type': AgUiEventTypes.thinking},
            {
              'type': AgUiEventTypes.toolCallStart,
              'toolCallName': 'search_web',
            },
          ],
        );

        final result = processor.process(emptyState, event);

        expect(result.activityUpdate?.isActive, isTrue);
        expect(
          result.activityUpdate?.eventType,
          equals(AgUiEventTypes.toolCallStart),
        );
        expect(result.activityUpdate?.toolName, equals('search_web'));
      });

      test('falls back to thinking if no tool call', () {
        const event = ag_ui.ActivitySnapshotEvent(
          activities: [
            {'type': AgUiEventTypes.thinking},
            {'type': 'other'},
          ],
        );

        final result = processor.process(emptyState, event);

        expect(result.activityUpdate?.isActive, isTrue);
        expect(
          result.activityUpdate?.eventType,
          equals(AgUiEventTypes.thinking),
        );
        expect(result.activityUpdate?.toolName, isNull);
      });

      test('falls back to textMessageStart if no tool call or thinking', () {
        const event = ag_ui.ActivitySnapshotEvent(
          activities: [
            {'type': AgUiEventTypes.textMessageStart},
            {'type': 'other'},
          ],
        );

        final result = processor.process(emptyState, event);

        expect(result.activityUpdate?.isActive, isTrue);
        expect(
          result.activityUpdate?.eventType,
          equals(AgUiEventTypes.textMessageStart),
        );
        expect(result.activityUpdate?.toolName, isNull);
      });

      test('is inactive if no relevant activities', () {
        const event = ag_ui.ActivitySnapshotEvent(
          activities: [
            {'type': 'other'},
          ],
        );

        final result = processor.process(emptyState, event);

        expect(result.activityUpdate?.isActive, isFalse);
      });

      test('is inactive for empty activities list', () {
        const event = ag_ui.ActivitySnapshotEvent(activities: []);

        final result = processor.process(emptyState, event);

        expect(result.activityUpdate?.isActive, isFalse);
      });
    });

    group('ThinkingEndEvent', () {
      test('removes current thinking tracking', () {
        const event = ag_ui.ThinkingEndEvent();

        final result = processor.process(emptyState, event);

        expect(result.thinkingMessageIdsUpdate?.removes, contains('current'));
      });
    });

    group('Unhandled events', () {
      test('ToolCallArgsEvent returns empty', () {
        const event = ag_ui.ToolCallArgsEvent(
          toolCallId: 'tool-1',
          delta: '{"arg": "value"}',
        );

        final result = processor.process(emptyState, event);

        expect(result, equals(EventProcessingResult.empty));
      });

      test('ToolCallEndEvent returns empty', () {
        const event = ag_ui.ToolCallEndEvent(toolCallId: 'tool-1');

        final result = processor.process(emptyState, event);

        expect(result, equals(EventProcessingResult.empty));
      });

      test('CustomEvent returns empty', () {
        const event = ag_ui.CustomEvent(name: 'custom', value: {});

        final result = processor.process(emptyState, event);

        expect(result, equals(EventProcessingResult.empty));
      });
    });
  });

  group('ThinkingBufferState', () {
    test('startBuffering creates empty buffer in buffering state', () {
      final initial = ThinkingBufferState.empty();
      final buffering = initial.startBuffering();

      expect(buffering.isBuffering, isTrue);
      expect(buffering.bufferedText, equals(''));
      expect(buffering.isFinalized, isFalse);
    });

    test('appendText adds delta to buffer', () {
      const buffering = ThinkingBufferState(
        bufferedText: 'hello ',
        isBuffering: true,
      );
      final appended = buffering.appendText('world');

      expect(appended.bufferedText, equals('hello world'));
      expect(appended.isBuffering, isTrue);
    });

    test('finalize marks buffer as finalized', () {
      const buffering = ThinkingBufferState(
        bufferedText: 'content',
        isBuffering: true,
      );
      final finalized = buffering.finalize();

      expect(finalized.isFinalized, isTrue);
      expect(finalized.bufferedText, equals('content'));
    });

    test('clear returns empty state', () {
      const withContent = ThinkingBufferState(
        bufferedText: 'content',
        isBuffering: true,
        isFinalized: true,
      );
      final cleared = withContent.clear();

      expect(cleared.bufferedText, isNull);
      expect(cleared.isBuffering, isFalse);
      expect(cleared.isFinalized, isFalse);
    });
  });

  group('MapUpdate', () {
    test('applyTo adds puts and removes keys', () {
      final map = {'a': 1, 'b': 2, 'c': 3};
      const update = MapUpdate<String, int>(
        puts: {'d': 4, 'e': 5},
        removes: {'a', 'b'},
      );

      update.applyTo(map);

      expect(map, equals({'c': 3, 'd': 4, 'e': 5}));
    });
  });

  group('EventProcessingResult', () {
    test('empty has no changes', () {
      expect(EventProcessingResult.empty.hasChanges, isFalse);
    });

    test('hasChanges detects mutations', () {
      final dummyMessage = ChatMessage.text(user: ChatUser.agent, text: 'test');
      final withMutations = EventProcessingResult(
        messageMutations: [AddMessage(dummyMessage)],
      );
      expect(withMutations.hasChanges, isTrue);
    });

    test('hasChanges detects side effects', () {
      const withContext = EventProcessingResult(
        contextUpdate: ContextUpdate('test'),
      );
      expect(withContext.hasChanges, isTrue);
    });

    test('hasChanges detects clearDeduplication', () {
      const withClear = EventProcessingResult(clearDeduplication: true);
      expect(withClear.hasChanges, isTrue);
    });
  });
}
