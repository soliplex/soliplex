import 'package:soliplex_client/src/agui/text_message_buffer.dart';
import 'package:soliplex_client/src/models/chat_message.dart';
import 'package:test/test.dart';

void main() {
  group('TextMessageBuffer', () {
    late TextMessageBuffer buffer;

    setUp(() {
      buffer = TextMessageBuffer();
    });

    group('initial state', () {
      test('isActive is false', () {
        expect(buffer.isActive, isFalse);
      });

      test('messageId is null', () {
        expect(buffer.messageId, isNull);
      });

      test('user defaults to assistant', () {
        expect(buffer.user, equals(ChatUser.assistant));
      });

      test('currentContent is empty', () {
        expect(buffer.currentContent, isEmpty);
      });
    });

    group('start', () {
      test('activates the buffer', () {
        buffer.start(messageId: 'msg-123');

        expect(buffer.isActive, isTrue);
        expect(buffer.messageId, equals('msg-123'));
      });

      test('sets the user', () {
        buffer.start(messageId: 'msg-123', user: ChatUser.user);

        expect(buffer.user, equals(ChatUser.user));
      });

      test('defaults user to assistant', () {
        buffer.start(messageId: 'msg-123');

        expect(buffer.user, equals(ChatUser.assistant));
      });

      test('clears any previous content', () {
        // Simulate a previous incomplete message
        buffer
          ..start(messageId: 'msg-1')
          ..append('old content')
          ..reset()
          // Start a new message
          ..start(messageId: 'msg-2');

        expect(buffer.currentContent, isEmpty);
      });

      test('throws when already active', () {
        buffer.start(messageId: 'msg-123');

        expect(
          () => buffer.start(messageId: 'msg-456'),
          throwsStateError,
        );
      });
    });

    group('append', () {
      test('appends content to the buffer', () {
        buffer.start(messageId: 'msg-123');

        expect(
          (buffer..append('Hello, ')).currentContent,
          equals('Hello, '),
        );

        expect(
          (buffer..append('world!')).currentContent,
          equals('Hello, world!'),
        );
      });

      test('handles empty deltas', () {
        buffer.start(messageId: 'msg-123');

        expect(
          (buffer..append('')).currentContent,
          isEmpty,
        );

        buffer
          ..append('content')
          ..append('');
        expect(buffer.currentContent, equals('content'));
      });

      test('handles unicode content', () {
        buffer
          ..start(messageId: 'msg-123')
          ..append('Hello ')
          ..append('\u{1F44B}') // Wave emoji
          ..append(' ')
          ..append('\u{4F60}\u{597D}'); // Chinese "hello"

        expect(
          buffer.currentContent,
          equals('Hello \u{1F44B} \u{4F60}\u{597D}'),
        );
      });

      test('throws when not active', () {
        expect(
          () => buffer.append('content'),
          throwsStateError,
        );
      });
    });

    group('complete', () {
      test('returns a ChatMessage with accumulated content', () {
        buffer
          ..start(messageId: 'msg-123')
          ..append('Hello, ')
          ..append('world!');

        final message = buffer.complete();

        expect(message.id, equals('msg-123'));
        expect(message.user, equals(ChatUser.assistant));
        expect(message.type, equals(MessageType.text));
        expect(message.text, equals('Hello, world!'));
        expect(message.createdAt, isNotNull);
      });

      test('resets the buffer after completion', () {
        buffer
          ..start(messageId: 'msg-123')
          ..append('content')
          ..complete();

        expect(buffer.isActive, isFalse);
        expect(buffer.messageId, isNull);
        expect(buffer.currentContent, isEmpty);
      });

      test('handles empty content', () {
        buffer.start(messageId: 'msg-123');

        final message = buffer.complete();

        expect(message.text, isEmpty);
      });

      test('throws when not active', () {
        expect(
          () => buffer.complete(),
          throwsStateError,
        );
      });

      test('allows starting a new message after completion', () {
        buffer
          ..start(messageId: 'msg-1')
          ..append('first')
          ..complete()
          // Should not throw
          ..start(messageId: 'msg-2')
          ..append('second');
        final message = buffer.complete();

        expect(message.id, equals('msg-2'));
        expect(message.text, equals('second'));
      });
    });

    group('reset', () {
      test('clears all state', () {
        buffer
          ..start(messageId: 'msg-123', user: ChatUser.user)
          ..append('content')
          ..reset();

        expect(buffer.isActive, isFalse);
        expect(buffer.messageId, isNull);
        expect(buffer.user, equals(ChatUser.assistant));
        expect(buffer.currentContent, isEmpty);
      });

      test('can be called when not active', () {
        // Should not throw
        buffer.reset();

        expect(buffer.isActive, isFalse);
      });

      test('allows starting a new message after reset', () {
        buffer
          ..start(messageId: 'msg-1')
          ..append('old content')
          ..reset()
          // Should not throw
          ..start(messageId: 'msg-2');

        expect(buffer.messageId, equals('msg-2'));
        expect(buffer.currentContent, isEmpty);
      });
    });

    group('full lifecycle', () {
      test('handles multiple message cycles', () {
        // First message
        buffer
          ..start(messageId: 'msg-1')
          ..append('First ')
          ..append('message');
        final first = buffer.complete();

        // Second message
        buffer
          ..start(messageId: 'msg-2', user: ChatUser.user)
          ..append('Second ')
          ..append('message');
        final second = buffer.complete();

        // Third message with reset
        buffer
          ..start(messageId: 'msg-3')
          ..append('Discarded')
          ..reset()
          // Fourth message
          ..start(messageId: 'msg-4')
          ..append('Fourth ')
          ..append('message');
        final fourth = buffer.complete();

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
        buffer.start(messageId: 'stream-1');

        const content = 'Hello, world!';
        for (var i = 0; i < content.length; i++) {
          buffer.append(content[i]);
        }

        final message = buffer.complete();
        expect(message.text, equals(content));
      });
    });
  });

  group('TextMessageBufferSnapshot', () {
    test('captures buffer state', () {
      final buffer = TextMessageBuffer()
        ..start(messageId: 'msg-123', user: ChatUser.user)
        ..append('Hello');

      final snapshot = TextMessageBufferSnapshot.fromBuffer(buffer);

      expect(snapshot.isActive, isTrue);
      expect(snapshot.messageId, equals('msg-123'));
      expect(snapshot.user, equals(ChatUser.user));
      expect(snapshot.currentContent, equals('Hello'));
    });

    test('captures inactive buffer state', () {
      final buffer = TextMessageBuffer();

      final snapshot = TextMessageBufferSnapshot.fromBuffer(buffer);

      expect(snapshot.isActive, isFalse);
      expect(snapshot.messageId, isNull);
      expect(snapshot.user, equals(ChatUser.assistant));
      expect(snapshot.currentContent, isEmpty);
    });

    test('is independent of buffer changes', () {
      final buffer = TextMessageBuffer()
        ..start(messageId: 'msg-123')
        ..append('Initial');

      final snapshot = TextMessageBufferSnapshot.fromBuffer(buffer);

      // Modify buffer
      buffer.append(' more content');

      // Snapshot should be unchanged
      expect(snapshot.currentContent, equals('Initial'));
    });

    test('const constructor works', () {
      const snapshot = TextMessageBufferSnapshot(
        isActive: true,
        messageId: 'msg-123',
        user: ChatUser.assistant,
        currentContent: 'test',
      );

      expect(snapshot.isActive, isTrue);
      expect(snapshot.messageId, equals('msg-123'));
    });
  });
}
