import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_providers.dart';
import '../models/server_models.dart';
import '../services/auth_manager.dart';
import '../services/server_config_service.dart' show secureStorageProvider;
import '../services/server_registry.dart';
import '../state/app_state.dart';
import '../state/app_state_manager.dart';

// Re-export for convenience
export '../state/app_state.dart';

/// Provider for ServerRegistry.
/// Singleton - persists for app lifetime.
final serverRegistryProvider = Provider<ServerRegistry>((ref) {
  final storage = ref.read(secureStorageProvider);
  final registry = ServerRegistry(storage: storage);
  ref.onDispose(() => registry.dispose());
  return registry;
});

/// Provider for AuthManager.
/// Singleton - persists for app lifetime.
final authManagerProvider = Provider<AuthManager>((ref) {
  final storage = ref.read(secureStorageProvider);
  final oidcInteractor = ref.read(oidcAuthInteractorProvider);
  final tokenStorage = ref.read(secureTokenStorageProvider);
  final manager = AuthManager(
    storage: storage,
    oidcInteractor: oidcInteractor,
    tokenStorage: tokenStorage,
  );
  ref.onDispose(() => manager.dispose());
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
  ref.onDispose(() => manager.dispose());
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
  debugPrint('currentServerFromAppStateProvider: server=${server?.url}, id=${server?.id}');
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
