/// Buffer for accumulating streamed text message content.
class TextMessageBuffer {
  TextMessageBuffer(this.messageId);
  final String messageId;
  final StringBuffer _buffer = StringBuffer();

  void add(String id, String content) {
    if (id != messageId) {
      throw StateError(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'Incoming message id ($id) does not match with original message id ($messageId)',
      );
    }

    _buffer.write(content);
  }

  String get content => _buffer.toString();
}
