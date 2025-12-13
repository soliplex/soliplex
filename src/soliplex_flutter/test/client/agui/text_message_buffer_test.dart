import 'package:soliplex_flutter/client/agui/text_message_buffer.dart';
import 'package:test/test.dart';

void main() {
  group('TextMessageBuffer', () {
    test('creates with message id', () {
      final buffer = TextMessageBuffer('msg-1');

      expect(buffer.messageId, 'msg-1');
      expect(buffer.content, isEmpty);
    });

    test('accumulates content', () {
      final buffer = TextMessageBuffer('msg-1');

      buffer.add('msg-1', 'Hello');
      buffer.add('msg-1', ' ');
      buffer.add('msg-1', 'World');

      expect(buffer.content, 'Hello World');
    });

    test('throws on mismatched id', () {
      final buffer = TextMessageBuffer('msg-1');

      expect(
        () => buffer.add('msg-2', 'content'),
        throwsA(isA<StateError>()),
      );
    });

    test('clear resets content', () {
      final buffer = TextMessageBuffer('msg-1');
      buffer.add('msg-1', 'Hello');

      buffer.clear();

      expect(buffer.content, isEmpty);
    });
  });
}
