import 'package:ag_ui/ag_ui.dart';
import 'package:meta/meta.dart';
import 'package:soliplex_client/src/application/streaming_state.dart';
import 'package:soliplex_client/src/domain/chat_message.dart';
import 'package:soliplex_client/src/domain/conversation.dart'
    hide NotStreaming, Streaming, StreamingState;

/// Result of processing an AG-UI event.
///
/// Contains both the updated domain state (Conversation) and ephemeral
/// streaming state.
@immutable
class EventProcessingResult {
  /// Creates an event processing result.
  const EventProcessingResult({
    required this.conversation,
    required this.streaming,
  });

  /// Updated conversation (domain state).
  final Conversation conversation;

  /// Updated streaming state (ephemeral operation state).
  final StreamingState streaming;
}

/// Processes a single AG-UI event, returning updated domain and streaming
/// state.
///
/// This is a pure function with no side effects. It takes the current state
/// and an event, and returns the new state.
///
/// Example usage:
/// ```dart
/// final result = processEvent(conversation, streaming, event);
/// // result.conversation - updated domain state
/// // result.streaming - updated streaming state
/// ```
EventProcessingResult processEvent(
  Conversation conversation,
  StreamingState streaming,
  BaseEvent event,
) {
  return switch (event) {
    // Run lifecycle events
    RunStartedEvent(:final runId) => EventProcessingResult(
        conversation: conversation.withStatus(Running(runId: runId)),
        streaming: streaming,
      ),
    RunFinishedEvent() => EventProcessingResult(
        conversation: conversation.withStatus(const Completed()),
        streaming: const NotStreaming(),
      ),
    RunErrorEvent(:final message) => EventProcessingResult(
        conversation: conversation.withStatus(Failed(error: message)),
        streaming: const NotStreaming(),
      ),

    // Text message streaming events
    TextMessageStartEvent(:final messageId) => EventProcessingResult(
        conversation: conversation,
        streaming: Streaming(messageId: messageId, text: ''),
      ),
    TextMessageContentEvent(:final messageId, :final delta) =>
      _processTextContent(conversation, streaming, messageId, delta),
    TextMessageEndEvent(:final messageId) =>
      _processTextEnd(conversation, streaming, messageId),

    // Tool call events
    ToolCallStartEvent(:final toolCallId, :final toolCallName) =>
      EventProcessingResult(
        conversation: conversation.withToolCall(
          ToolCallInfo(id: toolCallId, name: toolCallName),
        ),
        streaming: streaming,
      ),
    ToolCallEndEvent(:final toolCallId) => EventProcessingResult(
        conversation: conversation.copyWith(
          toolCalls: conversation.toolCalls
              .where((tc) => tc.id != toolCallId)
              .toList(),
        ),
        streaming: streaming,
      ),

    // All other events pass through unchanged
    _ => EventProcessingResult(
        conversation: conversation,
        streaming: streaming,
      ),
  };
}

// TODO(cleanup): Extract streaming guard pattern if a third streaming event
// type is added. Both _processTextContent and _processTextEnd share the
// "check if streaming matches messageId, else return unchanged" pattern.
EventProcessingResult _processTextContent(
  Conversation conversation,
  StreamingState streaming,
  String messageId,
  String delta,
) {
  if (streaming is Streaming && streaming.messageId == messageId) {
    return EventProcessingResult(
      conversation: conversation,
      streaming: streaming.appendDelta(delta),
    );
  }
  return EventProcessingResult(
    conversation: conversation,
    streaming: streaming,
  );
}

EventProcessingResult _processTextEnd(
  Conversation conversation,
  StreamingState streaming,
  String messageId,
) {
  if (streaming is Streaming && streaming.messageId == messageId) {
    final newMessage = TextMessage.create(
      id: messageId,
      user: ChatUser.assistant,
      text: streaming.text,
    );
    return EventProcessingResult(
      conversation: conversation.withAppendedMessage(newMessage),
      streaming: const NotStreaming(),
    );
  }
  return EventProcessingResult(
    conversation: conversation,
    streaming: streaming,
  );
}
