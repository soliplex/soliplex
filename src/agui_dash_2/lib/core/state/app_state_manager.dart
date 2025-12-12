import 'package:flutter/foundation.dart';
import 'package:rxdart/rxdart.dart';

import '../models/server_models.dart';
import '../services/auth_manager.dart';
import '../services/server_registry.dart';
import 'app_state.dart';

/// Manager for application state.
///
/// Uses a BehaviorSubject stream instead of ChangeNotifier.
/// Explicit state transitions via methods.
/// Single source of truth for app state.
class AppStateManager {
  final ServerRegistry _serverRegistry;
  final AuthManager _authManager;

  final _stateSubject = BehaviorSubject<AppState>.seeded(const AppStateNoServer());

  AppStateManager({
    required ServerRegistry serverRegistry,
    required AuthManager authManager,
  })  : _serverRegistry = serverRegistry,
        _authManager = authManager;

  /// Stream of app state changes.
  Stream<AppState> get state => _stateSubject.stream;

  /// Current state value.
  AppState get currentState => _stateSubject.value;

  /// Initialize - check for saved server and auth state.
  Future<void> initialize() async {
    debugPrint('AppStateManager: Initializing...');

    try {
      await _serverRegistry.initialize();
      final server = _serverRegistry.currentServer;

      if (server == null) {
        debugPrint('AppStateManager: No saved server');
        _stateSubject.add(const AppStateNoServer());
        return;
      }

      debugPrint('AppStateManager: Found server ${server.url}, requiresAuth=${server.requiresAuth}');

      if (!server.requiresAuth) {
        debugPrint('AppStateManager: Server does not require auth, ready');
        _stateSubject.add(AppStateReady(server: server));
        return;
      }

      // Check for valid token
      final hasValidToken = await _authManager.hasValidToken(server.id);
      debugPrint('AppStateManager: hasValidToken=$hasValidToken');

      if (hasValidToken) {
        final userInfo = await _authManager.getUserInfo(server);
        debugPrint('AppStateManager: Got user info, ready');
        _stateSubject.add(AppStateReady(
          server: server,
          userName: userInfo?.name,
          userEmail: userInfo?.email,
        ));
      } else {
        // Need to probe server to get OIDC providers
        debugPrint('AppStateManager: No valid token, probing for providers');
        final serverInfo = await _serverRegistry.probeServer(server.url);
        _stateSubject.add(AppStateNeedsAuth(
          server: server,
          providers: serverInfo.oidcProviders,
        ));
      }
    } catch (e) {
      debugPrint('AppStateManager: Initialization error: $e');
      _stateSubject.add(AppStateError('Failed to initialize: $e'));
    }
  }

  /// Set server (from setup screen).
  /// Probes server and transitions to appropriate state.
  Future<void> setServer(ServerInfo serverInfo, {String? displayName}) async {
    debugPrint('AppStateManager: Setting server ${serverInfo.url}');

    try {
      final server = await _serverRegistry.saveServer(serverInfo, displayName: displayName);

      if (!server.requiresAuth) {
        debugPrint('AppStateManager: Server does not require auth, ready');
        _stateSubject.add(AppStateReady(server: server));
      } else {
        debugPrint('AppStateManager: Server requires auth');
        _stateSubject.add(AppStateNeedsAuth(
          server: server,
          providers: serverInfo.oidcProviders,
        ));
      }
    } catch (e) {
      debugPrint('AppStateManager: Error setting server: $e');
      _stateSubject.add(AppStateError('Failed to set server: $e'));
    }
  }

  /// Start OIDC login.
  Future<void> startLogin(OIDCAuthSystem provider) async {
    final current = currentState;
    if (current is! AppStateNeedsAuth) {
      debugPrint('AppStateManager: startLogin called in wrong state: $current');
      return;
    }

    debugPrint('AppStateManager: Starting login with provider ${provider.id}');
    _stateSubject.add(AppStateAuthenticating(
      server: current.server,
      provider: provider,
    ));

    try {
      final userInfo = await _authManager.login(provider, current.server);
      debugPrint('AppStateManager: Login successful');
      _stateSubject.add(AppStateReady(
        server: current.server,
        userName: userInfo?.name,
        userEmail: userInfo?.email,
      ));
    } catch (e) {
      debugPrint('AppStateManager: Login failed: $e');
      _stateSubject.add(AppStateError(
        'Authentication failed: $e',
        previousState: current,
      ));
    }
  }

  /// Logout.
  Future<void> logout() async {
    final current = currentState;
    if (current is! AppStateReady) {
      debugPrint('AppStateManager: logout called in wrong state: $current');
      return;
    }

    debugPrint('AppStateManager: Logging out');
    await _authManager.logout(current.server);

    // Re-probe server to get providers
    final serverInfo = await _serverRegistry.probeServer(current.server.url);
    _stateSubject.add(AppStateNeedsAuth(
      server: current.server,
      providers: serverInfo.oidcProviders,
    ));
  }

  /// Switch to a different server.
  Future<void> switchServer(ServerInfo serverInfo, {String? displayName}) async {
    final current = currentState;
    debugPrint('AppStateManager: Switching server to ${serverInfo.url}');

    // Clear auth for previous server if we have one
    if (current.server != null) {
      await _authManager.clearTokens(current.server!.id);
    }

    await setServer(serverInfo, displayName: displayName);
  }

  /// Retry from error state.
  void retryFromError() {
    final current = currentState;
    if (current is AppStateError && current.previousState != null) {
      debugPrint('AppStateManager: Retrying from error');
      _stateSubject.add(current.previousState!);
    }
  }

  /// Clear server and go to setup.
  Future<void> clearServer() async {
    final current = currentState;
    if (current.server != null) {
      await _serverRegistry.removeServer(current.server!.id);
    }
    _stateSubject.add(const AppStateNoServer());
  }

  void dispose() {
    _stateSubject.close();
  }
}
