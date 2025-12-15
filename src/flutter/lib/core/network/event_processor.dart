import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:collection/collection.dart'; // Import for firstWhereOrNull

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/models/error_types.dart';
import 'package:soliplex/core/protocol/agui_event_types.dart'; // Import AgUiEventTypes
import 'package:soliplex/core/utils/debug_log.dart';

// =============================================================================
// STATE TYPES
// =============================================================================

/// Immutable state passed to EventProcessor for processing.
class EventProcessingState {
  const EventProcessingState({
    required this.messages,
    required this.messageIdMap,
    required this.textBuffers,
    required this.thinkingMessageIds,
    required this.thinkingBuffer,
  });

  /// Create empty initial state.
  factory EventProcessingState.empty() => EventProcessingState(
    messages: const [],
    messageIdMap: const {},
    textBuffers: const {},
    thinkingMessageIds: const {},
    thinkingBuffer: ThinkingBufferState.empty(),
  );

  /// Current messages list.
  final List<ChatMessage> messages;

  /// AG-UI messageId → ChatMessage id mapping.
  final Map<String, String> messageIdMap;

  /// Text buffers for streaming messages.
  final Map<String, StringBuffer> textBuffers;

  /// Thinking message ID mapping (key → chatMessageId).
  final Map<String, String> thinkingMessageIds;

  /// Pending thinking buffer state.
  final ThinkingBufferState thinkingBuffer;
}

/// State for buffering thinking text that arrives before a message exists.
class ThinkingBufferState {
  const ThinkingBufferState({
    this.bufferedText,
    this.isBuffering = false,
    this.isFinalized = false,
  });

  factory ThinkingBufferState.empty() => const ThinkingBufferState();
  final String? bufferedText;
  final bool isBuffering;
  final bool isFinalized;

  ThinkingBufferState startBuffering() =>
      const ThinkingBufferState(bufferedText: '', isBuffering: true);

  ThinkingBufferState appendText(String delta) => ThinkingBufferState(
    bufferedText: (bufferedText ?? '') + delta,
    isBuffering: isBuffering,
    isFinalized: isFinalized,
  );

  ThinkingBufferState finalize() => ThinkingBufferState(
    bufferedText: bufferedText,
    isBuffering: isBuffering,
    isFinalized: true,
  );

  ThinkingBufferState clear() => const ThinkingBufferState();
}

// =============================================================================
// RESULT TYPES
// =============================================================================

/// Result of processing an event - contains all state changes and side effects.
class EventProcessingResult {
  const EventProcessingResult({
    this.messageMutations = const [],
    this.messageIdMapUpdate,
    this.textBuffersUpdate,
    this.thinkingMessageIdsUpdate,
    this.thinkingBufferUpdate,
    this.contextUpdate,
    this.activityUpdate,
    this.clearDeduplication = false,
  });

  /// Message mutations to apply.
  final List<MessageMutation> messageMutations;

  /// Updates to the messageIdMap.
  final MapUpdate<String, String>? messageIdMapUpdate;

  /// Updates to textBuffers.
  final MapUpdate<String, StringBuffer>? textBuffersUpdate;

  /// Updates to thinkingMessageIds.
  final MapUpdate<String, String>? thinkingMessageIdsUpdate;

  /// New thinking buffer state (if changed).
  final ThinkingBufferState? thinkingBufferUpdate;

  /// Context update side effect.
  final ContextUpdate? contextUpdate;

  /// Activity update side effect.
  final ActivityUpdate? activityUpdate;

  /// Whether to clear deduplication state (processed tool calls/notifications).
  final bool clearDeduplication;

  /// No-op result (event ignored or unhandled).
  static const empty = EventProcessingResult();

  /// Check if there are any changes.
  bool get hasChanges =>
      messageMutations.isNotEmpty ||
      messageIdMapUpdate != null ||
      textBuffersUpdate != null ||
      thinkingMessageIdsUpdate != null ||
      thinkingBufferUpdate != null ||
      contextUpdate != null ||
      activityUpdate != null ||
      clearDeduplication;
}

/// Generic map update operation.
class MapUpdate<K, V> {
  const MapUpdate({this.puts = const {}, this.removes = const {}});
  final Map<K, V> puts;
  final Set<K> removes;

  /// Apply update to a mutable map.
  void applyTo(Map<K, V> map) {
    map.addAll(puts);
    removes.forEach(map.remove);
  }
}

// =============================================================================
// MESSAGE MUTATIONS
// =============================================================================

/// Base class for message mutations.
sealed class MessageMutation {
  const MessageMutation();
}

/// Add a new message.
class AddMessage extends MessageMutation {
  const AddMessage(this.message);
  final ChatMessage message;
}

/// Update an existing message by ID.
class UpdateMessage extends MessageMutation {
  const UpdateMessage(this.messageId, this.updater);
  final String messageId;
  final ChatMessage Function(ChatMessage) updater;
}

// =============================================================================
// SIDE EFFECT TYPES
// =============================================================================

/// Context pane update side effect.
class ContextUpdate {
  const ContextUpdate(this.eventType, {this.summary, this.data});
  final String eventType;
  final String? summary;
  final Map<String, dynamic>? data;
}

/// Activity status update side effect.
class ActivityUpdate {
  const ActivityUpdate({required this.isActive, this.eventType, this.toolName});
  final bool isActive;
  final String? eventType;
  final String? toolName;
}

// =============================================================================
// EVENT PROCESSOR
// =============================================================================

/// Processes AG-UI events and returns state changes.
///
/// This is a pure function that takes current state and an event,
/// and returns the changes to apply. It does NOT mutate state directly.
///
/// This design enables:
/// 1. Unit testing of event processing in isolation
/// 2. Clear separation of event logic from state management
/// 3. Potential for event replay/debugging
class EventProcessor {
  const EventProcessor();

  /// Process an AG-UI event against current state.
  ///
  /// Returns EventProcessingResult describing all changes to apply.
  EventProcessingResult process(
    EventProcessingState state,
    ag_ui.BaseEvent event,
  ) {
    switch (event) {
      case ag_ui.RunStartedEvent():
        return _processRunStarted(event);

      case ag_ui.TextMessageStartEvent():
        return _processTextMessageStart(state, event);

      case ag_ui.TextMessageContentEvent():
        return _processTextMessageContent(state, event);

      case ag_ui.TextMessageEndEvent():
        return _processTextMessageEnd(state, event);

      case ag_ui.ToolCallStartEvent():
        return _processToolCallStart(event);

      case ag_ui.ToolCallArgsEvent():
        return EventProcessingResult.empty; // Args handled by Thread

      case ag_ui.ToolCallEndEvent():
        return EventProcessingResult.empty;

      case ag_ui.ToolCallResultEvent():
        return const EventProcessingResult(
          contextUpdate: ContextUpdate(AgUiEventTypes.toolResult),
        );

      case ag_ui.StateSnapshotEvent():
        return _processStateSnapshot(event);

      case ag_ui.StateDeltaEvent():
        return _processStateDelta(event);

      case ag_ui.ActivitySnapshotEvent():
        return _processActivitySnapshot(event);

      case ag_ui.ThinkingStartEvent():
        return const EventProcessingResult(
          contextUpdate: ContextUpdate(AgUiEventTypes.thinking),
          activityUpdate: ActivityUpdate(isActive: true,
            eventType: AgUiEventTypes.thinking,
          ),
        );

      case ag_ui.ThinkingTextMessageStartEvent():
        return _processThinkingTextMessageStart(state);

      case ag_ui.ThinkingTextMessageContentEvent():
        return _processThinkingTextMessageContent(state, event);

      case ag_ui.ThinkingTextMessageEndEvent():
        return _processThinkingTextMessageEnd(state);

      case ag_ui.ThinkingEndEvent():
        return const EventProcessingResult(
          thinkingMessageIdsUpdate: MapUpdate(removes: {'current'}),
        );

      case ag_ui.RunFinishedEvent():
        return _processRunFinished(event);

      case ag_ui.RunErrorEvent():
        return _processRunError(event);

      case ag_ui.CustomEvent():
        return EventProcessingResult.empty; // Handled via uiToolHandler

      default:
        DebugLog.warn('EventProcessor: Unhandled event: ${event.runtimeType}');
        return EventProcessingResult.empty;
    }
  }

  // ===========================================================================
  // PRIVATE EVENT HANDLERS
  // ===========================================================================

  EventProcessingResult _processRunStarted(ag_ui.RunStartedEvent event) {
    DebugLog.agui('RunStarted runId=${event.runId}');
    return EventProcessingResult(
      thinkingBufferUpdate: ThinkingBufferState.empty(),
      contextUpdate: ContextUpdate(
        AgUiEventTypes.runStarted,
        summary: event.runId,
      ),
      activityUpdate: const ActivityUpdate(isActive: true),
      clearDeduplication:
          true, // Clear tool call/notification dedup state for new run
    );
  }

  EventProcessingResult _processTextMessageStart(
    EventProcessingState state,
    ag_ui.TextMessageStartEvent event,
  ) {
    final aguiMessageId = event.messageId;
    DebugLog.mapping(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'TextMessageStart aguiId=$aguiMessageId, current map: ${state.messageIdMap}',
    );

    // Create new streaming message
    final chatMessage = ChatMessage.text(
      user: ChatUser.agent,
      text: '',
      isStreaming: true,
    );
    final chatMessageId = chatMessage.id;

    DebugLog.mapping(
      'TextMessageStart mapped: aguiId=$aguiMessageId -> chatId=$chatMessageId',
    );

    // Build mutations list
    final mutations = <MessageMutation>[AddMessage(chatMessage)];

    // Apply any pending thinking to this new message
    ThinkingBufferState? newThinkingBuffer;
    MapUpdate<String, String>? thinkingIdsUpdate;

    if (state.thinkingBuffer.isBuffering &&
        state.thinkingBuffer.bufferedText != null) {
      final thinkingText = state.thinkingBuffer.bufferedText!;
      if (thinkingText.isNotEmpty) {
        // Update the message to include thinking
        mutations.add(
          UpdateMessage(chatMessageId, (msg) {
            final updated = msg.copyWith(
              thinkingText: thinkingText,
              isThinkingStreaming: !state.thinkingBuffer.isFinalized,
            );
            return updated;
          }),
        );

        if (!state.thinkingBuffer.isFinalized) {
          thinkingIdsUpdate = MapUpdate(puts: {'current': chatMessageId});
          DebugLog.agui(
            // ignore: lines_longer_than_80_chars (auto-documented)
            'Applied buffered thinking (${thinkingText.length} chars) to chatId=$chatMessageId, still streaming',
          );
        } else {
          DebugLog.agui(
            // ignore: lines_longer_than_80_chars (auto-documented)
            'Applied and finalized buffered thinking (${thinkingText.length} chars) to chatId=$chatMessageId',
          );
        }
      }
      newThinkingBuffer = ThinkingBufferState.empty();
    }

    return EventProcessingResult(
      messageMutations: mutations,
      messageIdMapUpdate: MapUpdate(puts: {aguiMessageId: chatMessageId}),
      textBuffersUpdate: MapUpdate(puts: {aguiMessageId: StringBuffer()}),
      thinkingBufferUpdate: newThinkingBuffer,
      thinkingMessageIdsUpdate: thinkingIdsUpdate,
      activityUpdate: const ActivityUpdate(isActive: true,
        eventType: AgUiEventTypes.textMessageStart,
      ),
    );
  }

  EventProcessingResult _processTextMessageContent(
    EventProcessingState state,
    ag_ui.TextMessageContentEvent event,
  ) {
    final aguiMessageId = event.messageId;
    final chatMessageId = state.messageIdMap[aguiMessageId];

    if (chatMessageId == null) {
      DebugLog.warn(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'TextMessageContent: NO MAPPING for aguiId=$aguiMessageId, map=${state.messageIdMap}',
      );
      return EventProcessingResult.empty;
    }

    // Update text buffer
    final buffer = state.textBuffers[aguiMessageId];
    buffer?.write(event.delta);

    return EventProcessingResult(
      messageMutations: [
        UpdateMessage(chatMessageId, (msg) {
          return msg.copyWith(text: (msg.text ?? '') + event.delta);
        }),
      ],
    );
  }

  EventProcessingResult _processTextMessageEnd(
    EventProcessingState state,
    ag_ui.TextMessageEndEvent event,
  ) {
    final aguiMessageId = event.messageId;
    final chatMessageId = state.messageIdMap[aguiMessageId];
    DebugLog.mapping(
      'TextMessageEnd aguiId=$aguiMessageId, chatId=$chatMessageId',
    );

    if (chatMessageId == null) {
      DebugLog.warn('TextMessageEnd: NO MAPPING for aguiId=$aguiMessageId');
      return EventProcessingResult.empty;
    }

    final text = state.textBuffers[aguiMessageId]?.toString() ?? '';
    DebugLog.chat('Finalized message: ${text.length} chars');

    return EventProcessingResult(
      messageMutations: [
        UpdateMessage(chatMessageId, (msg) => msg.copyWith(isStreaming: false)),
      ],
      messageIdMapUpdate: MapUpdate(removes: {aguiMessageId}),
      textBuffersUpdate: MapUpdate(removes: {aguiMessageId}),
      contextUpdate: ContextUpdate(AgUiEventTypes.textMessage, summary: text),
    );
  }

  EventProcessingResult _processToolCallStart(ag_ui.ToolCallStartEvent event) {
    DebugLog.tool(
      'ToolCallStart: ${event.toolCallName} (id=${event.toolCallId})',
    );

    // Create visible chat message for ALL tool calls
    final chatMessage = ChatMessage.toolCall(
      user: ChatUser.agent,
      toolName: event.toolCallName,
      toolCallId: event.toolCallId,
    );

    return EventProcessingResult(
      messageMutations: [AddMessage(chatMessage)],
      // Store mapping: toolCallId -> chatMessageId
      // We use the toolCallId from the event as the key
      messageIdMapUpdate: MapUpdate(puts: {event.toolCallId: chatMessage.id}),
      contextUpdate: ContextUpdate(
        AgUiEventTypes.toolCallStart,
        summary: event.toolCallName,
      ),
      activityUpdate: ActivityUpdate(isActive: true,
        eventType: AgUiEventTypes.toolCallStart,
        toolName: event.toolCallName,
      ),
    );
  }

  EventProcessingResult _processStateSnapshot(ag_ui.StateSnapshotEvent event) {
    final stateData = event.snapshot as Map<String, dynamic>? ?? {};
    return EventProcessingResult(
      contextUpdate: ContextUpdate(
        AgUiEventTypes.stateSnapshot,
        data: stateData,
      ),
    );
  }

  EventProcessingResult _processStateDelta(ag_ui.StateDeltaEvent event) {
    final delta = event.delta as List<dynamic>? ?? [];
    if (delta.isNotEmpty && delta.first is Map<String, dynamic>) {
      return EventProcessingResult(
        contextUpdate: ContextUpdate(
          AgUiEventTypes.stateDelta,
          data: delta.first as Map<String, dynamic>,
        ),
      );
    }
    return EventProcessingResult.empty;
  }

  EventProcessingResult _processThinkingTextMessageStart(
    EventProcessingState state,
  ) {
    // Find current streaming assistant message
    ChatMessage? targetMessage;
    for (final m in state.messages.reversed) {
      if (m.user.id == ChatUser.agent.id && m.isStreaming) {
        targetMessage = m;
        break;
      }
    }

    if (targetMessage != null) {
      DebugLog.agui(
        'ThinkingTextMessageStart: attached to chatId=${targetMessage.id}',
      );
      return EventProcessingResult(
        messageMutations: [
          UpdateMessage(targetMessage.id, (msg) {
            return msg.copyWith(thinkingText: '', isThinkingStreaming: true);
          }),
        ],
        thinkingMessageIdsUpdate: MapUpdate(
          puts: {'current': targetMessage.id},
        ),
      );
    } else {
      DebugLog.agui('ThinkingTextMessageStart: buffering (no message yet)');
      return EventProcessingResult(
        thinkingBufferUpdate: ThinkingBufferState.empty().startBuffering(),
      );
    }
  }

  EventProcessingResult _processThinkingTextMessageContent(
    EventProcessingState state,
    ag_ui.ThinkingTextMessageContentEvent event,
  ) {
    final chatMessageId = state.thinkingMessageIds['current'];

    if (chatMessageId != null) {
      return EventProcessingResult(
        messageMutations: [
          UpdateMessage(chatMessageId, (msg) {
            return msg.copyWith(
              thinkingText: (msg.thinkingText ?? '') + event.delta,
            );
          }),
        ],
      );
    } else if (state.thinkingBuffer.isBuffering) {
      return EventProcessingResult(
        thinkingBufferUpdate: state.thinkingBuffer.appendText(event.delta),
      );
    }

    return EventProcessingResult.empty;
  }

  EventProcessingResult _processThinkingTextMessageEnd(
    EventProcessingState state,
  ) {
    final chatMessageId = state.thinkingMessageIds['current'];

    if (chatMessageId != null) {
      DebugLog.agui('ThinkingTextMessageEnd: finalized chatId=$chatMessageId');
      return EventProcessingResult(
        messageMutations: [
          UpdateMessage(chatMessageId, (msg) {
            return msg.copyWith(isThinkingStreaming: false);
          }),
        ],
        thinkingMessageIdsUpdate: const MapUpdate(removes: {'current'}),
      );
    } else if (state.thinkingBuffer.isBuffering) {
      DebugLog.agui(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'ThinkingTextMessageEnd: buffered ${state.thinkingBuffer.bufferedText?.length ?? 0} chars, marked finalized',
      );
      return EventProcessingResult(
        thinkingBufferUpdate: state.thinkingBuffer.finalize(),
      );
    }

    return EventProcessingResult.empty;
  }

  EventProcessingResult _processRunFinished(ag_ui.RunFinishedEvent event) {
    DebugLog.agui('RunFinished runId=${event.runId}');
    return const EventProcessingResult(
      contextUpdate: ContextUpdate(AgUiEventTypes.runFinished),
      activityUpdate: ActivityUpdate(isActive: false),
    );
  }

  EventProcessingResult _processRunError(ag_ui.RunErrorEvent event) {
    DebugLog.error('RunError: ${event.code}: ${event.message}');

    final errorInfo = ChatErrorInfo(
      type: ChatErrorType.server,
      friendlyMessage: 'Something went wrong',
      technicalDetails: event.message,
      errorCode: event.code,
    );
    final errorMessage = ChatMessage.error(
      user: ChatUser.system,
      errorInfo: errorInfo,
    );

    return EventProcessingResult(
      messageMutations: [AddMessage(errorMessage)],
      contextUpdate: ContextUpdate(
        AgUiEventTypes.runError,
        summary: event.message,
      ),
      activityUpdate: const ActivityUpdate(isActive: false),
    );
  }

  EventProcessingResult _processActivitySnapshot(
    ag_ui.ActivitySnapshotEvent event,
  ) {
    String? activeEventType;
    String? activeToolName;

    // Helper to safely get type from activity map
    String? getType(dynamic activity) {
      if (activity is Map) {
        return activity['type'] as String?;
      }
      return null;
    }

    // Helper to safely get tool name from activity map
    String? getToolName(dynamic activity) {
      if (activity is Map) {
        return activity['toolCallName'] as String?;
      }
      return null;
    }

    // Prioritize tool calls for displaying status
    final activeTool = event.activities.firstWhereOrNull(
      (a) => getType(a) == AgUiEventTypes.toolCallStart,
    );
    if (activeTool != null) {
      activeEventType = AgUiEventTypes.toolCallStart;
      activeToolName = getToolName(activeTool);
    } else {
      // Fallback to thinking or text message start
      final activeThinking = event.activities.firstWhereOrNull(
        (a) => getType(a) == AgUiEventTypes.thinking,
      );
      if (activeThinking != null) {
        activeEventType = AgUiEventTypes.thinking;
      } else {
        final activeTextMessage = event.activities.firstWhereOrNull(
          (a) => getType(a) == AgUiEventTypes.textMessageStart,
        );
        if (activeTextMessage != null) {
          activeEventType = AgUiEventTypes.textMessageStart;
        }
      }
    }

    return EventProcessingResult(
      contextUpdate: ContextUpdate(
        AgUiEventTypes.activitySnapshot,
        summary: '${event.activities.length} activities',
      ),
      activityUpdate: ActivityUpdate(
        // isActive if any relevant activity found
        isActive: activeEventType != null, 
        eventType: activeEventType,
        toolName: activeToolName,
      ),
    );
  }
}
