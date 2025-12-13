import 'package:rxdart/rxdart.dart';

import '../models/server_models.dart';
import '../services/auth_manager.dart';
import '../services/server_registry.dart';
import '../utils/debug_log.dart';
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
    DebugLog.service('AppStateManager: Initializing...');

    try {
      await _serverRegistry.initialize();
      final server = _serverRegistry.currentServer;

      if (server == null) {
        DebugLog.service('AppStateManager: No saved server');
        _stateSubject.add(const AppStateNoServer());
        return;
      }

      DebugLog.service('AppStateManager: Found server ${server.url}, requiresAuth=${server.requiresAuth}');

      if (!server.requiresAuth) {
        DebugLog.service('AppStateManager: Server does not require auth, ready');
        _stateSubject.add(AppStateReady(server: server));
        return;
      }

      // Check for valid token
      final hasValidToken = await _authManager.hasValidToken(server.id);
      DebugLog.service('AppStateManager: hasValidToken=$hasValidToken');

      if (hasValidToken) {
        final userInfo = await _authManager.getUserInfo(server);
        DebugLog.service('AppStateManager: Got user info, ready');
        _stateSubject.add(AppStateReady(
          server: server,
          userName: userInfo?.name,
          userEmail: userInfo?.email,
        ));
      } else {
        // Need to probe server to get OIDC providers
        DebugLog.service('AppStateManager: No valid token, probing for providers');
        final serverInfo = await _serverRegistry.probeServer(server.url);
        _stateSubject.add(AppStateNeedsAuth(
          server: server,
          providers: serverInfo.oidcProviders,
        ));
      }
    } catch (e) {
      DebugLog.error('AppStateManager: Initialization error: $e');
      _stateSubject.add(AppStateError('Failed to initialize: $e'));
    }
  }

  /// Set server (from setup screen).
  /// Probes server and transitions to appropriate state.
  Future<void> setServer(ServerInfo serverInfo, {String? displayName}) async {
    DebugLog.service('AppStateManager: Setting server ${serverInfo.url}');

    try {
      final server = await _serverRegistry.saveServer(serverInfo, displayName: displayName);
      DebugLog.service('AppStateManager: Saved server ${server.url} with id=${server.id}');

      if (!server.requiresAuth) {
        DebugLog.service('AppStateManager: Server does not require auth, ready');
        _stateSubject.add(AppStateReady(server: server));
      } else {
        DebugLog.service('AppStateManager: Server requires auth');
        _stateSubject.add(AppStateNeedsAuth(
          server: server,
          providers: serverInfo.oidcProviders,
        ));
      }
    } catch (e) {
      DebugLog.error('AppStateManager: Error setting server: $e');
      _stateSubject.add(AppStateError('Failed to set server: $e'));
    }
  }

  /// Start OIDC login.
  Future<void> startLogin(OIDCAuthSystem provider) async {
    final current = currentState;
    if (current is! AppStateNeedsAuth) {
      DebugLog.warn('AppStateManager: startLogin called in wrong state: $current');
      return;
    }

    DebugLog.service('AppStateManager: Starting login with provider ${provider.id}');
    _stateSubject.add(AppStateAuthenticating(
      server: current.server,
      provider: provider,
    ));

    try {
      final userInfo = await _authManager.login(provider, current.server);
      DebugLog.service('AppStateManager: Login successful');
      _stateSubject.add(AppStateReady(
        server: current.server,
        userName: userInfo?.name,
        userEmail: userInfo?.email,
      ));
    } catch (e) {
      DebugLog.error('AppStateManager: Login failed: $e');
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
      DebugLog.warn('AppStateManager: logout called in wrong state: $current');
      return;
    }

    DebugLog.service('AppStateManager: Logging out');
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
    DebugLog.service('AppStateManager: Switching server to ${serverInfo.url}');

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
      DebugLog.service('AppStateManager: Retrying from error');
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

  // ===========================================================================
  // Server History Operations (for ServerHistoryWidget)
  // ===========================================================================

  /// Get the server history list.
  /// For reactive updates, use serverHistoryProvider.
  List<ServerConnection> get serverHistory => _serverRegistry.serverHistory;

  /// Remove a server from history.
  /// Emits state update after removal.
  Future<void> removeServerFromHistory(String serverId) async {
    DebugLog.service('AppStateManager: Removing server $serverId from history');
    await _serverRegistry.removeServer(serverId);

    // If we removed the current server, emit new state
    if (currentState.server?.id == serverId) {
      final newCurrent = _serverRegistry.currentServer;
      if (newCurrent == null) {
        _stateSubject.add(const AppStateNoServer());
      } else {
        // Re-initialize for new server
        await initialize();
      }
    } else {
      // Just re-emit current state to trigger provider rebuild
      _stateSubject.add(currentState);
    }
  }

  /// Select a server from history.
  /// Probes and transitions to appropriate state.
  Future<void> selectServerFromHistory(String serverId) async {
    DebugLog.service('AppStateManager: Selecting server $serverId from history');

    try {
      final server = await _serverRegistry.setCurrentServer(serverId);

      if (!server.requiresAuth) {
        _stateSubject.add(AppStateReady(server: server));
        return;
      }

      // Check for valid token
      final hasValidToken = await _authManager.hasValidToken(server.id);
      if (hasValidToken) {
        final userInfo = await _authManager.getUserInfo(server);
        _stateSubject.add(AppStateReady(
          server: server,
          userName: userInfo?.name,
          userEmail: userInfo?.email,
        ));
      } else {
        // Need to probe server to get OIDC providers
        final serverInfo = await _serverRegistry.probeServer(server.url);
        _stateSubject.add(AppStateNeedsAuth(
          server: server,
          providers: serverInfo.oidcProviders,
        ));
      }
    } catch (e) {
      DebugLog.error('AppStateManager: Error selecting server: $e');
      _stateSubject.add(AppStateError('Failed to select server: $e'));
    }
  }

  void dispose() {
    _stateSubject.close();
  }
}
