import 'package:soliplex_client/src/agui/text_message_buffer.dart';
import 'package:soliplex_client/src/models/chat_message.dart';
import 'package:test/test.dart';

void main() {
  group('TextMessageBuffer', () {
    group('initial state (empty)', () {
      test('isActive is false', () {
        expect(TextMessageBuffer.empty.isActive, isFalse);
      });

      test('empty is InactiveTextBuffer', () {
        expect(TextMessageBuffer.empty, isA<InactiveTextBuffer>());
      });

      test('currentContent is empty', () {
        expect(TextMessageBuffer.empty.currentContent, isEmpty);
      });
    });

    group('start', () {
      test('activates the buffer and returns ActiveTextBuffer', () {
        final buffer = TextMessageBuffer.empty.start(messageId: 'msg-123');

        expect(buffer.isActive, isTrue);
        expect(buffer, isA<ActiveTextBuffer>());
        expect((buffer as ActiveTextBuffer).messageId, equals('msg-123'));
      });

      test('sets the user', () {
        final buffer = TextMessageBuffer.empty.start(
          messageId: 'msg-123',
          user: ChatUser.user,
        );

        expect((buffer as ActiveTextBuffer).user, equals(ChatUser.user));
      });

      test('defaults user to assistant', () {
        final buffer = TextMessageBuffer.empty.start(messageId: 'msg-123');

        expect((buffer as ActiveTextBuffer).user, equals(ChatUser.assistant));
      });

      test('clears any previous content', () {
        // Simulate a previous incomplete message
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-1');
        buffer = (buffer as ActiveTextBuffer).append('old content');
        buffer = buffer.reset();
        // Start a new message
        buffer = buffer.start(messageId: 'msg-2');

        expect(buffer.currentContent, isEmpty);
      });

      test('throws when already active', () {
        final buffer = TextMessageBuffer.empty.start(messageId: 'msg-123');

        expect(
          () => buffer.start(messageId: 'msg-456'),
          throwsStateError,
        );
      });
    });

    group('append', () {
      test('appends content to the buffer', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-123')
            as ActiveTextBuffer;

        buffer = buffer.append('Hello, ');
        expect(buffer.currentContent, equals('Hello, '));

        buffer = buffer.append('world!');
        expect(buffer.currentContent, equals('Hello, world!'));
      });

      test('handles empty deltas', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-123')
            as ActiveTextBuffer;

        buffer = buffer.append('');
        expect(buffer.currentContent, isEmpty);

        buffer = buffer.append('content').append('');
        expect(buffer.currentContent, equals('content'));
      });

      test('handles unicode content', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-123')
            as ActiveTextBuffer;
        buffer = buffer
            .append('Hello ')
            .append('\u{1F44B}') // Wave emoji
            .append(' ')
            .append('\u{4F60}\u{597D}'); // Chinese "hello"

        expect(
          buffer.currentContent,
          equals('Hello \u{1F44B} \u{4F60}\u{597D}'),
        );
      });

      test('append not available on InactiveTextBuffer', () {
        // InactiveTextBuffer doesn't have append method - compile-time safe
        expect(TextMessageBuffer.empty, isA<InactiveTextBuffer>());
        // The following would not compile:
        // TextMessageBuffer.empty.append('content');
      });
    });

    group('complete', () {
      test('returns a tuple with reset buffer and ChatMessage', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-123')
            as ActiveTextBuffer;
        buffer = buffer.append('Hello, ').append('world!');

        final (newBuffer, message) = buffer.complete();

        expect(newBuffer.isActive, isFalse);
        expect(newBuffer, isA<InactiveTextBuffer>());
        expect(message.id, equals('msg-123'));
        expect(message.user, equals(ChatUser.assistant));
        expect(message, isA<TextMessage>());
        expect(message.text, equals('Hello, world!'));
        expect(message.createdAt, isNotNull);
      });

      test('resets the buffer after completion', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-123')
            as ActiveTextBuffer;
        buffer = buffer.append('content');

        final (newBuffer, _) = buffer.complete();

        expect(newBuffer.isActive, isFalse);
        expect(newBuffer, isA<InactiveTextBuffer>());
        expect(newBuffer.currentContent, isEmpty);
      });

      test('handles empty content', () {
        final buffer = TextMessageBuffer.empty.start(messageId: 'msg-123')
            as ActiveTextBuffer;

        final (_, message) = buffer.complete();

        expect(message.text, isEmpty);
      });

      test('complete not available on InactiveTextBuffer', () {
        // InactiveTextBuffer doesn't have complete method - compile-time safe
        expect(TextMessageBuffer.empty, isA<InactiveTextBuffer>());
      });

      test('allows starting a new message after completion', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-1')
            as ActiveTextBuffer;
        buffer = buffer.append('first');

        final (newBuffer1, _) = buffer.complete();

        // Should not throw
        var buffer2 = newBuffer1.start(messageId: 'msg-2') as ActiveTextBuffer;
        buffer2 = buffer2.append('second');

        final (_, message) = buffer2.complete();

        expect(message.id, equals('msg-2'));
        expect(message.text, equals('second'));
      });
    });

    group('reset', () {
      test('clears all state', () {
        var buffer = TextMessageBuffer.empty.start(
          messageId: 'msg-123',
          user: ChatUser.user,
        ) as ActiveTextBuffer;
        buffer = buffer.append('content');
        final resetBuffer = buffer.reset();

        expect(resetBuffer.isActive, isFalse);
        expect(resetBuffer, isA<InactiveTextBuffer>());
        expect(resetBuffer.currentContent, isEmpty);
      });

      test('can be called when not active', () {
        // Should not throw
        final buffer = TextMessageBuffer.empty.reset();

        expect(buffer.isActive, isFalse);
      });

      test('allows starting a new message after reset', () {
        var buffer = TextMessageBuffer.empty.start(messageId: 'msg-1')
            as ActiveTextBuffer;
        buffer = buffer.append('old content');
        final resetBuffer = buffer.reset();
        // Should not throw
        final newBuffer =
            resetBuffer.start(messageId: 'msg-2') as ActiveTextBuffer;

        expect(newBuffer.messageId, equals('msg-2'));
        expect(newBuffer.currentContent, isEmpty);
      });
    });

    group('full lifecycle', () {
      test('handles multiple message cycles', () {
        TextMessageBuffer buffer = TextMessageBuffer.empty;

        // First message
        var active1 = buffer.start(messageId: 'msg-1') as ActiveTextBuffer;
        active1 = active1.append('First ').append('message');
        final (buffer1, first) = active1.complete();
        buffer = buffer1;

        // Second message
        var active2 = buffer.start(messageId: 'msg-2', user: ChatUser.user)
            as ActiveTextBuffer;
        active2 = active2.append('Second ').append('message');
        final (buffer2, second) = active2.complete();
        buffer = buffer2;

        // Third message with reset
        var active3 = buffer.start(messageId: 'msg-3') as ActiveTextBuffer;
        active3 = active3.append('Discarded');
        buffer = active3.reset();

        // Fourth message
        var active4 = buffer.start(messageId: 'msg-4') as ActiveTextBuffer;
        active4 = active4.append('Fourth ').append('message');
        final (_, fourth) = active4.complete();

        expect(first.id, equals('msg-1'));
        expect(first.text, equals('First message'));
        expect(first.user, equals(ChatUser.assistant));

        expect(second.id, equals('msg-2'));
        expect(second.text, equals('Second message'));
        expect(second.user, equals(ChatUser.user));

        expect(fourth.id, equals('msg-4'));
        expect(fourth.text, equals('Fourth message'));
      });

      test('handles streaming simulation', () {
        // Simulates receiving content character by character
        var buffer = TextMessageBuffer.empty.start(messageId: 'stream-1')
            as ActiveTextBuffer;

        const content = 'Hello, world!';
        for (var i = 0; i < content.length; i++) {
          buffer = buffer.append(content[i]);
        }

        final (_, message) = buffer.complete();
        expect(message.text, equals(content));
      });
    });

    group('equality', () {
      test('empty buffers are equal', () {
        expect(TextMessageBuffer.empty, equals(TextMessageBuffer.empty));
      });

      test('buffers with same state are equal', () {
        final buffer1 = TextMessageBuffer.empty.start(messageId: 'msg-1');
        final buffer2 = TextMessageBuffer.empty.start(messageId: 'msg-1');
        expect(buffer1, equals(buffer2));
      });

      test('buffers with different state are not equal', () {
        final buffer1 = TextMessageBuffer.empty.start(messageId: 'msg-1');
        final buffer2 = TextMessageBuffer.empty.start(messageId: 'msg-2');
        expect(buffer1, isNot(equals(buffer2)));
      });
    });
  });
}
