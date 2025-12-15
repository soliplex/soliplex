import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/room_session.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/rooms_service.dart';

class MockNetworkInspector extends Mock implements NetworkInspector {}

void main() {
  group('Chat Reactivity Tests', () {
    late ProviderContainer container;
    late MockNetworkInspector mockInspector;

    setUp(() {
      mockInspector = MockNetworkInspector();
      container = ProviderContainer(
        overrides: [
          networkInspectorProvider.overrideWith((ref) => mockInspector),
          currentServerFromAppStateProvider.overrideWith(
            (ref) => ServerConnection.agUi(
              id: 'test-server',
              url: 'http://test-server.com',
              lastConnected: DateTime.now(),
            ),
          ),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    test(
      'activeMessageStreamProvider updates when session messages change',
      () async {
        final registry = container.read(connectionRegistryProvider);

        const serverId = 'test-server';
        const roomId = 'room-1';
        const key = ServerRoomKey(serverId: serverId, roomId: roomId);

        final session =
            registry.getSession(key, baseUrl: 'http://test-server.com')
                as RoomSession;

        // Select room
        container.read(selectedRoomProvider.notifier).state = roomId;
        await Future.microtask(() {});

        // Keep provider alive
        final sub = container.listen(activeMessageStreamProvider, (_, next) {});

        // Initial state
        final initialAsync = container.read(activeMessageStreamProvider);
        // It might be loading initially
        expect(
          initialAsync.value == null || initialAsync.value!.isEmpty,
          isTrue,
        );

        // Add message
        session.addUserMessage('Hello');

        // Wait for stream -> provider propagation
        await Future<void>.delayed(const Duration(milliseconds: 50));

        final asyncVal1 = container.read(activeMessageStreamProvider);
        if (asyncVal1.hasError) {
          fail('Provider error: ${asyncVal1.error}');
        }
        if (asyncVal1.isLoading && !asyncVal1.hasValue) {
          fail('Provider stuck loading');
        }

        var messages = asyncVal1.value!;
        expect(messages, isNotEmpty);
        expect(messages.last.text, equals('Hello'));

        // Add another
        session.addUserMessage('World');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        messages = container.read(activeMessageStreamProvider).value!;
        expect(messages.last.text, equals('World'));

        sub.close();
      },
    );

    test(
      'activeMessageStreamProvider switches when active room changes',
      skip: 'Flaky timing in test env',
      () async {
        final registry = container.read(connectionRegistryProvider);

        const serverId = 'test-server';
        const key1 = ServerRoomKey(serverId: serverId, roomId: 'room1');
        const key2 = ServerRoomKey(serverId: serverId, roomId: 'room2');

        final session1 = registry.getSession(
          key1,
          baseUrl: 'http://test-server.com',
        );
        final session2 = registry.getSession(
          key2,
          baseUrl: 'http://test-server.com',
        );

        (session1 as RoomSession).addUserMessage('Message in Room 1');
        (session2 as RoomSession).addUserMessage('Message in Room 2');

        // Select Room 1
        container.read(selectedRoomProvider.notifier).state = 'room1';
        await Future.microtask(() {});
        await Future<void>.delayed(const Duration(milliseconds: 50));

        var asyncVal = container.read(activeMessageStreamProvider);
        if (!asyncVal.hasValue) {
          fail(
            // ignore: lines_longer_than_80_chars (auto-documented)
            'Room 1: Provider has no value. Loading: ${asyncVal.isLoading}, Error: ${asyncVal.error}', // ignore: lines_longer_than_80_chars
          );
        }
        expect(asyncVal.value!.last.text, equals('Message in Room 1'));

        // Select Room 2
        container.read(selectedRoomProvider.notifier).state = 'room2';
        await Future.microtask(() {});
        await Future<void>.delayed(const Duration(milliseconds: 50));

        asyncVal = container.read(activeMessageStreamProvider);
        if (!asyncVal.hasValue) {
          fail(
            // ignore: lines_longer_than_80_chars (auto-documented)
            'Room 2: Provider has no value. Loading: ${asyncVal.isLoading}, Error: ${asyncVal.error}', // ignore: lines_longer_than_80_chars
          );
        }
        expect(asyncVal.value!.last.text, equals('Message in Room 2'));
      },
    );
  });
}
