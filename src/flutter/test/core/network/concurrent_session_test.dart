import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/room_session.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/providers/panel_providers.dart';

class MockNetworkInspector extends Mock implements NetworkInspector {}

void main() {
  group('Concurrent Session Hardening Integration Test', () {
    late ProviderContainer container;
    late MockNetworkInspector mockInspector;

    setUp(() {
      mockInspector = MockNetworkInspector();
      container = ProviderContainer(
        overrides: [
          networkInspectorProvider.overrideWith((ref) => mockInspector),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    test('Background session updates context pane provider', () async {
      final registry = container.read(connectionRegistryProvider);
      const serverId = 'test-server';
      const roomId = 'room-1';
      const key = ServerRoomKey(serverId: serverId, roomId: roomId);

      final session =
          registry.getSession(key, baseUrl: 'http://test-server.com')
              as RoomSession;

      // Trigger GenUI update via RoomSession
      session.addGenUiMessage(
        const GenUiContent(
          toolCallId: 't1',
          widgetName: 'TestWidget',
        ),
      );

      // Verify ContextPane provider updated
      final contextState = container.read(roomContextPaneProvider(key));

      final item = contextState.items.first; // items are prepended
      expect(item.title, equals('GenUI Render'));
      expect(item.summary, equals('TestWidget'));
    });

    test('Background session updates canvas provider', () async {
      final registry = container.read(connectionRegistryProvider);
      const serverId = 'test-server';
      const roomId = 'room-2';
      const key = ServerRoomKey(serverId: serverId, roomId: roomId);

      final session =
          registry.getSession(key, baseUrl: 'http://test-server.com')
              as RoomSession;

      // Trigger Canvas update via RoomSession dispatch
      session.dispatchCanvasUpdate('append', 'CanvasWidget', {'foo': 'bar'});

      // Verify Canvas provider updated
      final canvasState = container.read(roomCanvasProvider(key));

      final item = canvasState.items.last;
      expect(item.widgetName, equals('CanvasWidget'));
      expect(item.data, equals({'foo': 'bar'}));
    });

    test('Registry injects handler into existing session', () async {
      final registry = container.read(connectionRegistryProvider);
      const serverId = 'test-server';
      const roomId = 'room-3';
      const key = ServerRoomKey(serverId: serverId, roomId: roomId);

      final session1 = registry.getSession(
        key,
        baseUrl: 'http://test-server.com',
      );

      // Get session again
      final session2 = registry.getSession(key) as RoomSession;

      expect(session1, equals(session2));

      // Trigger update
      session2.dispatchCanvasUpdate('append', 'Widget3', {});

      final canvasState = container.read(roomCanvasProvider(key));
      expect(canvasState.items, isNotEmpty);
    });
  });
}
