import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../auth/oidc_auth_interactor.dart';
import '../auth/secure_token_storage.dart';
import '../auth/sso_config.dart';
import '../models/server_models.dart';
import '../network/network_inspector.dart';
import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'secure_storage_service.dart';

/// User info retrieved from server.
class UserInfo {
  final String? id;
  final String? name;
  final String? email;

  const UserInfo({this.id, this.name, this.email});

  factory UserInfo.fromJson(Map<String, dynamic> json) {
    return UserInfo(
      id: json['sub'] as String?,
      name: json['name'] as String?,
      email: json['email'] as String?,
    );
  }
}

/// Manager for OIDC authentication operations.
///
/// Plain class (no ChangeNotifier) for auth operations.
/// Methods return data directly, no notifications.
///
/// Optionally accepts [NetworkInspector] for traffic observability.
/// HTTP calls are instrumented to appear in the Network Inspector panel.
class AuthManager {
  final SecureStorageService _storage;
  final OidcAuthInteractor _oidcInteractor;
  final SecureTokenStorage _tokenStorage;
  final http.Client _httpClient;
  final NetworkInspector? _inspector;

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

  /// Check if we have a valid (non-expired) token for a server.
  Future<bool> hasValidToken(String serverId) async {
    final token = await _storage.getAccessToken(serverId);
    if (token == null) return false;

    final expiry = await _storage.getTokenExpiry(serverId);
    if (expiry != null && DateTime.now().isAfter(expiry)) {
      // Token expired - try refresh
      return await _tryRefreshToken(serverId);
    }

    return true;
  }

  /// Get user info from server using stored token.
  Future<UserInfo?> getUserInfo(ServerConnection server) async {
    final token = await _storage.getAccessToken(server.id);
    if (token == null) return null;

    return await _fetchUserInfo(server.url, token);
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
      await _oidcInteractor.clearSsoConfig();

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
        redirectUrl: _getRedirectUrl(),
        scopes: scopes,
      );

      // Enable auth on the interactor
      _oidcInteractor.useAuth = true;

      // Use flutter_appauth for native OIDC flow
      DebugLog.service('AuthManager: Calling authorizeAndExchangeCode...');
      final tokenResponse = await _oidcInteractor.authorizeAndExchangeCode(
        ssoConfig,
      );
      DebugLog.service(
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
    } catch (e) {
      DebugLog.error('AuthManager: OIDC login failed: $e');
      rethrow;
    }
  }

  /// Logout - clear tokens and OIDC session.
  Future<void> logout(ServerConnection server) async {
    try {
      // Try to logout via OIDC provider
      final ssoConfig = await _oidcInteractor.getSsoConfig();
      if (ssoConfig != null) {
        await _oidcInteractor.logout(ssoConfig);
      }
    } catch (e) {
      DebugLog.error('AuthManager: OIDC logout failed: $e');
      // Continue with local logout even if OIDC logout fails
    }

    // Clear local tokens
    await _storage.clearTokens(server.id);

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

    return await _storage.getAccessToken(serverId);
  }

  /// Get auth headers for API calls.
  Future<Map<String, String>> getAuthHeaders(String serverId) async {
    DebugLog.network('AuthManager.getAuthHeaders: serverId=$serverId');
    final token = await getAccessToken(serverId);
    DebugLog.network(
      'AuthManager.getAuthHeaders: token=${token != null ? "present (${token.length} chars)" : "null"}',
    );
    if (token == null) return {};
    return {'Authorization': 'Bearer $token'};
  }

  String _getRedirectUrl() {
    if (kIsWeb) {
      return Uri.base.replace(path: '/auth/callback').toString();
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
          .timeout(const Duration(seconds: 10));

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
    } catch (e) {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      DebugLog.error('AuthManager: Failed to fetch user info: $e');
    }
    return null;
  }

  Future<bool> _tryRefreshToken(String serverId) async {
    try {
      final ssoConfig = await _oidcInteractor.getSsoConfig();
      if (ssoConfig == null) {
        DebugLog.warn('AuthManager: No SSO config found for token refresh');
        return false;
      }

      final tokenResponse = await _oidcInteractor.refreshAccessToken(ssoConfig);
      if (tokenResponse == null) {
        DebugLog.warn('AuthManager: Token refresh returned null');
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
      return true;
    } catch (e) {
      DebugLog.error('AuthManager: Token refresh failed: $e');
      return false;
    }
  }

  void dispose() {
    _httpClient.close();
  }
}
