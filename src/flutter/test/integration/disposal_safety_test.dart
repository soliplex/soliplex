import 'dart:async' as dart_async;

import 'package:flutter/material.dart'; // Added for GlobalKey, NavigatorState
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart'; // Added for GoRouter, ShellRoute, GoRoute
import 'package:mocktail/mocktail.dart';
import 'package:rxdart/rxdart.dart';
import 'package:soliplex/core/models/document_model.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/providers/app_providers.dart' as app_providers;
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/router/app_router.dart'; // Added for routerProvider
import 'package:soliplex/core/services/rooms_service.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/state/app_state.dart' as app_state;
import 'package:soliplex/core/state/app_state_manager.dart'
    as app_state_manager;
import 'package:soliplex/core/utils/url_builder.dart';
import 'package:soliplex/features/chat/chat_screen.dart';
import 'package:soliplex/features/navigation/app_scaffold.dart'; // Added for AppScaffold
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

class MockAppStateManager extends Mock
    implements app_state_manager.AppStateManager {
  final _stateSubject = BehaviorSubject<app_state.AppState>.seeded(
    const app_state.AppStateNoServer(),
  );

  @override
  dart_async.Stream<app_state.AppState> get state => _stateSubject.stream;

  @override
  app_state.AppState get currentState => _stateSubject.value;

  @override
  List<ServerConnection> get serverHistory => const [];

  @override
  Future<void> initialize() async {}

  @override
  void dispose() {}

  @override
  Future<void> retryFromError() async {}

  @override
  Future<void> setServer(
    ServerInfo serverInfo, {
    String? displayName,
    EndpointConfiguration? config,
  }) async {
    _stateSubject.add(
      app_state.AppStateReady(
        server: ServerConnection.agUi(
          id: 'test-server',
          url: 'http://localhost:8080',
          lastConnected: DateTime.now(),
        ),
      ),
    );
  }

  @override
  Future<void> startLogin(OIDCAuthSystem provider) async {}

  @override
  Future<void> logout() async {}

  @override
  Future<void> switchServer(
    ServerInfo serverInfo, {
    String? displayName,
  }) async {}

  @override
  Future<void> clearServer() async {}

  @override
  Future<void> removeServerFromHistory(String serverId) async {}

  @override
  Future<void> selectServerFromHistory(String serverId) async {}
}

void main() {
  testWidgets('App launches and renders ChatScreen without dispose errors', (
    tester,
  ) async {
    final mockInspector = MockNetworkInspector();
    final mockAppStateManager = MockAppStateManager();
    final mockStorage = MockSecureStorage();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          secureStorageProvider.overrideWith((ref) => mockStorage),
          networkInspectorProvider.overrideWith((ref) => mockInspector),
          app_providers.appStateManagerProvider.overrideWith(
            (ref) => mockAppStateManager,
          ),
          activeMessageStreamProvider.overrideWith(
            (ref) => const AsyncData([]),
          ),
          routerProvider.overrideWith(
            (ref) => GoRouter(
              navigatorKey: GlobalKey<NavigatorState>(
                debugLabel: 'test_router',
              ),
              initialLocation: '/chat',
              routes: [
                ShellRoute(
                  navigatorKey: GlobalKey<NavigatorState>(
                    debugLabel: 'test_shell_router',
                  ),
                  builder: (context, state, child) => AppScaffold(child: child),
                  routes: [
                    GoRoute(
                      path: '/chat',
                      builder: (context, state) => const ChatScreen(),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
        child: const AgUiDashApp(),
      ),
    );

    // Initial pump to render loading indicators or initial state
    await tester.pump();
    await Future.microtask(() {});
    await tester.pumpAndSettle();

    // Verify that ChatScreen is rendered
    expect(find.byType(ChatScreen), findsOneWidget);
  });
}
