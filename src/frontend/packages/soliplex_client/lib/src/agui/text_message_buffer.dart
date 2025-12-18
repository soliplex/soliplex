import 'package:meta/meta.dart';
import 'package:soliplex_client/src/models/chat_message.dart';

/// Sealed class buffer that accumulates streaming text message content.
///
/// Uses a sealed class hierarchy to eliminate nullable fields:
/// - `InactiveTextBuffer` - no active message being buffered
/// - `ActiveTextBuffer` - actively buffering a message with required fields
///
/// Each operation returns a new buffer instance, preserving immutability.
///
/// Usage:
/// 1. Call [start] when TEXT_MESSAGE_START event is received
/// 2. Call `append` for each TEXT_MESSAGE_CONTENT event (on ActiveTextBuffer)
/// 3. Call `complete` when TEXT_MESSAGE_END event is received
///
/// Example:
/// ```dart
/// TextMessageBuffer buffer = TextMessageBuffer.empty;
///
/// // When TEXT_MESSAGE_START arrives
/// buffer = buffer.start(messageId: 'msg-123');
///
/// // When TEXT_MESSAGE_CONTENT arrives (buffer is now ActiveTextBuffer)
/// if (buffer case ActiveTextBuffer active) {
///   buffer = active.append('Hello, ');
///   buffer = (buffer as ActiveTextBuffer).append('world!');
/// }
///
/// // When TEXT_MESSAGE_END arrives
/// if (buffer case ActiveTextBuffer active) {
///   final (newBuffer, message) = active.complete();
///   buffer = newBuffer;
///   // message.text == 'Hello, world!'
/// }
/// ```
@immutable
sealed class TextMessageBuffer {
  const TextMessageBuffer();

  /// An empty, inactive buffer.
  static const empty = InactiveTextBuffer();

  /// Whether the buffer is currently accumulating a message.
  bool get isActive;

  /// The current accumulated content (empty string if inactive).
  String get currentContent;

  /// Starts buffering a new message.
  ///
  /// Returns an [ActiveTextBuffer] ready to accumulate content.
  ///
  /// Throws [StateError] if already active.
  TextMessageBuffer start({
    required String messageId,
    ChatUser user = ChatUser.assistant,
  });

  /// Resets the buffer, discarding any accumulated content.
  ///
  /// Returns an [InactiveTextBuffer].
  TextMessageBuffer reset() => empty;
}

/// Inactive buffer state - no message being accumulated.
///
/// Use [start] to begin buffering a new message.
@immutable
class InactiveTextBuffer extends TextMessageBuffer {
  /// Creates an inactive buffer.
  const InactiveTextBuffer();

  @override
  bool get isActive => false;

  @override
  String get currentContent => '';

  @override
  TextMessageBuffer start({
    required String messageId,
    ChatUser user = ChatUser.assistant,
  }) {
    return ActiveTextBuffer(messageId: messageId, user: user);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is InactiveTextBuffer;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'InactiveTextBuffer()';
}

/// Active buffer state - accumulating content for a message.
///
/// Use [append] to add content and [complete] to finish the message.
@immutable
class ActiveTextBuffer extends TextMessageBuffer {
  /// Creates an active buffer with the given state.
  const ActiveTextBuffer({
    required this.messageId,
    this.user = ChatUser.assistant,
    this.content = '',
  });

  /// The message ID being buffered.
  final String messageId;

  /// The user for this message.
  final ChatUser user;

  /// The accumulated content.
  final String content;

  @override
  bool get isActive => true;

  @override
  String get currentContent => content;

  @override
  TextMessageBuffer start({
    required String messageId,
    ChatUser user = ChatUser.assistant,
  }) {
    throw StateError(
      'Cannot start a new message while one is already active. '
      'Call complete() or reset() first.',
    );
  }

  /// Appends content to the current message.
  ///
  /// Returns a new [ActiveTextBuffer] with the appended content.
  ActiveTextBuffer append(String delta) {
    return ActiveTextBuffer(
      messageId: messageId,
      user: user,
      content: content + delta,
    );
  }

  /// Completes the current message and returns a [TextMessage].
  ///
  /// Returns a tuple of (reset buffer, completed message).
  (TextMessageBuffer, TextMessage) complete() {
    final message = TextMessage(
      id: messageId,
      user: user,
      text: content,
      createdAt: DateTime.now(),
    );
    return (TextMessageBuffer.empty, message);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ActiveTextBuffer &&
          runtimeType == other.runtimeType &&
          messageId == other.messageId &&
          user == other.user &&
          content == other.content;

  @override
  int get hashCode => Object.hash(messageId, user, content);

  @override
  String toString() => 'ActiveTextBuffer('
      'messageId: $messageId, '
      'user: $user, '
      'content: "$content")';
}
