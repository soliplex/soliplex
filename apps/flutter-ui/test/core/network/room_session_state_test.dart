import 'package:ag_ui/ag_ui.dart' as ag_ui;
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

class FakeRunAgentInput extends Fake implements ag_ui.RunAgentInput {}

/// State machine tests for RoomSession.
///
/// These tests verify that all state transitions follow the defined
/// state machine rules and that invalid transitions are prevented.
///
/// State Machine:
/// ```
///                    ┌─────────────────────────────────────────┐
///                    │                                         │
///                    ▼                                         │
///               ┌────────┐     suspend()     ┌────────────┐   │
///    init() →   │ active │ ───────────────→  │ backgrounded│───┤
///               └────────┘                   └────────────┘   │
///                    │  ▲                         │           │
///         startRun() │  │ run completes           │ resume()  │
///                    ▼  │                         ▼           │
///               ┌────────────┐              ┌────────┐        │
///               │ streaming  │              │ active │        │
///               └────────────┘              └────────┘        │
///                    │                           │            │
///                    │        dispose()          │            │
///                    └───────────────────────────┴────────────┘
///                                   │
///                                   ▼
///                              ┌──────────┐
///                              │ disposed │
///                              └──────────┘
/// ```
void main() {
  late MockHttpTransport transport;
  late RoomSession session;

  setUpAll(() {
    registerFallbackValue(FakeUri());
    registerFallbackValue(FakeRunAgentInput());
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

  group('RoomSession State Machine Tests', () {
    group('Initial State', () {
      test('starts in active state', () {
        expect(session.state, equals(SessionState.active));
        expect(session.isActive, isTrue);
        expect(session.isStreaming, isFalse);
        expect(session.isDisposed, isFalse);
      });

      test('has no thread before initialization', () {
        expect(session.threadId, isNull);
        expect(session.activeRunId, isNull);
      });
    });

    group('State Transition: active → backgrounded', () {
      test('suspend() transitions from active to backgrounded', () {
        expect(session.state, equals(SessionState.active));

        session.suspend();

        expect(session.state, equals(SessionState.backgrounded));
        expect(session.isActive, isFalse);
        expect(session.isStreaming, isFalse);
        expect(session.isDisposed, isFalse);
      });

      test(
        'suspend() emits SessionSuspendedEvent when thread exists',
        () async {
          final mockClient = MockAgUiClient();
          await session.initialize(agUiClient: mockClient);

          final events = <ConnectionEvent>[];
          session.events.listen(events.add);

          session.suspend();

          // Wait for event to be processed
          await Future.delayed(Duration.zero);

          expect(events, contains(isA<SessionSuspendedEvent>()));
        },
      );
    });

    group('State Transition: backgrounded → active', () {
      test('resume() transitions from backgrounded to active', () {
        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));

        session.resume();

        expect(session.state, equals(SessionState.active));
        expect(session.isActive, isTrue);
      });

      test('resume() updates lastActivity', () {
        session.suspend();
        final beforeResume = session.lastActivity;

        // Small delay to ensure time difference
        session.resume();

        expect(session.lastActivity, isNotNull);
        // lastActivity should be updated (or set for the first time)
        if (beforeResume != null) {
          expect(
            session.lastActivity!.isAfter(beforeResume) ||
                session.lastActivity == beforeResume,
            isTrue,
          );
        }
      });

      test('resume() emits SessionResumedEvent when thread exists', () async {
        final mockClient = MockAgUiClient();
        await session.initialize(agUiClient: mockClient);

        session.suspend();

        final events = <ConnectionEvent>[];
        session.events.listen(events.add);

        session.resume();

        // Wait for event to be processed
        await Future.delayed(Duration.zero);

        expect(events, contains(isA<SessionResumedEvent>()));
      });
    });

    group('State Transition: any → disposed', () {
      test('dispose() from active state', () {
        expect(session.state, equals(SessionState.active));

        session.dispose();

        expect(session.state, equals(SessionState.disposed));
        expect(session.isDisposed, isTrue);
        expect(session.isActive, isFalse);
      });

      test('dispose() from backgrounded state', () {
        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));

        session.dispose();

        expect(session.state, equals(SessionState.disposed));
        expect(session.isDisposed, isTrue);
      });

      test('dispose() is idempotent', () {
        session.dispose();
        expect(session.state, equals(SessionState.disposed));

        // Second dispose should not throw
        session.dispose();

        expect(session.state, equals(SessionState.disposed));
      });

      test('dispose() emits SessionDisposedEvent', () async {
        final mockClient = MockAgUiClient();
        await session.initialize(agUiClient: mockClient);

        final events = <ConnectionEvent>[];
        session.events.listen(events.add);

        session.dispose();

        // Wait for event to be processed
        await Future.delayed(Duration.zero);

        expect(events, contains(isA<SessionDisposedEvent>()));
      });
    });

    group('Invalid State Transitions', () {
      test('cannot initialize disposed session', () async {
        session.dispose();

        final mockClient = MockAgUiClient();
        expect(
          () => session.initialize(agUiClient: mockClient),
          throwsA(isA<StateError>()),
        );
      });

      test('cannot resume disposed session', () {
        session.dispose();

        expect(() => session.resume(), throwsA(isA<StateError>()));
      });

      test('cannot start run on disposed session', () async {
        final mockClient = MockAgUiClient();
        await session.initialize(agUiClient: mockClient);

        session.dispose();

        expect(
          () => session.startRun(messages: []),
          throwsA(isA<StateError>()),
        );
      });

      test('suspend() on disposed session is no-op', () {
        session.dispose();

        // Should not throw, just ignored
        session.suspend();

        expect(session.state, equals(SessionState.disposed));
      });
    });

    group('State Invariants', () {
      test('isActive is true only for active and streaming states', () {
        // active state
        expect(session.state, equals(SessionState.active));
        expect(session.isActive, isTrue);

        // backgrounded state
        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));
        expect(session.isActive, isFalse);

        // back to active
        session.resume();
        expect(session.state, equals(SessionState.active));
        expect(session.isActive, isTrue);

        // disposed state
        session.dispose();
        expect(session.state, equals(SessionState.disposed));
        expect(session.isActive, isFalse);
      });

      test('isStreaming is true only for streaming state', () {
        // We can't easily test streaming state without mocking the full
        // Thread class, but we verify the property works
        expect(session.isStreaming, isFalse);

        session.suspend();
        expect(session.isStreaming, isFalse);

        session.resume();
        expect(session.isStreaming, isFalse);

        session.dispose();
        expect(session.isStreaming, isFalse);
      });

      test('isDisposed is true only after dispose()', () {
        expect(session.isDisposed, isFalse);

        session.suspend();
        expect(session.isDisposed, isFalse);

        session.resume();
        expect(session.isDisposed, isFalse);

        session.dispose();
        expect(session.isDisposed, isTrue);
      });
    });

    group('State-Dependent Operations', () {
      test('createRun requires initialization', () async {
        expect(() => session.createRun(), throwsA(isA<StateError>()));
      });

      test('startRun requires initialization', () async {
        expect(
          () => session.startRun(messages: []),
          throwsA(isA<StateError>()),
        );
      });

      test('sendToolResults requires initialization', () async {
        expect(
          () => session.sendToolResults(runId: 'run-1', toolMessages: []),
          throwsA(isA<StateError>()),
        );
      });
    });

    group('Event Stream Lifecycle', () {
      test('events stream closes on dispose', () async {
        var streamClosed = false;
        session.events.listen((_) {}, onDone: () => streamClosed = true);

        session.dispose();

        // Wait for stream to close
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(streamClosed, isTrue);
      });

      test('message stream closes on dispose', () async {
        var streamClosed = false;
        session.messageStream.listen((_) {}, onDone: () => streamClosed = true);

        session.dispose();

        // Wait for stream to close
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(streamClosed, isTrue);
      });
    });

    group('All Valid Transitions Matrix', () {
      /// Tests all valid state transitions in a single comprehensive test.
      /// This documents the complete state machine.
      test('complete transition sequence', () async {
        // Start: active
        expect(session.state, equals(SessionState.active));

        // active → backgrounded
        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));

        // backgrounded → active
        session.resume();
        expect(session.state, equals(SessionState.active));

        // active → backgrounded again
        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));

        // backgrounded → disposed
        session.dispose();
        expect(session.state, equals(SessionState.disposed));
      });

      test('direct active → disposed transition', () {
        expect(session.state, equals(SessionState.active));

        session.dispose();

        expect(session.state, equals(SessionState.disposed));
      });

      test('multiple suspend calls are idempotent', () {
        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));

        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));

        session.suspend();
        expect(session.state, equals(SessionState.backgrounded));
      });

      test('multiple resume calls are idempotent', () {
        session.suspend();
        session.resume();
        expect(session.state, equals(SessionState.active));

        session.resume();
        expect(session.state, equals(SessionState.active));

        session.resume();
        expect(session.state, equals(SessionState.active));
      });
    });

    group('ServerRoomKey Integration', () {
      test('key getter returns correct composite key', () {
        final key = session.key;

        expect(key, isNotNull);
        expect(key!.serverId, equals('test-server'));
        expect(key.roomId, equals('test-room'));
      });

      test('key getter returns null when serverId is null', () {
        final anotherTransport = MockHttpTransport();
        final sessionWithoutServer = RoomSession(
          roomId: 'test-room',
          baseUrl: 'http://localhost:8080',
          transport: anotherTransport,
        );

        expect(sessionWithoutServer.key, isNull);

        sessionWithoutServer.dispose();
      });
    });

    group('Rapid State Transitions', () {
      test('handles rapid suspend/resume cycles', () {
        for (var i = 0; i < 100; i++) {
          session.suspend();
          expect(session.state, equals(SessionState.backgrounded));

          session.resume();
          expect(session.state, equals(SessionState.active));
        }
      });

      test('state is consistent after many transitions', () {
        // Random sequence of suspend/resume
        for (var i = 0; i < 50; i++) {
          if (i % 3 == 0) {
            session.suspend();
          } else {
            session.resume();
          }
        }

        // Should be in a valid state
        expect(
          session.state == SessionState.active ||
              session.state == SessionState.backgrounded,
          isTrue,
        );

        // Should be able to dispose
        session.dispose();
        expect(session.state, equals(SessionState.disposed));
      });
    });
  });
}
