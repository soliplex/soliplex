import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/network/connection_events.dart';
import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/network/http_transport.dart';
import 'package:soliplex/core/network/room_session.dart';

// Mock for HttpTransport
class MockHttpTransport extends Mock implements HttpTransport {}

// Fake classes for mocktail
class FakeUri extends Fake implements Uri {}

/// Phase 3 tests for ConnectionManager facade.
///
/// Tests verify that:
/// - ConnectionManager delegates to ConnectionRegistry
/// - switchServer() is non-destructive
/// - focusServer() works correctly
/// - Backward compatibility is maintained
void main() {
  late ConnectionRegistry registry;
  late ConnectionManager manager;

  setUpAll(() {
    registerFallbackValue(FakeUri());
  });

  setUp(() {
    registry = ConnectionRegistry();
    manager = ConnectionManager(registry: registry);
  });

  tearDown(() {
    manager.dispose();
    registry.dispose();
  });

  group('ConnectionManager Facade Tests', () {
    group('Basic Configuration', () {
      test('starts unconfigured with no servers', () {
        expect(manager.isConfigured, isFalse);
        expect(manager.activeServerId, isNull);
        expect(manager.activeRoomId, isNull);
        expect(manager.serverUrl, isEmpty);
      });

      test('isConfigured returns true after switchServer', () {
        manager.switchServer('http://localhost:8080');

        expect(manager.isConfigured, isTrue);
        expect(manager.activeServerId, isNotNull);
        expect(manager.serverUrl, equals('http://localhost:8080'));
      });

      test('can be created with initial baseUrl', () {
        final initialManager = ConnectionManager(
          registry: registry,
          baseUrl: 'http://initial:9000',
        );

        expect(initialManager.isConfigured, isTrue);
        expect(initialManager.serverUrl, equals('http://initial:9000'));

        initialManager.dispose();
      });
    });

    group('switchServer() Non-Destructive Behavior', () {
      test('switchServer connects to registry', () {
        manager.switchServer('http://server1:8080');

        expect(registry.hasServer('server1:8080'), isTrue);
        expect(manager.activeServerId, equals('server1:8080'));
      });

      test('switching to second server preserves first', () {
        manager.switchServer('http://server1:8080');
        manager.switchServer('http://server2:9000');

        // Both servers should exist
        expect(registry.hasServer('server1:8080'), isTrue);
        expect(registry.hasServer('server2:9000'), isTrue);

        // Active should be second
        expect(manager.activeServerId, equals('server2:9000'));
      });

      test('switching back to first server reuses connection', () {
        manager.switchServer('http://server1:8080');
        manager.switchServer('http://server2:9000');

        final serverCountBefore = registry.serverCount;

        manager.switchServer('http://server1:8080');

        // Should not create new server
        expect(registry.serverCount, equals(serverCountBefore));
        expect(manager.activeServerId, equals('server1:8080'));
      });

      test('switching to same server is no-op', () {
        manager.switchServer('http://server1:8080');

        var notifyCount = 0;
        manager.addListener(() => notifyCount++);

        manager.switchServer('http://server1:8080');

        // Should not notify (no change)
        expect(notifyCount, equals(0));
      });
    });

    group('focusServer() Method', () {
      test('focusServer switches active server', () {
        manager.switchServer('http://server1:8080');
        manager.switchServer('http://server2:9000');

        manager.focusServer('server1:8080');

        expect(manager.activeServerId, equals('server1:8080'));
      });

      test('focusServer throws if server not connected', () {
        expect(
          () => manager.focusServer('nonexistent:1234'),
          throwsA(isA<StateError>()),
        );
      });

      test('focusServer is no-op if already focused', () {
        manager.switchServer('http://server1:8080');

        var notifyCount = 0;
        manager.addListener(() => notifyCount++);

        manager.focusServer('server1:8080');

        // Should not notify (no change)
        expect(notifyCount, equals(0));
      });
    });

    group('Multi-Server Support', () {
      test('connectedServerIds returns all servers', () {
        manager.switchServer('http://server1:8080');
        manager.switchServer('http://server2:9000');
        manager.switchServer('http://server3:7000');

        expect(manager.connectedServerIds, hasLength(3));
        expect(manager.connectedServerIds, contains('server1:8080'));
        expect(manager.connectedServerIds, contains('server2:9000'));
        expect(manager.connectedServerIds, contains('server3:7000'));
      });

      test('hasServer returns correct values', () {
        manager.switchServer('http://server1:8080');

        expect(manager.hasServer('server1:8080'), isTrue);
        expect(manager.hasServer('nonexistent:1234'), isFalse);
      });

      test('removeServer removes server from registry', () {
        manager.switchServer('http://server1:8080');
        manager.switchServer('http://server2:9000');

        manager.removeServer('server1:8080');

        expect(manager.hasServer('server1:8080'), isFalse);
        expect(manager.hasServer('server2:9000'), isTrue);
      });

      test('removeServer clears activeServerId if removed', () {
        manager.switchServer('http://server1:8080');

        manager.removeServer('server1:8080');

        expect(manager.activeServerId, isNull);
        expect(manager.isConfigured, isFalse);
      });
    });

    group('Backward Compatibility', () {
      test('getSession throws if no server configured', () {
        expect(() => manager.getSession('room1'), throwsA(isA<StateError>()));
      });

      test('getSession creates session on current server', () {
        manager.switchServer('http://localhost:8080');

        final session = manager.getSession('room1') as RoomSession;

        expect(session.roomId, equals('room1'));
        expect(session.serverId, equals('localhost:8080'));
      });

      test('switchRoom throws if no server configured', () {
        expect(() => manager.switchRoom('room1'), throwsA(isA<StateError>()));
      });

      test('switchRoom updates registry active key', () async {
        manager.switchServer('http://localhost:8080');

        await manager.switchRoom('room1');

        expect(registry.activeRoomId, equals('room1'));
        expect(manager.activeRoomId, equals('room1'));
      });

      test('activeSession returns session for active room', () async {
        manager.switchServer('http://localhost:8080');
        await manager.switchRoom('room1');

        final session = manager.activeSession as RoomSession?;

        expect(session, isNotNull);
        expect(session!.roomId, equals('room1'));
      });

      test('activeSession returns null when no room active', () {
        manager.switchServer('http://localhost:8080');

        expect(manager.activeSession, isNull);
      });

      test('activeConnections returns sessions for current server', () {
        manager.switchServer('http://localhost:8080');
        manager.getSession('room1');
        manager.getSession('room2');

        expect(manager.activeConnections, hasLength(2));
      });

      test('initializeSession throws if no server', () {
        expect(
          () => manager.initializeSession('room1'),
          throwsA(isA<StateError>()),
        );
      });
    });

    group('Event Forwarding', () {
      test('events from session are forwarded', () async {
        manager.switchServer('http://localhost:8080');
        final session = manager.getSession('room1');

        final events = <ConnectionEvent>[];
        manager.events.listen(events.add);

        session.suspend();
        await Future.delayed(Duration.zero);

        // No events yet because thread is null
        // Events are only emitted when thread exists
        expect(events, isEmpty);
      });

      test('switchRoom emits RoomSwitchedEvent', () async {
        manager.switchServer('http://localhost:8080');

        final events = <ConnectionEvent>[];
        manager.events.listen(events.add);

        await manager.switchRoom('room1');
        await Future.delayed(Duration.zero);

        expect(events.whereType<RoomSwitchedEvent>(), hasLength(1));
      });
    });

    group('Session Operations', () {
      test('isAgentTyping returns false when no server', () {
        expect(manager.isAgentTyping('room1'), isFalse);
      });

      test('isAgentTyping returns false when no session', () {
        manager.switchServer('http://localhost:8080');
        expect(manager.isAgentTyping('nonexistent'), isFalse);
      });

      test('clearMessages does nothing when no server', () {
        // Should not throw
        manager.clearMessages('room1');
      });

      test('cancelRun does nothing when no server', () async {
        // Should not throw
        await manager.cancelRun('room1');
      });

      test('disposeSession removes session from server', () {
        manager.switchServer('http://localhost:8080');
        manager.getSession('room1');

        expect(manager.activeConnections, hasLength(1));

        manager.disposeSession('room1');

        expect(manager.activeConnections, isEmpty);
      });
    });

    group('Server ID Generation', () {
      test('generates server ID from URL host and port', () {
        manager.switchServer('http://localhost:8080');
        expect(manager.activeServerId, equals('localhost:8080'));

        manager.switchServer('https://api.example.com:443');
        expect(manager.activeServerId, equals('api.example.com:443'));
      });

      test('handles URLs with default ports', () {
        manager.switchServer('http://example.com');
        expect(manager.activeServerId, equals('example.com:80'));
      });
    });

    group('Dispose', () {
      test('dispose cleans up resources', () {
        // Use separate instances for dispose tests
        final testRegistry = ConnectionRegistry();
        final testManager = ConnectionManager(registry: testRegistry);

        testManager.switchServer('http://localhost:8080');
        testManager.getSession('room1');

        testManager.dispose();

        // ChangeNotifier doesn't allow double-dispose, so we just verify it
        // completed
        testRegistry.dispose();
      });

      test('dispose does not dispose shared registry', () {
        // Use separate instances for dispose tests
        final testRegistry = ConnectionRegistry();
        final testManager = ConnectionManager(registry: testRegistry);

        testManager.switchServer('http://localhost:8080');
        testManager.dispose();

        // Registry should still work
        expect(testRegistry.isDisposed, isFalse);
        expect(testRegistry.hasServer('localhost:8080'), isTrue);

        testRegistry.dispose();
      });
    });
  });
}
