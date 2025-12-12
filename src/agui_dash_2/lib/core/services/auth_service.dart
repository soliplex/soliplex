import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../auth/auth_providers.dart';
import '../auth/oidc_auth_interactor.dart';
import '../auth/secure_token_storage.dart';
import '../auth/sso_config.dart';
import '../utils/url_builder.dart';
import 'secure_storage_service.dart';
import 'server_config_service.dart'; // exports server_models.dart

/// Service for handling OIDC authentication flow.
///
/// Handles:
/// - Initiating OIDC login flow via flutter_appauth
/// - Processing auth callbacks (tokens from redirect)
/// - Token validation and refresh
/// - User info retrieval
/// - Logout
class AuthService extends ChangeNotifier {
  final SecureStorageService _storage;
  final ServerConfigService _serverConfig;
  final OidcAuthInteractor _oidcInteractor;
  final SecureTokenStorage _tokenStorage;
  final http.Client _httpClient;

  AuthState _state = const AuthState.initial();
  Completer<TokenData?>? _authCompleter;

  AuthService({
    required SecureStorageService storage,
    required ServerConfigService serverConfig,
    required OidcAuthInteractor oidcInteractor,
    required SecureTokenStorage tokenStorage,
    http.Client? httpClient,
  })  : _storage = storage,
        _serverConfig = serverConfig,
        _oidcInteractor = oidcInteractor,
        _tokenStorage = tokenStorage,
        _httpClient = httpClient ?? http.Client();

  // Getters
  AuthState get state => _state;
  bool get isAuthenticated => _state.isAuthenticated;
  bool get needsAuth => _state.needsAuth;

  /// Initialize auth state from stored credentials
  Future<void> initialize() async {
    final server = _serverConfig.currentServer;
    if (server == null) {
      _state = const AuthState(status: AuthStatus.noServer);
      notifyListeners();
      return;
    }

    // Check if server requires auth
    if (!server.requiresAuth) {
      _state = AuthState(
        status: AuthStatus.authenticated,
        currentServer: server,
      );
      notifyListeners();
      return;
    }

    // Check for stored token
    final token = await _storage.getAccessToken(server.id);
    final expiry = await _storage.getTokenExpiry(server.id);

    if (token == null) {
      _state = AuthState(
        status: AuthStatus.unauthenticated,
        currentServer: server,
      );
      notifyListeners();
      return;
    }

    // Check token expiry
    if (expiry != null && DateTime.now().isAfter(expiry)) {
      // Token expired - try refresh or mark as expired
      final refreshed = await _tryRefreshToken(server.id);
      if (!refreshed) {
        _state = AuthState(
          status: AuthStatus.tokenExpired,
          currentServer: server,
        );
        notifyListeners();
        return;
      }
    }

    // Validate token and get user info
    final userInfo = await _fetchUserInfo(server.url, token);
    if (userInfo != null) {
      _state = AuthState(
        status: AuthStatus.authenticated,
        currentServer: server,
        userId: userInfo['sub'] as String?,
        userName: userInfo['name'] as String?,
        userEmail: userInfo['email'] as String?,
      );
    } else {
      _state = AuthState(
        status: AuthStatus.tokenExpired,
        currentServer: server,
      );
    }
    notifyListeners();
  }

  /// Start OIDC login flow with the specified provider using flutter_appauth
  Future<void> startLogin(OIDCAuthSystem provider) async {
    debugPrint('AuthService.startLogin: Starting with provider ${provider.id}');
    final server = _serverConfig.currentServer;
    if (server == null) {
      debugPrint('AuthService.startLogin: No server configured!');
      throw StateError('No server configured');
    }
    debugPrint('AuthService.startLogin: Server=${server.url}');

    _state = _state.copyWith(status: AuthStatus.authenticating);
    notifyListeners();

    try {
      // Clear any existing OIDC tokens and config to avoid stale state on server switch
      debugPrint('AuthService: Clearing existing OIDC tokens and config before login');
      await _tokenStorage.deleteOidcAuthTokenResponse();
      await _oidcInteractor.clearSsoConfig();
      debugPrint('AuthService: Tokens and config cleared');

      // Build SsoConfig from OIDCAuthSystem
      // serverUrl is the OIDC issuer URL (e.g., https://keycloak.example.com/realms/myrealm)
      final issuerUrl = provider.serverUrl;
      final scopes = provider.scope?.split(' ') ?? ['openid', 'profile', 'email'];
      debugPrint('AuthService: issuerUrl=$issuerUrl, scopes=$scopes');

      final ssoConfig = SsoConfig(
        id: provider.id,
        title: provider.title,
        endpoint: issuerUrl,
        tokenEndpoint: '$issuerUrl/protocol/openid-connect/token',
        loginUrl: Uri.parse('$issuerUrl/protocol/openid-connect/auth'),
        clientId: provider.clientId,
        redirectUrl: _getRedirectUrl(),
        scopes: scopes,
      );
      debugPrint('AuthService: SsoConfig created, redirectUrl=${_getRedirectUrl()}');

      // Enable auth on the interactor
      _oidcInteractor.useAuth = true;

      // Use flutter_appauth for native OIDC flow
      debugPrint('AuthService: Calling authorizeAndExchangeCode...');
      final tokenResponse = await _oidcInteractor.authorizeAndExchangeCode(ssoConfig);
      debugPrint('AuthService: Got token response, expiry=${tokenResponse.accessTokenExpiration}');

      // Store tokens using existing storage service
      debugPrint('AuthService: Storing tokens...');
      await _storage.storeTokens(
        serverId: server.id,
        accessToken: tokenResponse.accessToken,
        refreshToken: tokenResponse.refreshToken,
        expiresAt: tokenResponse.accessTokenExpiration,
      );
      debugPrint('AuthService: Tokens stored');

      // Fetch user info
      debugPrint('AuthService: Fetching user info...');
      final userInfo = await _fetchUserInfo(server.url, tokenResponse.accessToken);
      debugPrint('AuthService: User info: $userInfo');

      _state = AuthState(
        status: AuthStatus.authenticated,
        currentServer: server.copyWith(tokenExpiry: tokenResponse.accessTokenExpiration),
        userId: userInfo?['sub'] as String?,
        userName: userInfo?['name'] as String?,
        userEmail: userInfo?['email'] as String?,
      );
      debugPrint('AuthService: State updated to authenticated');

      // Note: Don't call _serverConfig.updateServer() here as it triggers
      // notifyListeners() which causes AppShell to rebuild and interrupt the auth flow.
      // Token expiry is stored in _storage and in the AuthState.currentServer.

      notifyListeners();
    } catch (e) {
      debugPrint('AuthService: OIDC login failed: $e');
      _state = _state.copyWith(
        status: AuthStatus.error,
        error: 'Authentication failed: $e',
      );
      notifyListeners();
    }
  }

  /// Get the redirect URL for OIDC callback
  String _getRedirectUrl() {
    if (kIsWeb) {
      // On web, return to the current page with auth path
      return Uri.base.replace(path: '/auth/callback').toString();
    } else {
      // On mobile/desktop, use custom scheme matching Info.plist
      return 'ai.soliplex.client://callback';
    }
  }

  /// Handle OIDC callback with tokens
  Future<void> handleAuthCallback(Map<String, String> params) async {
    final server = _serverConfig.currentServer;
    if (server == null) {
      _authCompleter?.complete(null);
      return;
    }

    try {
      final tokenData = TokenData.fromCallbackParams(params);

      if (tokenData.accessToken.isEmpty) {
        throw StateError('No access token in callback');
      }

      // Store tokens
      await _storage.storeTokens(
        serverId: server.id,
        accessToken: tokenData.accessToken,
        refreshToken: tokenData.refreshToken,
        expiresAt: tokenData.expiresAt,
      );

      // Update server connection with token expiry
      await _serverConfig.updateServer(
        server.copyWith(tokenExpiry: tokenData.expiresAt),
      );

      // Fetch user info
      final userInfo = await _fetchUserInfo(server.url, tokenData.accessToken);

      _state = AuthState(
        status: AuthStatus.authenticated,
        currentServer: server.copyWith(tokenExpiry: tokenData.expiresAt),
        userId: userInfo?['sub'] as String?,
        userName: userInfo?['name'] as String?,
        userEmail: userInfo?['email'] as String?,
      );

      _authCompleter?.complete(tokenData);
    } catch (e) {
      _state = _state.copyWith(
        status: AuthStatus.error,
        error: 'Authentication failed: $e',
      );
      _authCompleter?.complete(null);
    }

    notifyListeners();
  }

  /// Fetch user info from server
  Future<Map<String, dynamic>?> _fetchUserInfo(
    String serverUrl,
    String token,
  ) async {
    try {
      final urlBuilder = UrlBuilder(serverUrl);
      final uri = urlBuilder.userInfo();
      debugPrint('AuthService: Fetching user info from $uri');
      debugPrint('AuthService: Token (first 20 chars): ${token.substring(0, token.length > 20 ? 20 : token.length)}...');

      final response = await _httpClient.get(
        uri,
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));

      debugPrint('AuthService: User info response status: ${response.statusCode}');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        debugPrint('AuthService: User info parsed: $data');
        return data;
      } else {
        debugPrint('AuthService: User info failed: ${response.body}');
      }
    } catch (e) {
      debugPrint('AuthService: Failed to fetch user info: $e');
    }
    return null;
  }

  /// Try to refresh the token using OidcAuthInteractor
  Future<bool> _tryRefreshToken(String serverId) async {
    try {
      final ssoConfig = await _oidcInteractor.getSsoConfig();
      if (ssoConfig == null) {
        debugPrint('AuthService: No SSO config found for token refresh');
        return false;
      }

      final tokenResponse = await _oidcInteractor.refreshAccessToken(ssoConfig);
      if (tokenResponse == null) {
        debugPrint('AuthService: Token refresh returned null');
        return false;
      }

      // Update stored tokens
      await _storage.storeTokens(
        serverId: serverId,
        accessToken: tokenResponse.accessToken,
        refreshToken: tokenResponse.refreshToken,
        expiresAt: tokenResponse.accessTokenExpiration,
      );

      debugPrint('AuthService: Token refreshed successfully');
      return true;
    } catch (e) {
      debugPrint('AuthService: Token refresh failed: $e');
      return false;
    }
  }

  /// Logout - clear tokens and reset state
  Future<void> logout() async {
    final server = _serverConfig.currentServer;

    try {
      // Try to logout via OIDC provider
      final ssoConfig = await _oidcInteractor.getSsoConfig();
      if (ssoConfig != null) {
        await _oidcInteractor.logout(ssoConfig);
      }
    } catch (e) {
      debugPrint('AuthService: OIDC logout failed: $e');
      // Continue with local logout even if OIDC logout fails
    }

    // Clear local tokens
    if (server != null) {
      await _storage.clearTokens(server.id);
    }

    // Disable auth on interactor
    _oidcInteractor.useAuth = false;

    _state = AuthState(
      status: AuthStatus.unauthenticated,
      currentServer: server,
    );
    notifyListeners();
  }

  /// Get current access token (for API calls)
  Future<String?> getAccessToken() async {
    final server = _serverConfig.currentServer;
    if (server == null) return null;

    // Check if we need to refresh
    final expiry = await _storage.getTokenExpiry(server.id);
    if (expiry != null &&
        DateTime.now().isAfter(expiry.subtract(const Duration(minutes: 5)))) {
      // Token expiring soon, try refresh
      await _tryRefreshToken(server.id);
    }

    return await _storage.getAccessToken(server.id);
  }

  /// Get auth headers for API calls
  Future<Map<String, String>> getAuthHeaders() async {
    final token = await getAccessToken();
    if (token == null) return {};
    return {'Authorization': 'Bearer $token'};
  }

  @override
  void dispose() {
    _httpClient.close();
    super.dispose();
  }
}

// ============================================================================
// Riverpod Providers
// ============================================================================

/// Provider for auth service
/// Note: Uses ref.read instead of ref.watch to prevent disposal during auth flow
/// when serverConfig.updateServer() triggers provider rebuilds
final authServiceProvider = ChangeNotifierProvider<AuthService>((ref) {
  final storage = ref.read(secureStorageProvider);
  final serverConfig = ref.read(serverConfigProvider);
  final oidcInteractor = ref.read(oidcAuthInteractorProvider);
  final tokenStorage = ref.read(secureTokenStorageProvider);
  return AuthService(
    storage: storage,
    serverConfig: serverConfig,
    oidcInteractor: oidcInteractor,
    tokenStorage: tokenStorage,
  );
});

/// Provider for current auth state
final authStateProvider = Provider<AuthState>((ref) {
  final auth = ref.watch(authServiceProvider);
  return auth.state;
});

/// Provider for authentication status
final isAuthenticatedProvider = Provider<bool>((ref) {
  final auth = ref.watch(authServiceProvider);
  return auth.isAuthenticated;
});

/// Provider for checking if auth is needed
final needsAuthProvider = Provider<bool>((ref) {
  final auth = ref.watch(authServiceProvider);
  return auth.needsAuth;
});

/// Provider for current user name
final currentUserNameProvider = Provider<String?>((ref) {
  final authState = ref.watch(authStateProvider);
  return authState.userName;
});
