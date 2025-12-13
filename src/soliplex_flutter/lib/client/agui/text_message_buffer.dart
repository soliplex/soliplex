/// Buffer for accumulating streaming text message content.
class TextMessageBuffer {
  TextMessageBuffer(this.messageId);

  final String messageId;
  final StringBuffer _buffer = StringBuffer();

  /// Add content to the buffer.
  void add(String id, String content) {
    if (id != messageId) {
      throw StateError(
        'Incoming message id ($id) does not match with original message id ($messageId)',
      );
    }
    _buffer.write(content);
  }

  /// Get the accumulated content.
  String get content => _buffer.toString();

  /// Clear the buffer.
  void clear() {
    _buffer.clear();
  }

  @override
  String toString() => 'TextMessageBuffer(messageId: $messageId)';
}
