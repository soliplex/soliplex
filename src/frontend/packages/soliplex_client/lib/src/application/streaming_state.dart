import 'package:meta/meta.dart';

/// Ephemeral streaming state (application layer, not domain).
///
/// Streaming is operation state that exists only during active streaming.
/// When streaming completes, the text becomes a domain message.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (streaming) {
///   case NotStreaming():
///     // No message being streamed
///   case Streaming(:final messageId, :final text):
///     // Message is streaming
/// }
/// ```
@immutable
sealed class StreamingState {
  const StreamingState();
}

/// No message is currently streaming.
@immutable
class NotStreaming extends StreamingState {
  /// Creates a not streaming state.
  const NotStreaming();

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is NotStreaming && runtimeType == other.runtimeType;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NotStreaming()';
}

/// A message is currently streaming.
@immutable
class Streaming extends StreamingState {
  /// Creates a streaming state with the given [messageId] and accumulated
  /// [text].
  const Streaming({required this.messageId, required this.text});

  /// The ID of the message being streamed.
  final String messageId;

  /// The text accumulated so far.
  final String text;

  // TODO(cleanup): Consider inlining this in agui_event_processor.dart.
  // This method is only used by one caller (Feature Envy smell). Keeping
  // Streaming as pure data would be cleaner.
  /// Creates a copy with the delta appended to text.
  Streaming appendDelta(String delta) {
    return Streaming(messageId: messageId, text: text + delta);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Streaming &&
          runtimeType == other.runtimeType &&
          messageId == other.messageId &&
          text == other.text;

  @override
  int get hashCode => Object.hash(runtimeType, messageId, text);

  @override
  String toString() =>
      'Streaming(messageId: $messageId, text: ${text.length} chars)';
}
