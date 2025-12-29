import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/network/connection_events.dart';
import 'package:soliplex/core/network/http_transport.dart';
import 'package:soliplex/core/network/room_session.dart';

// Mock for AgUiClient
class MockAgUiClient extends Mock implements ag_ui.AgUiClient {}

// Mock for HttpTransport
class MockHttpTransport extends Mock implements HttpTransport {}

// Fake classes for mocktail
class FakeUri extends Fake implements Uri {}

/// Phase 2 tests for RoomSession enhanced features.
///
/// Tests cover:
/// - Inactivity timer for backgrounded sessions
/// - isExpired() method for timestamp-based cleanup
/// - Events emitted with serverId
/// - ConnectionInfo with serverId
void main() {
  late MockHttpTransport transport;
  late RoomSession session;

  setUpAll(() {
    registerFallbackValue(FakeUri());
  });

  setUp(() {
    transport = MockHttpTransport();

    // Setup default mock behavior for post
    when(() => transport.post(any(), any())).thenAnswer(
      (_) async => {
        'thread_id': 'test-thread-id',
        'runs': {'run-1': {}},
      },
    );

    // Setup default mock behavior for cancelRun
    when(
      () => transport.cancelRun(
        roomId: any(named: 'roomId'),
        threadId: any(named: 'threadId'),
        runId: any(named: 'runId'),
      ),
    ).thenAnswer((_) async {});

    session = RoomSession(
      roomId: 'test-room',
      serverId: 'test-server',
      baseUrl: 'http://localhost:8080',
      transport: transport,
    );
  });

  tearDown(() {
    if (!session.isDisposed) {
      session.dispose();
    }
  });

  group('RoomSession Inactivity Timer Tests', () {
    test('inactivityTimeout defaults to 24 hours', () {
      final defaultSession = RoomSession(
        roomId: 'room',
        baseUrl: 'http://localhost',
        transport: transport,
      );

      expect(
        defaultSession.inactivityTimeout,
        equals(const Duration(hours: 24)),
      );

      defaultSession.dispose();
    });

    test('inactivityTimeout can be customized', () {
      final customSession = RoomSession(
        roomId: 'room',
        baseUrl: 'http://localhost',
        transport: transport,
        inactivityTimeout: const Duration(hours: 1),
      );

      expect(customSession.inactivityTimeout, equals(const Duration(hours: 1)));

      customSession.dispose();
    });

    test('onInactivityTimeout callback is called when timer fires', () {
      fakeAsync((async) {
        var callbackCalled = false;

        final timedSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(hours: 1),
          onInactivityTimeout: () => callbackCalled = true,
        );

        // Suspend to start the timer
        timedSession.suspend();

        // Advance time past the timeout
        async.elapse(const Duration(hours: 1, minutes: 1));

        expect(callbackCalled, isTrue);

        timedSession.dispose();
      });
    });

    test('timer is cancelled when session resumes', () {
      fakeAsync((async) {
        var callbackCalled = false;

        final timedSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(hours: 1),
          onInactivityTimeout: () => callbackCalled = true,
        );

        // Suspend to start the timer
        timedSession.suspend();

        // Advance time but not past timeout
        async.elapse(const Duration(minutes: 30));

        // Resume to cancel the timer
        timedSession.resume();

        // Advance past original timeout
        async.elapse(const Duration(hours: 1));

        // Callback should NOT have been called
        expect(callbackCalled, isFalse);

        timedSession.dispose();
      });
    });

    test('timer is cancelled when session is disposed', () {
      fakeAsync((async) {
        var callbackCalled = false;

        final timedSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(hours: 1),
          onInactivityTimeout: () => callbackCalled = true,
        );

        // Suspend to start the timer
        timedSession.suspend();

        // Dispose before timeout
        timedSession.dispose();

        // Advance past original timeout
        async.elapse(const Duration(hours: 2));

        // Callback should NOT have been called
        expect(callbackCalled, isFalse);
      });
    });

    // ignore: lines_longer_than_80_chars (auto-documented)
    test(
      'timer callback does not fire if session is no longer backgrounded',
      () {
        fakeAsync((async) {
          var callbackCalled = false;

          final timedSession = RoomSession(
            roomId: 'room',
            baseUrl: 'http://localhost',
            transport: transport,
            inactivityTimeout: const Duration(hours: 1),
            onInactivityTimeout: () => callbackCalled = true,
          );

          // Suspend to start the timer
          timedSession.suspend();

          // Resume before timeout
          timedSession.resume();

          // Suspend again (creates new timer)
          timedSession.suspend();

          // Advance past first timer but before second
          async.elapse(const Duration(minutes: 30));

          // Should not have fired because we resumed and the new timer hasn't
          // expired
          expect(callbackCalled, isFalse);

          timedSession.dispose();
        });
      },
    );

    test('new timer replaces old timer on subsequent suspends', () {
      fakeAsync((async) {
        var callbackCount = 0;

        final timedSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(hours: 1),
          onInactivityTimeout: () => callbackCount++,
        );

        // Suspend multiple times rapidly
        timedSession.suspend();
        timedSession.resume();
        timedSession.suspend();
        timedSession.resume();
        timedSession.suspend();

        // Advance past timeout
        async.elapse(const Duration(hours: 2));

        // Callback should only have been called once
        expect(callbackCount, equals(1));

        timedSession.dispose();
      });
    });
  });

  group('RoomSession isExpired() Tests', () {
    test('returns false when not backgrounded', () {
      expect(session.state, equals(SessionState.active));
      expect(session.isExpired(), isFalse);
    });

    test('returns false when backgrounded but not past timeout', () {
      session.suspend();
      expect(session.state, equals(SessionState.backgrounded));
      expect(session.isExpired(), isFalse);
    });

    test('returns false when backgrounded with no lastActivity', () {
      // Fresh session has no lastActivity
      final freshSession = RoomSession(
        roomId: 'room',
        baseUrl: 'http://localhost',
        transport: transport,
        inactivityTimeout: const Duration(milliseconds: 1),
      );

      freshSession.suspend();
      expect(freshSession.isExpired(), isFalse);

      freshSession.dispose();
    });

    test(
      'transitions to suspended when backgrounded and past timeout',
      () async {
        final mockClient = MockAgUiClient();
        final shortTimeoutSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(milliseconds: 50),
        );

        // Initialize to set lastActivity
        await shortTimeoutSession.initialize(agUiClient: mockClient);

        // Suspend
        shortTimeoutSession.suspend();

        // Wait past timeout
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Timer should have fired and hibernated the session
        expect(shortTimeoutSession.state, equals(SessionState.suspended));

        shortTimeoutSession.dispose();
      },
    );

    test('returns false after resume even if time passed', () async {
      final mockClient = MockAgUiClient();
      final shortTimeoutSession = RoomSession(
        roomId: 'room',
        baseUrl: 'http://localhost',
        transport: transport,
        inactivityTimeout: const Duration(milliseconds: 50),
      );

      await shortTimeoutSession.initialize(agUiClient: mockClient);
      shortTimeoutSession.suspend();
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // Resume updates lastActivity
      shortTimeoutSession.resume();

      // State is no longer backgrounded, so isExpired should be false
      expect(shortTimeoutSession.isExpired(), isFalse);

      shortTimeoutSession.dispose();
    });
  });

  group('RoomSession Events with serverId Tests', () {
    test('SessionCreatedEvent includes serverId', () async {
      final mockClient = MockAgUiClient();
      final events = <ConnectionEvent>[];
      session.events.listen(events.add);

      await session.initialize(agUiClient: mockClient);
      await Future.delayed(Duration.zero);

      final createdEvent = events.whereType<SessionCreatedEvent>().first;
      expect(createdEvent.serverId, equals('test-server'));
    });

    test('SessionSuspendedEvent includes serverId', () async {
      final mockClient = MockAgUiClient();
      await session.initialize(agUiClient: mockClient);

      final events = <ConnectionEvent>[];
      session.events.listen(events.add);

      session.suspend();
      await Future.delayed(Duration.zero);

      final suspendedEvent = events.whereType<SessionSuspendedEvent>().first;
      expect(suspendedEvent.serverId, equals('test-server'));
    });

    test('SessionResumedEvent includes serverId', () async {
      final mockClient = MockAgUiClient();
      await session.initialize(agUiClient: mockClient);

      session.suspend();

      final events = <ConnectionEvent>[];
      session.events.listen(events.add);

      session.resume();
      await Future.delayed(Duration.zero);

      final resumedEvent = events.whereType<SessionResumedEvent>().first;
      expect(resumedEvent.serverId, equals('test-server'));
    });

    test('SessionDisposedEvent includes serverId', () async {
      final mockClient = MockAgUiClient();
      await session.initialize(agUiClient: mockClient);

      final events = <ConnectionEvent>[];
      session.events.listen(events.add);

      session.dispose();
      await Future.delayed(Duration.zero);

      final disposedEvent = events.whereType<SessionDisposedEvent>().first;
      expect(disposedEvent.serverId, equals('test-server'));
    });
  });

  group('ConnectionInfo with serverId Tests', () {
    test('connectionInfo getter includes serverId', () {
      final info = session.connectionInfo;

      expect(info.serverId, equals('test-server'));
      expect(info.roomId, equals('test-room'));
      expect(info.state, equals(SessionState.active));
    });

    test('connectionInfo updates with state changes', () async {
      expect(session.connectionInfo.state, equals(SessionState.active));

      session.suspend();
      expect(session.connectionInfo.state, equals(SessionState.backgrounded));

      session.resume();
      expect(session.connectionInfo.state, equals(SessionState.active));
    });

    test(
      'connectionInfo includes thread and run info after initialization',
      () async {
        final mockClient = MockAgUiClient();
        await session.initialize(agUiClient: mockClient);

        final info = session.connectionInfo;
        expect(info.threadId, isNotNull);
        expect(info.activeRunId, isNotNull);
      },
    );
  });

  group('Session without serverId', () {
    test('events have null serverId when session has no serverId', () async {
      final noServerSession = RoomSession(
        roomId: 'room',
        baseUrl: 'http://localhost',
        transport: transport,
      );

      final mockClient = MockAgUiClient();
      final events = <ConnectionEvent>[];
      noServerSession.events.listen(events.add);

      await noServerSession.initialize(agUiClient: mockClient);
      await Future.delayed(Duration.zero);

      final createdEvent = events.whereType<SessionCreatedEvent>().first;
      expect(createdEvent.serverId, isNull);

      noServerSession.dispose();
    });

    test('connectionInfo has null serverId when session has no serverId', () {
      final noServerSession = RoomSession(
        roomId: 'room',
        baseUrl: 'http://localhost',
        transport: transport,
      );

      expect(noServerSession.connectionInfo.serverId, isNull);

      noServerSession.dispose();
    });
  });

  group('Rapid Timer Operations', () {
    test('handles rapid suspend/resume without timer leaks', () {
      fakeAsync((async) {
        var callbackCount = 0;

        final timedSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(hours: 1),
          onInactivityTimeout: () => callbackCount++,
        );

        // Rapid suspend/resume 100 times
        for (var i = 0; i < 100; i++) {
          timedSession.suspend();
          timedSession.resume();
        }

        // Advance way past any possible timeout
        async.elapse(const Duration(hours: 200));

        // No callbacks should have fired since all were cancelled
        expect(callbackCount, equals(0));

        timedSession.dispose();
      });
    });

    test('dispose during timer does not cause errors', () {
      fakeAsync((async) {
        final timedSession = RoomSession(
          roomId: 'room',
          baseUrl: 'http://localhost',
          transport: transport,
          inactivityTimeout: const Duration(hours: 1),
        );

        timedSession.suspend();

        // Dispose mid-timer
        async.elapse(const Duration(minutes: 30));
        timedSession.dispose();

        // Advancing should not cause errors
        async.elapse(const Duration(hours: 2));
      });
    });
  });
}
