import 'package:rxdart/rxdart.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/services/auth_manager.dart';
import 'package:soliplex/core/services/server_registry.dart';
import 'package:soliplex/core/state/app_state.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// Manager for application state.
///
/// Uses a BehaviorSubject stream instead of ChangeNotifier.
/// Explicit state transitions via methods.
/// Single source of truth for app state.
class AppStateManager {
  AppStateManager({
    required ServerRegistry serverRegistry,
    required AuthManager authManager,
  }) : _serverRegistry = serverRegistry,
       _authManager = authManager;
  final ServerRegistry _serverRegistry;
  final AuthManager _authManager;

  final _stateSubject = BehaviorSubject<AppState>.seeded(
    const AppStateNoServer(),
  );

  /// Stream of app state changes.
  Stream<AppState> get state => _stateSubject.stream;

  /// Current state value.
  AppState get currentState => _stateSubject.value;

  /// Initialize - check for saved server and auth state.
  Future<void> initialize() async {
    DebugLog.service('AppStateManager: initialize()');

    try {
      await _serverRegistry.initialize();
      final server = _serverRegistry.currentServer;

      if (server == null) {
        DebugLog.service('AppStateManager: No saved server');
        _stateSubject.add(const AppStateNoServer());
        return;
      }

      DebugLog.service(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'AppStateManager: Found server ${server.url}, requiresAuth=${server.requiresAuth}',
      );

      if (!server.requiresAuth) {
        DebugLog.service('AppStateManager: Server ready (no auth required)');
        _stateSubject.add(AppStateReady(server: server));
        return;
      }

      // Check for valid token
      final hasValidToken = await _authManager.hasValidToken(server.id);
      DebugLog.service('AppStateManager: hasValidToken=$hasValidToken');

      if (hasValidToken) {
        final userInfo = await _authManager.getUserInfo(server);
        DebugLog.service('AppStateManager: Valid token found, server ready');
        _stateSubject.add(
          AppStateReady(
            server: server,
            userName: userInfo?.name,
            userEmail: userInfo?.email,
          ),
        );
      } else {
        // Need to probe server to get OIDC providers
        DebugLog.service(
          'AppStateManager: No valid token, probing for providers',
        );
        final serverInfo = await _serverRegistry.probeServer(server.url);
        _stateSubject.add(
          AppStateNeedsAuth(
            server: server,
            providers: serverInfo.oidcProviders,
          ),
        );
      }
    } on Object catch (e) {
      DebugLog.error('AppStateManager: Initialization error: $e');
      _stateSubject.add(AppStateError('Failed to initialize: $e'));
    }
  }

  /// Set server (from setup screen).
  /// Probes server and transitions to appropriate state.
  Future<void> setServer(
    ServerInfo serverInfo, {
    String? displayName,
    EndpointConfiguration? config,
  }) async {
    DebugLog.service('AppStateManager: setServer() url=${serverInfo.url}');

    try {
      final server = await _serverRegistry.saveServer(
        serverInfo,
        displayName: displayName,
        config: config,
      );
      DebugLog.service(
        'AppStateManager: Saved server ${server.url} with id=${server.id}',
      );

      if (!server.requiresAuth) {
        DebugLog.service('AppStateManager: Server ready (no auth)');
        _stateSubject.add(AppStateReady(server: server));
      } else {
        DebugLog.service('AppStateManager: Server requires auth');
        _stateSubject.add(
          AppStateNeedsAuth(
            server: server,
            providers: serverInfo.oidcProviders,
          ),
        );
      }
    } on Object catch (e) {
      DebugLog.error('AppStateManager: Error setting server: $e');
      _stateSubject.add(AppStateError('Failed to set server: $e'));
    }
  }

  /// Start OIDC login.
  ///
  /// On web, this will throw OidcWebRedirectException when the browser
  /// redirects to the OIDC provider. The app will reload at /auth/callback
  /// where [initializeWithServer] will be called.
  Future<void> startLogin(OIDCAuthSystem provider) async {
    DebugLog.service('AppStateManager: startLogin() provider=${provider.id}');
    final current = currentState;
    if (current is! AppStateNeedsAuth) {
      DebugLog.warn(
        'AppStateManager: startLogin called in wrong state: $current',
      );
      return;
    }

    DebugLog.service(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'AppStateManager: Starting login with provider ${provider.id}, server=${current.server.id}',
    );
    _stateSubject.add(
      AppStateAuthenticating(server: current.server, provider: provider),
    );

    try {
      final userInfo = await _authManager.login(provider, current.server);
      DebugLog.service('AppStateManager: Login successful');
      _stateSubject.add(
        AppStateReady(
          server: current.server,
          userName: userInfo?.name,
          userEmail: userInfo?.email,
        ),
      );
    } on OidcWebRedirectException catch (e) {
      // Web auth redirect - browser is navigating to OIDC provider
      // Keep Authenticating state - app will reload at /auth/callback
      DebugLog.auth(
        'AppStateManager: Web auth redirect for server ${e.serverId}',
      );
      // State stays as Authenticating - this is expected on web
    } on Object catch (e) {
      DebugLog.error('AppStateManager: Login failed: $e');
      _stateSubject.add(
        AppStateError('Authentication failed: $e', previousState: current),
      );
    }
  }

  /// Initialize the app with a specific server (used after web auth callback).
  ///
  /// Called by AuthCallbackScreen after tokens are successfully exchanged.
  Future<void> initializeWithServer(String serverId) async {
    DebugLog.service(
      'AppStateManager: initializeWithServer() serverId=$serverId',
    );

    try {
      await _serverRegistry.initialize();
      final server = await _serverRegistry.setCurrentServer(serverId);
      DebugLog.service(
        'AppStateManager: Server ID from registry: ${server.id}',
      );

      // At this point we should have valid tokens from the callback
      final hasValidToken = await _authManager.hasValidToken(server.id);
      DebugLog.service(
        'AppStateManager: Checking for token with server.id=${server.id}, '
        'hasValidToken=$hasValidToken',
      );
      if (hasValidToken) {
        final userInfo = await _authManager.getUserInfo(server);
        DebugLog.service('AppStateManager: Server ready after auth callback');
        _stateSubject.add(
          AppStateReady(
            server: server,
            userName: userInfo?.name,
            userEmail: userInfo?.email,
          ),
        );
      } else {
        // Shouldn't happen - callback should have stored tokens
        DebugLog.error('AppStateManager: No valid token after callback');
        _stateSubject.add(
          const AppStateError('Authentication failed: No valid token received'),
        );
      }
    } on Object catch (e) {
      DebugLog.error('AppStateManager: initializeWithServer error: $e');
      _stateSubject.add(AppStateError('Failed to initialize: $e'));
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
    _stateSubject.add(
      AppStateNeedsAuth(
        server: current.server,
        providers: serverInfo.oidcProviders,
      ),
    );
  }

  /// Handle authentication required (e.g., token refresh failed).
  ///
  /// Called when an API request fails with 401 and token refresh fails.
  /// Transitions to NeedsAuth state so user can re-authenticate.
  Future<void> requireReauthentication(String serverId) async {
    DebugLog.service(
      'AppStateManager: requireReauthentication() serverId=$serverId',
    );

    final current = currentState;

    // Only handle if we're in Ready state for this server
    if (current is! AppStateReady || current.server.id != serverId) {
      DebugLog.warn(
        'AppStateManager: requireReauthentication called in wrong state or '
        'for different server. Current: $current, requested: $serverId',
      );
      return;
    }

    try {
      // Tokens are already cleared by AuthManager when refresh fails
      // Re-probe server to get OIDC providers
      final serverInfo = await _serverRegistry.probeServer(current.server.url);
      DebugLog.service(
        'AppStateManager: Transitioning to NeedsAuth for re-authentication',
      );
      _stateSubject.add(
        AppStateNeedsAuth(
          server: current.server,
          providers: serverInfo.oidcProviders,
        ),
      );
    } on Object catch (e) {
      DebugLog.error(
        'AppStateManager: Error during requireReauthentication: $e',
      );
      _stateSubject.add(
        AppStateError(
          'Re-authentication required but failed to probe server: $e',
          previousState: current,
        ),
      );
    }
  }

  /// Switch to a different server.
  Future<void> switchServer(
    ServerInfo serverInfo, {
    String? displayName,
  }) async {
    // Note: We do NOT clear tokens here anymore.
    // Switching servers should preserve session state for the previous server
    // so we can switch back without re-login.
    // Explicit logout is required to clear tokens.
    DebugLog.service('AppStateManager: Switching server to ${serverInfo.url}');

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
      // Re-emit current state to trigger provider rebuild
      _stateSubject.add(currentState);
    }
  }

  /// Select a server from history.
  /// Probes and transitions to appropriate state.
  Future<void> selectServerFromHistory(String serverId) async {
    DebugLog.service(
      'AppStateManager: selectServerFromHistory() serverId=$serverId',
    );

    try {
      final server = await _serverRegistry.setCurrentServer(serverId);

      if (!server.requiresAuth) {
        DebugLog.service('AppStateManager: Server ready (no auth)');
        _stateSubject.add(AppStateReady(server: server));
        return;
      }

      // Check for valid token
      final hasValidToken = await _authManager.hasValidToken(server.id);
      if (hasValidToken) {
        final userInfo = await _authManager.getUserInfo(server);
        DebugLog.service('AppStateManager: Valid token found, server ready');
        _stateSubject.add(
          AppStateReady(
            server: server,
            userName: userInfo?.name,
            userEmail: userInfo?.email,
          ),
        );
      } else {
        // Need to probe server to get OIDC providers
        final serverInfo = await _serverRegistry.probeServer(server.url);
        _stateSubject.add(
          AppStateNeedsAuth(
            server: server,
            providers: serverInfo.oidcProviders,
          ),
        );
      }
    } on Object catch (e) {
      DebugLog.error('AppStateManager: Error selecting server: $e');
      _stateSubject.add(AppStateError('Failed to select server: $e'));
    }
  }

  void dispose() {
    _stateSubject.close();
  }
}
