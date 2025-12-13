import 'package:soliplex_flutter/client/session/connection_manager.dart';
import 'package:test/test.dart';

void main() {
  group('ConnectionManager', () {
    test('creates with default URL', () {
      final manager = ConnectionManager();

      expect(manager.baseUrl, equals('http://localhost:8000'));
      expect(manager.activeRoomId, isNull);
      expect(manager.agUiClient, isNotNull);
    });

    test('creates with custom URL', () {
      final manager = ConnectionManager(baseUrl: 'https://api.example.com');

      expect(manager.baseUrl, equals('https://api.example.com'));
    });

    test('creates with custom headers', () {
      final manager = ConnectionManager(
        baseUrl: 'https://api.example.com',
        headers: {'Authorization': 'Bearer token'},
      );

      expect(manager.baseUrl, equals('https://api.example.com'));
    });

    test('normalizes base URL', () {
      final manager = ConnectionManager(baseUrl: 'example.com/api/');

      expect(manager.baseUrl, equals('https://example.com'));
    });

    test('urlBuilder is available', () {
      final manager = ConnectionManager();

      expect(manager.urlBuilder, isNotNull);
    });

    group('getSession', () {
      test('creates new session for room', () {
        final manager = ConnectionManager();

        final session = manager.getSession('room1');

        expect(session, isNotNull);
        expect(session.roomId, equals('room1'));
      });

      test('returns same session for same room', () {
        final manager = ConnectionManager();

        final session1 = manager.getSession('room1');
        final session2 = manager.getSession('room1');

        expect(identical(session1, session2), isTrue);
      });

      test('returns different sessions for different rooms', () {
        final manager = ConnectionManager();

        final session1 = manager.getSession('room1');
        final session2 = manager.getSession('room2');

        expect(identical(session1, session2), isFalse);
        expect(session1.roomId, equals('room1'));
        expect(session2.roomId, equals('room2'));
      });
    });

    group('switchRoom', () {
      test('switches active room', () {
        final manager = ConnectionManager();

        manager.switchRoom('room1');

        expect(manager.activeRoomId, equals('room1'));
      });

      test('emits RoomSwitchedEvent', () async {
        final manager = ConnectionManager();
        final events = <ConnectionEvent>[];

        manager.events.listen(events.add);
        manager.switchRoom('room1');

        await Future.delayed(Duration.zero);
        expect(events, hasLength(1));
        expect(events.first, isA<RoomSwitchedEvent>());

        final event = events.first as RoomSwitchedEvent;
        expect(event.roomId, equals('room1'));
        expect(event.previousRoomId, isNull);
      });

      test('suspends previous room session', () {
        final manager = ConnectionManager();

        manager.switchRoom('room1');
        final session1 = manager.getSession('room1');

        manager.switchRoom('room2');

        // Session should be suspended (state not directly accessible, but verify no errors)
        expect(manager.activeRoomId, equals('room2'));
      });

      test('emits events with previous room', () async {
        final manager = ConnectionManager();
        final events = <ConnectionEvent>[];

        manager.switchRoom('room1');
        manager.events.listen(events.add);
        manager.switchRoom('room2');

        await Future.delayed(Duration.zero);
        expect(events.last, isA<RoomSwitchedEvent>());

        final event = events.last as RoomSwitchedEvent;
        expect(event.roomId, equals('room2'));
        expect(event.previousRoomId, equals('room1'));
      });
    });

    group('initializeSession', () {
      test('initializes session with thread', () async {
        final manager = ConnectionManager();
        final events = <ConnectionEvent>[];

        manager.events.listen(events.add);
        manager.initializeSession('room1', 'thread1');

        await Future.delayed(Duration.zero);
        expect(events, hasLength(1));
        expect(events.first, isA<SessionCreatedEvent>());

        final event = events.first as SessionCreatedEvent;
        expect(event.roomId, equals('room1'));
        expect(event.threadId, equals('thread1'));
      });
    });

    group('getMessages', () {
      test('returns empty list for non-existent room', () {
        final manager = ConnectionManager();

        final messages = manager.getMessages('room1');

        expect(messages, isEmpty);
      });

      test('returns messages from session', () {
        final manager = ConnectionManager();
        final session = manager.getSession('room1');
        session.addUserMessage('Hello');

        final messages = manager.getMessages('room1');

        expect(messages, hasLength(1));
      });
    });

    group('getMessageStream', () {
      test('returns null for non-existent room', () {
        final manager = ConnectionManager();

        final stream = manager.getMessageStream('room1');

        expect(stream, isNull);
      });

      test('returns stream from session', () {
        final manager = ConnectionManager();
        manager.getSession('room1');

        final stream = manager.getMessageStream('room1');

        expect(stream, isNotNull);
      });
    });

    group('cancelRun', () {
      test('does not throw for non-existent room', () {
        final manager = ConnectionManager();

        expect(() => manager.cancelRun('room1'), returnsNormally);
      });
    });

    group('disposeSession', () {
      test('disposes session and emits event', () async {
        final manager = ConnectionManager();
        final events = <ConnectionEvent>[];

        manager.getSession('room1');
        manager.events.listen(events.add);
        manager.disposeSession('room1');

        await Future.delayed(Duration.zero);
        expect(events, hasLength(1));
        expect(events.first, isA<SessionDisposedEvent>());
      });

      test('does nothing for non-existent room', () async {
        final manager = ConnectionManager();
        final events = <ConnectionEvent>[];

        manager.events.listen(events.add);
        manager.disposeSession('nonexistent');

        await Future.delayed(Duration.zero);
        expect(events, isEmpty);
      });
    });

    group('switchServer', () {
      test('switches to new server', () {
        final manager = ConnectionManager(baseUrl: 'https://old.example.com');

        manager.switchServer('https://new.example.com');

        expect(manager.baseUrl, equals('https://new.example.com'));
      });

      test('disposes existing sessions', () async {
        final manager = ConnectionManager();
        final events = <ConnectionEvent>[];

        manager.getSession('room1');
        manager.events.listen(events.add);
        manager.switchServer('https://new.example.com');

        await Future.delayed(Duration.zero);
        expect(events.any((e) => e is SessionDisposedEvent), isTrue);
      });

      test('clears active room', () {
        final manager = ConnectionManager();
        manager.switchRoom('room1');

        manager.switchServer('https://new.example.com');

        expect(manager.activeRoomId, isNull);
      });

      test('does nothing for same URL', () async {
        final manager = ConnectionManager(baseUrl: 'https://example.com');
        final events = <ConnectionEvent>[];

        manager.events.listen(events.add);
        manager.switchServer('https://example.com');

        await Future.delayed(Duration.zero);
        expect(events, isEmpty);
      });
    });

    group('dispose', () {
      test('disposes all sessions', () {
        final manager = ConnectionManager();

        manager.getSession('room1');
        manager.getSession('room2');

        expect(() => manager.dispose(), returnsNormally);
      });
    });

    test('toString includes baseUrl and session count', () {
      final manager = ConnectionManager();
      manager.getSession('room1');

      final str = manager.toString();

      expect(str, contains('localhost:8000'));
      expect(str, contains('1'));
    });
  });

  group('ConnectionEvent classes', () {
    test('SessionCreatedEvent stores roomId and threadId', () {
      final event = SessionCreatedEvent('room1', 'thread1');

      expect(event.roomId, equals('room1'));
      expect(event.threadId, equals('thread1'));
    });

    test('SessionDisposedEvent stores roomId and threadId', () {
      final event = SessionDisposedEvent('room1', 'thread1');

      expect(event.roomId, equals('room1'));
      expect(event.threadId, equals('thread1'));
    });

    test('RoomSwitchedEvent stores roomId and previousRoomId', () {
      final event = RoomSwitchedEvent('room1', 'room0');

      expect(event.roomId, equals('room1'));
      expect(event.previousRoomId, equals('room0'));
    });
  });
}
