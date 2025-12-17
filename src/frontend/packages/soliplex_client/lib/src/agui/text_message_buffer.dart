import 'package:meta/meta.dart';
import 'package:soliplex_client/src/models/chat_message.dart';

/// Buffer that accumulates streaming text message content.
///
/// Usage:
/// 1. Call [start] when TEXT_MESSAGE_START event is received
/// 2. Call [append] for each TEXT_MESSAGE_CONTENT event
/// 3. Call [complete] when TEXT_MESSAGE_END event is received
///
/// Example:
/// ```dart
/// final buffer = TextMessageBuffer();
///
/// // When TEXT_MESSAGE_START arrives
/// buffer.start(messageId: 'msg-123', user: ChatUser.assistant);
///
/// // When TEXT_MESSAGE_CONTENT arrives
/// buffer.append('Hello, ');
/// buffer.append('world!');
///
/// // When TEXT_MESSAGE_END arrives
/// final message = buffer.complete();
/// // message.text == 'Hello, world!'
/// ```
class TextMessageBuffer {
  String? _messageId;
  ChatUser _user = ChatUser.assistant;
  final StringBuffer _content = StringBuffer();
  bool _isActive = false;

  /// Whether the buffer is currently accumulating a message.
  bool get isActive => _isActive;

  /// The current message ID being buffered, or null if not active.
  String? get messageId => _messageId;

  /// The current user for the message being buffered.
  ChatUser get user => _user;

  /// The current accumulated content.
  String get currentContent => _content.toString();

  /// Starts buffering a new message.
  ///
  /// Throws [StateError] if a message is already being buffered.
  void start({
    required String messageId,
    ChatUser user = ChatUser.assistant,
  }) {
    if (_isActive) {
      throw StateError(
        'Cannot start a new message while one is already active. '
        'Call complete() or reset() first.',
      );
    }
    _messageId = messageId;
    _user = user;
    _content.clear();
    _isActive = true;
  }

  /// Appends content to the current message.
  ///
  /// Throws [StateError] if no message is being buffered.
  void append(String delta) {
    if (!_isActive) {
      throw StateError(
        'Cannot append content when no message is active. '
        'Call start() first.',
      );
    }
    _content.write(delta);
  }

  /// Completes the current message and returns a [ChatMessage].
  ///
  /// The buffer is reset after this call.
  ///
  /// Throws [StateError] if no message is being buffered.
  ChatMessage complete() {
    if (!_isActive) {
      throw StateError(
        'Cannot complete a message when none is active. '
        'Call start() first.',
      );
    }

    final message = ChatMessage(
      id: _messageId!,
      user: _user,
      type: MessageType.text,
      text: _content.toString(),
      createdAt: DateTime.now(),
    );

    reset();
    return message;
  }

  /// Resets the buffer, discarding any accumulated content.
  void reset() {
    _messageId = null;
    _user = ChatUser.assistant;
    _content.clear();
    _isActive = false;
  }
}

/// Immutable snapshot of a text message buffer state.
///
/// Useful for exposing buffer state without allowing modifications.
@immutable
class TextMessageBufferSnapshot {
  /// Creates a new [TextMessageBufferSnapshot] with the given state.
  const TextMessageBufferSnapshot({
    required this.isActive,
    required this.messageId,
    required this.user,
    required this.currentContent,
  });

  /// Creates a snapshot from a [TextMessageBuffer].
  factory TextMessageBufferSnapshot.fromBuffer(TextMessageBuffer buffer) {
    return TextMessageBufferSnapshot(
      isActive: buffer.isActive,
      messageId: buffer.messageId,
      user: buffer.user,
      currentContent: buffer.currentContent,
    );
  }

  /// Whether the buffer is currently accumulating a message.
  final bool isActive;

  /// The current message ID being buffered, or null if not active.
  final String? messageId;

  /// The current user for the message being buffered.
  final ChatUser user;

  /// The current accumulated content.
  final String currentContent;
}
