import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import 'secure_storage_service.dart';
import 'server_config_service.dart'; // exports server_models.dart

/// Service for handling OIDC authentication flow.
///
/// Handles:
/// - Initiating OIDC login flow
/// - Processing auth callbacks (tokens from redirect)
/// - Token validation and refresh
/// - User info retrieval
/// - Logout
class AuthService extends ChangeNotifier {
  final SecureStorageService _storage;
  final ServerConfigService _serverConfig;
  final http.Client _httpClient;

  AuthState _state = const AuthState.initial();
  Completer<TokenData?>? _authCompleter;

  AuthService({
    required SecureStorageService storage,
    required ServerConfigService serverConfig,
    http.Client? httpClient,
  })  : _storage = storage,
        _serverConfig = serverConfig,
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

  /// Start OIDC login flow with the specified provider
  Future<void> startLogin(OIDCAuthSystem provider) async {
    final server = _serverConfig.currentServer;
    if (server == null) {
      throw StateError('No server configured');
    }

    _state = _state.copyWith(status: AuthStatus.authenticating);
    notifyListeners();

    // Build the login URL
    final returnTo = _getReturnUrl();
    final loginUrl = Uri.parse(
      '${server.url}/login/${provider.id}?return_to=$returnTo',
    );

    // Launch browser for OIDC flow
    try {
      final launched = await launchUrl(
        loginUrl,
        mode: kIsWeb
            ? LaunchMode.platformDefault
            : LaunchMode.externalApplication,
      );

      if (!launched) {
        _state = _state.copyWith(
          status: AuthStatus.error,
          error: 'Could not open login page',
        );
        notifyListeners();
      }

      // Set up completer for waiting on callback
      _authCompleter = Completer<TokenData?>();
    } catch (e) {
      _state = _state.copyWith(
        status: AuthStatus.error,
        error: 'Failed to start login: $e',
      );
      notifyListeners();
    }
  }

  /// Get the return URL for OIDC callback
  String _getReturnUrl() {
    if (kIsWeb) {
      // On web, return to the current page with auth path
      // The actual URL will be configured in the web app
      return Uri.base.replace(path: '/auth/callback').toString();
    } else {
      // On mobile/desktop, use custom scheme
      return 'soliplex://auth';
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
      final response = await _httpClient.get(
        Uri.parse('$serverUrl/user_info'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (e) {
      debugPrint('AuthService: Failed to fetch user info: $e');
    }
    return null;
  }

  /// Try to refresh the token
  Future<bool> _tryRefreshToken(String serverId) async {
    final refreshToken = await _storage.getRefreshToken(serverId);
    if (refreshToken == null) return false;

    // Note: Server-side refresh implementation depends on the OIDC provider
    // This is a placeholder for when refresh endpoint is available
    debugPrint('AuthService: Token refresh not yet implemented');
    return false;
  }

  /// Logout - clear tokens and reset state
  Future<void> logout() async {
    final server = _serverConfig.currentServer;
    if (server != null) {
      await _storage.clearTokens(server.id);
    }

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
final authServiceProvider = ChangeNotifierProvider<AuthService>((ref) {
  final storage = ref.watch(secureStorageProvider);
  final serverConfig = ref.watch(serverConfigProvider);
  return AuthService(
    storage: storage,
    serverConfig: serverConfig,
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
