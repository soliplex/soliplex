import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/controllers/session_lifecycle_controller.dart';
import 'package:soliplex/core/models/document_model.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/protocol/chat_session.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/auth_manager.dart';
import 'package:soliplex/core/services/rooms_service.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/services/server_registry.dart';
import 'package:soliplex/core/utils/url_builder.dart';
import 'package:soliplex/features/chat/chat_screen.dart';
import 'package:soliplex/features/server/server_setup_screen.dart';
import 'package:soliplex/main.dart';

// Mocks
class MockNetworkInspector extends Mock implements NetworkInspector {}

class MockSecureStorage extends Mock implements SecureStorageService {
  final Map<String, String> _storage = {};

  @override
  Future<void> write(String key, String value) async {
    _storage[key] = value;
  }

  @override
  Future<String?> read(String key) async {
    return _storage[key];
  }

  @override
  Future<void> delete(String key) async {
    _storage.remove(key);
  }

  @override
  Future<void> deleteAll() async {
    _storage.clear();
  }

  @override
  Future<bool> containsKey(String key) async {
    return _storage.containsKey(key);
  }

  @override
  Future<Map<String, String>> readAll() async {
    return Map.from(_storage);
  }
}

class MockRoomsNotifier extends StateNotifier<RoomsState>
    implements RoomsNotifier {
  MockRoomsNotifier() : super(const RoomsState());

  @override
  Future<List<Document>> fetchDocuments(String roomId) async {
    return Future.value([]); // Return empty list for mock
  }

  @override
  Future<void> fetchRooms() async {}

  @override
  UrlBuilder get urlBuilder => throw UnimplementedError();

  @override
  Future<void> refresh() => fetchRooms();

  @override
  void setTransportLayer(
    NetworkTransportLayer? transportLayer,
    String serverUrl,
  ) {}
}

class MockAuthManager extends Mock implements AuthManager {
  @override
  Future<Map<String, String>> getAuthHeaders(String serverId) async => {};
  @override
  Future<bool> hasValidToken(String serverId) async => true;
  @override
  // ignore: lines_longer_than_80_chars (auto-documented)
  Future<UserInfo?> getUserInfo(ServerConnection server) async => null; // Mock getUserInfo // ignore: lines_longer_than_80_chars
}

class MockConnectionManager extends Mock implements ConnectionManager {
  @override
  bool get isConfigured => true;
  @override
  void switchServer(
    String newBaseUrl, {
    Map<String, String>? headers,
    String? serverId,
    EndpointConfiguration? config,
  }) {}
  @override
  ChatSession getSession(String roomId) => throw UnimplementedError();
}

class MockSessionLifecycleController extends AsyncNotifier<void>
    implements SessionLifecycleController {
  @override
  Future<void> build() async {}
}

class FakeServerRegistry extends Fake implements ServerRegistry {
  ServerConnection? _currentServer;
  final _serverHistory = <ServerConnection>[];

  @override
  ServerConnection? get currentServer => _currentServer;
  @override
  List<ServerConnection> get serverHistory => _serverHistory;

  @override
  Future<void> initialize() async {
    // Start empty to test setup flow
    _currentServer = null;
  }

  @override
  Future<ServerInfo> probeServer(String url) async {
    return ServerInfo(url: url, isReachable: true);
  }

  @override
  Future<ServerConnection> saveServer(
    ServerInfo serverInfo, {
    String? displayName,
    EndpointConfiguration? config,
  }) async {
    final connection = ServerConnection(
      id: 'test-server-id',
      lastConnected: DateTime.now(),
      config:
          config ??
          AgUiEndpoint(
            url: serverInfo.url,
            label: displayName ?? 'Test Server',
            requiresAuth: serverInfo.requiresAuth,
          ),
    );
    _currentServer = connection;
    _serverHistory.add(connection);
    return connection;
  }

  @override
  Future<ServerConnection> setCurrentServer(String serverId) async {
    final server = _serverHistory.firstWhere((s) => s.id == serverId);
    _currentServer = server;
    return server;
  }
}

class FakeServerInfo extends Fake implements ServerInfo {}

void main() {
  group('Login Flow Integration Test', () {
    late MockSecureStorage mockStorage;
    late MockNetworkInspector mockInspector;
    late MockRoomsNotifier mockRoomsNotifier;
    late FakeServerRegistry fakeServerRegistry;
    late MockAuthManager mockAuthManager;
    late MockConnectionManager mockConnectionManager;

    setUpAll(() {
      registerFallbackValue(FakeServerInfo());
    });

    setUp(() {
      mockStorage = MockSecureStorage();
      mockInspector = MockNetworkInspector();
      mockRoomsNotifier = MockRoomsNotifier();
      fakeServerRegistry = FakeServerRegistry();
      mockAuthManager = MockAuthManager();
      mockConnectionManager = MockConnectionManager();
    });

    // TODO: This test needs AppStateManager mocked to properly emit state
    // transitions.
    // The ServerRegistry mock works but AppStateManager is real and doesn't
    // transition
    // to AppStateReady without proper OIDC/auth flow mocking.
    testWidgets('User can enter server URL and connect', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureStorageProvider.overrideWith((ref) => mockStorage),
            networkInspectorProvider.overrideWith((ref) => mockInspector),
            serverRegistryProvider.overrideWith((ref) => fakeServerRegistry),
            roomsProvider.overrideWith((ref) => mockRoomsNotifier),
            authManagerProvider.overrideWith((ref) => mockAuthManager),
            connectionManagerProvider.overrideWith(
              (ref) => mockConnectionManager,
            ),
            sessionLifecycleProvider.overrideWith(
              MockSessionLifecycleController.new,
            ), // Use mock
            activeMessageStreamProvider.overrideWith(
              (ref) => const AsyncData([]),
            ),
          ],
          child: const AgUiDashApp(),
        ),
      );

      // Initial pump
      await tester.pump();
      await tester.pumpAndSettle();

      // Should be on ServerSetupScreen
      expect(find.byType(ServerSetupScreen), findsOneWidget);

      // Enter URL
      await tester.enterText(
        find.byType(TextFormField),
        'http://localhost:8080',
      );
      await tester.pump();

      // Tap Connect
      await tester.tap(find.text('Connect'));

      // Pump to trigger processing
      await tester.pump();

      // Wait for async operations (probing, saving, state transition)
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 1));

      if (find.byType(ServerSetupScreen).evaluate().isNotEmpty) {
        debugPrint('TEST FAIL: Still on ServerSetupScreen');
      } else {
        debugPrint('TEST INFO: Navigated away from ServerSetupScreen');
      }

      if (find.byType(ChatScreen).evaluate().isNotEmpty) {
        debugPrint('TEST INFO: Found ChatScreen');
      } else {
        debugPrint('TEST FAIL: ChatScreen NOT found');
      }

      // Should be on ChatScreen
      expect(find.byType(ChatScreen), findsOneWidget);
      expect(find.byType(ServerSetupScreen), findsNothing);
    });
  });
}
