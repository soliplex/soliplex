import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex/core/auth/oidc_auth_interactor.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/sso_config.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/http_config.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// User info retrieved from server.
class UserInfo {
  const UserInfo({this.id, this.name, this.email});

  factory UserInfo.fromJson(Map<String, dynamic> json) {
    return UserInfo(
      id: json['sub'] as String?,
      name: json['name'] as String?,
      email: json['email'] as String?,
    );
  }
  final String? id;
  final String? name;
  final String? email;
}

/// Manager for OIDC authentication operations.
///
/// Plain class (no ChangeNotifier) for auth operations.
/// Methods return data directly, no notifications.
///
/// Optionally accepts NetworkInspector for traffic observability.
/// HTTP calls are instrumented to appear in the Network Inspector panel.
class AuthManager {
  AuthManager({
    required SecureStorageService storage,
    required OidcAuthInteractor oidcInteractor,
    required SecureTokenStorage tokenStorage,
    http.Client? httpClient,
    NetworkInspector? inspector,
  }) : _storage = storage,
       _oidcInteractor = oidcInteractor,
       _tokenStorage = tokenStorage,
       _httpClient = httpClient ?? http.Client(),
       _inspector = inspector;
  final SecureStorageService _storage;
  final OidcAuthInteractor _oidcInteractor;
  final SecureTokenStorage _tokenStorage;
  final http.Client _httpClient;
  final NetworkInspector? _inspector;

  /// Per-server refresh lock to prevent concurrent token refreshes.
  /// Key is serverId, value is the in-flight refresh Future.
  final Map<String, Future<bool>> _refreshLocks = {};

  /// Check if we have a valid (non-expired) token for a server.
  Future<bool> hasValidToken(String serverId) async {
    DebugLog.service(
      'AuthManager.hasValidToken: checking for serverId=$serverId',
    );
    final token = await _storage.getAccessToken(serverId);
    DebugLog.service(
      'AuthManager.hasValidToken: token found=${token != null}, '
      'length=${token?.length ?? 0}',
    );
    if (token == null) return false;

    final expiry = await _storage.getTokenExpiry(serverId);
    DebugLog.service('AuthManager.hasValidToken: expiry=$expiry');
    if (expiry != null && DateTime.now().isAfter(expiry)) {
      // Token expired - try refresh
      DebugLog.service(
        'AuthManager.hasValidToken: token expired, trying refresh',
      );
      return _tryRefreshToken(serverId);
    }

    return true;
  }

  /// Get user info from server using stored token.
  Future<UserInfo?> getUserInfo(ServerConnection server) async {
    final token = await _storage.getAccessToken(server.id);
    if (token == null) return null;

    return _fetchUserInfo(server.url, token);
  }

  /// Start OIDC login flow.
  /// Returns UserInfo on success, throws on failure.
  Future<UserInfo?> login(
    OIDCAuthSystem provider,
    ServerConnection server,
  ) async {
    DebugLog.service(
      'AuthManager.login: Starting with provider ${provider.id}',
    );

    try {
      // Clear any existing OIDC tokens and config to avoid stale state
      DebugLog.service('AuthManager: Clearing existing OIDC tokens and config');
      await _tokenStorage.deleteOidcAuthTokenResponse();
      await _oidcInteractor.clearSsoConfig(server.id);

      // Build SsoConfig from OIDCAuthSystem
      final issuerUrl = provider.serverUrl;
      final scopes =
          provider.scope?.split(' ') ?? ['openid', 'profile', 'email'];
      DebugLog.service('AuthManager: issuerUrl=$issuerUrl, scopes=$scopes');

      final ssoConfig = SsoConfig(
        id: provider.id,
        title: provider.title,
        endpoint: issuerUrl,
        tokenEndpoint: '$issuerUrl/protocol/openid-connect/token',
        loginUrl: Uri.parse('$issuerUrl/protocol/openid-connect/auth'),
        clientId: provider.clientId,
        redirectUrl: _getRedirectUrl(provider.id),
        scopes: scopes,
        serverBaseUrl: server.url, // For web backend-mediated OAuth
      );

      // Enable auth on the interactor
      _oidcInteractor.useAuth = true;

      // Use flutter_appauth for native OIDC flow
      DebugLog.service('AuthManager: Calling authorizeAndExchangeCode...');
      final tokenResponse = await _oidcInteractor.authorizeAndExchangeCode(
        server.id,
        ssoConfig,
      );

      DebugLog.service(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'AuthManager: Got token response, expiry=${tokenResponse.accessTokenExpiration}',
      );

      // Store tokens
      await _storage.storeTokens(
        serverId: server.id,
        accessToken: tokenResponse.accessToken,
        refreshToken: tokenResponse.refreshToken,
        expiresAt: tokenResponse.accessTokenExpiration,
      );
      DebugLog.service('AuthManager: Tokens stored');

      // Fetch user info
      final userInfo = await _fetchUserInfo(
        server.url,
        tokenResponse.accessToken,
      );
      DebugLog.service('AuthManager: User info: $userInfo');

      return userInfo;
    } on Object catch (e) {
      DebugLog.error('AuthManager: OIDC login failed: $e');
      rethrow;
    }
  }

  /// Logout - clear tokens and OIDC session.
  Future<void> logout(ServerConnection server) async {
    DebugLog.service('AuthManager: Logout initiated for server ${server.id}');
    
    // Clear local tokens FIRST to ensure we are locally logged out
    // before any potential redirects or network calls.
    await _storage.clearTokens(server.id);
    DebugLog.service('AuthManager: Local tokens cleared');

    try {
      // Try to logout via OIDC provider
      final ssoConfig = await _oidcInteractor.getSsoConfig(server.id);
      DebugLog.service('AuthManager: SSO config found: ${ssoConfig != null}');
      
      if (ssoConfig != null) {
        await _oidcInteractor.logout(server.id, ssoConfig);
      } else {
        DebugLog.warn(
          'AuthManager: Skipping OIDC logout - no SSO config found',
        );
      }
    } on OidcWebRedirectException catch (e) {
      DebugLog.service(
        'AuthManager: Redirecting for OIDC logout: ${e.serverId}',
      );
      // Allow exception to propagate or just return?
      // Since we are redirecting, the app context is ending.
    } on Object catch (e) {
      DebugLog.error('AuthManager: OIDC logout failed: $e');
      // Continue with local logout even if OIDC logout fails
    }

    // Disable auth on interactor
    _oidcInteractor.useAuth = false;
  }

  /// Clear tokens for a server.
  Future<void> clearTokens(String serverId) async {
    await _storage.clearTokens(serverId);
  }

  /// Get current access token (for API calls).
  Future<String?> getAccessToken(String serverId) async {
    // Check if we need to refresh
    final expiry = await _storage.getTokenExpiry(serverId);
    if (expiry != null &&
        DateTime.now().isAfter(expiry.subtract(const Duration(minutes: 5)))) {
      // Token expiring soon, try refresh
      await _tryRefreshToken(serverId);
    }

    return _storage.getAccessToken(serverId);
  }

  /// Get auth headers for API calls.
  Future<Map<String, String>> getAuthHeaders(String serverId) async {
    DebugLog.network('AuthManager.getAuthHeaders: serverId=$serverId');
    final token = await getAccessToken(serverId);
    DebugLog.network(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'AuthManager.getAuthHeaders: token=${token != null ? "present (${token.length} chars)" : "null"}',
    );
    if (token == null) return {};
    return {'Authorization': 'Bearer $token'};
  }

  String _getRedirectUrl(String providerId) {
    if (kIsWeb) {
      // Hash-based routing: redirect to /#/auth/callback with tokens in query
      // Must be absolute for OIDC logout
      return '${Uri.base.origin}/#/auth/callback';
    } else {
      return 'ai.soliplex.client://callback';
    }
  }

  Future<UserInfo?> _fetchUserInfo(String serverUrl, String token) async {
    final urlBuilder = UrlBuilder(serverUrl);
    final uri = urlBuilder.userInfo();
    final headers = {'Authorization': 'Bearer $token'};

    DebugLog.network('AuthManager: Fetching user info from $uri');

    // Record request for Network Inspector
    final requestId = _inspector?.recordRequest(
      method: 'GET',
      uri: uri,
      headers: headers,
    );

    try {
      final response = await _httpClient
          .get(uri, headers: headers)
          .timeout(HttpConfig.defaultTimeout);

      // Record response for Network Inspector
      if (requestId != null) {
        _inspector?.recordResponse(
          requestId: requestId,
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
        );
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return UserInfo.fromJson(data);
      }
    } on Object catch (e) {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      DebugLog.error('AuthManager: Failed to fetch user info: $e');
      rethrow; // Propagate error - auth should fail if user info can't be fetched // ignore: lines_longer_than_80_chars (auto-documented)
    }
    return null;
  }

  Future<bool> _tryRefreshToken(String serverId) async {
    DebugLog.service(
      'AuthManager: Attempting token refresh for server $serverId',
    );

    // If refresh already in progress for this server, wait for it
    if (_refreshLocks.containsKey(serverId)) {
      DebugLog.service(
        'AuthManager: Refresh already in progress for $serverId, waiting...',
      );
      try {
        await _refreshLocks[serverId];
      } on Object catch (_) {
        // Previous refresh failed, check if token exists anyway
      }
      return (await _storage.getAccessToken(serverId)) != null;
    }

    // Create lock for this server
    final completer = Completer<bool>();
    _refreshLocks[serverId] = completer.future;

    try {
      final ssoConfig = await _oidcInteractor.getSsoConfig(serverId);
      if (ssoConfig == null) {
        DebugLog.warn('AuthManager: No SSO config found for token refresh');
        completer.complete(false);
        return false;
      }

      final tokenResponse = await _oidcInteractor.refreshAccessToken(
        serverId,
        ssoConfig,
      );
      if (tokenResponse == null) {
        DebugLog.warn('AuthManager: Token refresh returned null');
        completer.complete(false);
        return false;
      }

      // Update stored tokens
      await _storage.storeTokens(
        serverId: serverId,
        accessToken: tokenResponse.accessToken,
        refreshToken: tokenResponse.refreshToken,
        expiresAt: tokenResponse.accessTokenExpiration,
      );

      DebugLog.service('AuthManager: Token refreshed successfully');
      completer.complete(true);
      return true;
    } on Object catch (e) {
      DebugLog.error('AuthManager: Token refresh failed: $e');
      completer.complete(false);
      return false;
    } finally {
      unawaited(_refreshLocks.remove(serverId));
    }
  }

  void dispose() {
    _httpClient.close();
  }
}
