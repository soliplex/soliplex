import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/auth/auth_providers.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/services/auth_manager.dart';
import 'package:soliplex/core/services/secure_storage_service.dart'
    show secureStorageProvider;
import 'package:soliplex/core/services/server_registry.dart';
import 'package:soliplex/core/state/app_state.dart';
import 'package:soliplex/core/state/app_state_manager.dart';
import 'package:soliplex/core/utils/debug_log.dart';

// Re-export for convenience
export '../state/app_state.dart';

/// Provider for ServerRegistry.
/// Singleton - persists for app lifetime.
/// Injects NetworkInspector for traffic observability.
final serverRegistryProvider = Provider<ServerRegistry>((ref) {
  final storage = ref.read(secureStorageProvider);
  final inspector = ref.read(networkInspectorProvider);
  final registry = ServerRegistry(storage: storage, inspector: inspector);
  ref.onDispose(registry.dispose);
  return registry;
});

/// Provider for AuthManager.
/// Singleton - persists for app lifetime.
/// Injects NetworkInspector for traffic observability.
final authManagerProvider = Provider<AuthManager>((ref) {
  final storage = ref.read(secureStorageProvider);
  final oidcInteractor = ref.read(oidcAuthInteractorProvider);
  final tokenStorage = ref.read(secureTokenStorageProvider);
  final inspector = ref.read(networkInspectorProvider);
  final manager = AuthManager(
    storage: storage,
    oidcInteractor: oidcInteractor,
    tokenStorage: tokenStorage,
    inspector: inspector,
  );
  ref.onDispose(manager.dispose);
  return manager;
});

/// Provider for AppStateManager.
/// Singleton - persists for app lifetime.
/// This is the main entry point for app state management.
final appStateManagerProvider = Provider<AppStateManager>((ref) {
  final serverRegistry = ref.read(serverRegistryProvider);
  final authManager = ref.read(authManagerProvider);
  final manager = AppStateManager(
    serverRegistry: serverRegistry,
    authManager: authManager,
  );
  ref.onDispose(manager.dispose);
  return manager;
});

/// Stream provider for app state.
/// UI subscribes to this for reactive updates.
final appStateStreamProvider = StreamProvider<AppState>((ref) {
  final manager = ref.watch(appStateManagerProvider);
  return manager.state;
});

/// Current app state (sync access).
/// Use appStateStreamProvider for reactive updates.
final currentAppStateProvider = Provider<AppState>((ref) {
  final manager = ref.watch(appStateManagerProvider);
  return manager.currentState;
});

/// Current server from app state.
/// Convenience accessor.
final currentServerFromAppStateProvider = Provider<ServerConnection?>((ref) {
  final stateAsync = ref.watch(appStateStreamProvider);
  final server = stateAsync.whenOrNull(data: (state) => state.server);
  DebugLog.service(
    // ignore: lines_longer_than_80_chars (auto-documented)
    'currentServerFromAppStateProvider: server=${server?.url}, id=${server?.id}',
  );
  return server;
});

/// Whether the app is ready (authenticated or no auth required).
final isAppReadyProvider = Provider<bool>((ref) {
  final stateAsync = ref.watch(appStateStreamProvider);
  return stateAsync.whenOrNull(data: (state) => state.isReady) ?? false;
});

/// Whether authentication is needed.
final needsAuthFromAppStateProvider = Provider<bool>((ref) {
  final stateAsync = ref.watch(appStateStreamProvider);
  return stateAsync.whenOrNull(data: (state) => state.needsAuth) ?? false;
});

/// Server history list.
/// Rebuilds when app state changes (which happens after server operations).
final serverHistoryProvider = Provider<List<ServerConnection>>((ref) {
  // Watch the app state stream to trigger rebuilds when servers change
  ref.watch(appStateStreamProvider);
  final manager = ref.read(appStateManagerProvider);
  return manager.serverHistory;
});
