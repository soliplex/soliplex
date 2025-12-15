import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/connection_events.dart';

/// Phase 2 tests for connection events with serverId support.
///
/// Tests verify that all connection events properly support and propagate
/// serverId for multi-server routing.
void main() {
  group('ConnectionEvent serverId Tests', () {
    group('SessionCreatedEvent', () {
      test('includes serverId in constructor', () {
        final event = SessionCreatedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.roomId, equals('room-1'));
        expect(event.threadId, equals('thread-1'));
      });

      test('serverId defaults to null', () {
        final event = SessionCreatedEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, isNull);
      });

      test('toString includes serverId', () {
        final event = SessionCreatedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.toString(), contains('server-1'));
      });
    });

    group('RoomSwitchedEvent', () {
      test('includes serverId in constructor', () {
        final event = RoomSwitchedEvent(
          serverId: 'server-1',
          roomId: 'room-2',
          previousRoomId: 'room-1',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.roomId, equals('room-2'));
        expect(event.previousRoomId, equals('room-1'));
      });

      test('serverId defaults to null', () {
        final event = RoomSwitchedEvent(roomId: 'room-2');

        expect(event.serverId, isNull);
      });

      test('toString includes serverId', () {
        final event = RoomSwitchedEvent(serverId: 'server-1', roomId: 'room-2');

        expect(event.toString(), contains('server-1'));
      });
    });

    group('RunStartedEvent', () {
      test('includes serverId in constructor', () {
        final event = RunStartedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.roomId, equals('room-1'));
        expect(event.threadId, equals('thread-1'));
        expect(event.runId, equals('run-1'));
      });

      test('serverId defaults to null', () {
        final event = RunStartedEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.serverId, isNull);
      });

      test('toString includes serverId', () {
        final event = RunStartedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.toString(), contains('server-1'));
      });
    });

    group('RunCompletedEvent', () {
      test('includes serverId in constructor', () {
        final event = RunCompletedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.serverId, equals('server-1'));
      });

      test('serverId defaults to null', () {
        final event = RunCompletedEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.serverId, isNull);
      });

      test('toString includes serverId', () {
        final event = RunCompletedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.toString(), contains('server-1'));
      });
    });

    group('RunCancelledEvent', () {
      test('includes serverId in constructor', () {
        final event = RunCancelledEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
          reason: 'User cancelled',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.reason, equals('User cancelled'));
      });

      test('serverId defaults to null', () {
        final event = RunCancelledEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.serverId, isNull);
      });

      test('toString includes serverId', () {
        final event = RunCancelledEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(event.toString(), contains('server-1'));
      });
    });

    group('RunFailedEvent', () {
      test('includes serverId in constructor', () {
        final event = RunFailedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
          error: 'Something went wrong',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.error, equals('Something went wrong'));
      });

      test('serverId defaults to null', () {
        final event = RunFailedEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
          error: 'Error',
        );

        expect(event.serverId, isNull);
      });

      test('toString includes serverId', () {
        final event = RunFailedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
          error: 'Error',
        );

        expect(event.toString(), contains('server-1'));
      });
    });

    group('SessionSuspendedEvent', () {
      test('includes serverId in constructor', () {
        final event = SessionSuspendedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.roomId, equals('room-1'));
        expect(event.threadId, equals('thread-1'));
      });

      test('serverId defaults to null', () {
        final event = SessionSuspendedEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, isNull);
      });
    });

    group('SessionResumedEvent', () {
      test('includes serverId in constructor', () {
        final event = SessionResumedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.roomId, equals('room-1'));
        expect(event.threadId, equals('thread-1'));
      });

      test('serverId defaults to null', () {
        final event = SessionResumedEvent(
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, isNull);
      });
    });

    group('SessionDisposedEvent', () {
      test('includes serverId in constructor', () {
        final event = SessionDisposedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
          threadId: 'thread-1',
        );

        expect(event.serverId, equals('server-1'));
        expect(event.roomId, equals('room-1'));
        expect(event.threadId, equals('thread-1'));
      });

      test('serverId defaults to null', () {
        final event = SessionDisposedEvent(roomId: 'room-1');

        expect(event.serverId, isNull);
      });

      test('threadId is optional', () {
        final event = SessionDisposedEvent(
          serverId: 'server-1',
          roomId: 'room-1',
        );

        expect(event.threadId, isNull);
      });
    });
  });

  group('ConnectionInfo serverId Tests', () {
    test('includes serverId in constructor', () {
      const info = ConnectionInfo(
        serverId: 'server-1',
        roomId: 'room-1',
        threadId: 'thread-1',
        activeRunId: 'run-1',
        state: SessionState.active,
      );

      expect(info.serverId, equals('server-1'));
      expect(info.roomId, equals('room-1'));
      expect(info.threadId, equals('thread-1'));
      expect(info.activeRunId, equals('run-1'));
      expect(info.state, equals(SessionState.active));
    });

    test('serverId defaults to null', () {
      const info = ConnectionInfo(roomId: 'room-1', state: SessionState.active);

      expect(info.serverId, isNull);
    });

    test('toString includes serverId', () {
      const info = ConnectionInfo(
        serverId: 'server-1',
        roomId: 'room-1',
        state: SessionState.active,
      );

      expect(info.toString(), contains('server: server-1'));
    });

    test('isActive returns true for active and streaming states', () {
      const activeInfo = ConnectionInfo(
        roomId: 'room-1',
        state: SessionState.active,
      );
      const streamingInfo = ConnectionInfo(
        roomId: 'room-1',
        state: SessionState.streaming,
      );
      const backgroundedInfo = ConnectionInfo(
        roomId: 'room-1',
        state: SessionState.backgrounded,
      );
      const disposedInfo = ConnectionInfo(
        roomId: 'room-1',
        state: SessionState.disposed,
      );

      expect(activeInfo.isActive, isTrue);
      expect(streamingInfo.isActive, isTrue);
      expect(backgroundedInfo.isActive, isFalse);
      expect(disposedInfo.isActive, isFalse);
    });

    test('isStreaming returns true only for streaming state', () {
      const activeInfo = ConnectionInfo(
        roomId: 'room-1',
        state: SessionState.active,
      );
      const streamingInfo = ConnectionInfo(
        roomId: 'room-1',
        state: SessionState.streaming,
      );

      expect(activeInfo.isStreaming, isFalse);
      expect(streamingInfo.isStreaming, isTrue);
    });
  });

  group('ConnectionEvent timestamp Tests', () {
    test('timestamp defaults to now', () {
      final before = DateTime.now();
      final event = SessionCreatedEvent(roomId: 'room-1', threadId: 'thread-1');
      final after = DateTime.now();

      expect(
        event.timestamp.isAfter(before) || event.timestamp == before,
        isTrue,
      );
      expect(
        event.timestamp.isBefore(after) || event.timestamp == after,
        isTrue,
      );
    });

    test('timestamp can be specified', () {
      final customTime = DateTime(2024, 1, 1, 12);
      final event = SessionCreatedEvent(
        roomId: 'room-1',
        threadId: 'thread-1',
        timestamp: customTime,
      );

      expect(event.timestamp, equals(customTime));
    });
  });

  group('Event Type Verification', () {
    test('all events extend ConnectionEvent', () {
      expect(
        SessionCreatedEvent(roomId: 'r', threadId: 't'),
        isA<ConnectionEvent>(),
      );
      expect(RoomSwitchedEvent(roomId: 'r'), isA<ConnectionEvent>());
      expect(
        RunStartedEvent(roomId: 'r', threadId: 't', runId: 'run'),
        isA<ConnectionEvent>(),
      );
      expect(
        RunCompletedEvent(roomId: 'r', threadId: 't', runId: 'run'),
        isA<ConnectionEvent>(),
      );
      expect(
        RunCancelledEvent(roomId: 'r', threadId: 't', runId: 'run'),
        isA<ConnectionEvent>(),
      );
      expect(
        RunFailedEvent(roomId: 'r', threadId: 't', runId: 'run', error: 'e'),
        isA<ConnectionEvent>(),
      );
      expect(
        SessionSuspendedEvent(roomId: 'r', threadId: 't'),
        isA<ConnectionEvent>(),
      );
      expect(
        SessionResumedEvent(roomId: 'r', threadId: 't'),
        isA<ConnectionEvent>(),
      );
      expect(SessionDisposedEvent(roomId: 'r'), isA<ConnectionEvent>());
    });
  });
}
