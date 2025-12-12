import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'oidc_auth_token_response.dart';
import 'secure_sso_storage.dart';
import 'secure_token_storage.dart';
import 'sso_config.dart';

/// Exception thrown when SSO config is not set but auth is required.
class SsoConfigNotSetException implements Exception {
  final String message;
  SsoConfigNotSetException([
    this.message = 'Single sign on config has not been selected. '
        'Please try again after selecting a SSO configuration.',
  ]);

  @override
  String toString() => message;
}

/// Abstract interface for OIDC authentication.
abstract class OidcAuthInteractor {
  bool useAuth = false;
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(SsoConfig config);
  Future<OidcAuthTokenResponse?> refreshAccessToken(SsoConfig config);
  Future<OidcAuthTokenResponse?> getTokenResponse();
  Future<String?> getRefreshToken();
  Future<SsoConfig?> getSsoConfig();
  Future<void> setSsoConfig(SsoConfig config);
  Future<void> clearSsoConfig();
  bool isTokenExpiring(OidcAuthTokenResponse? tokenResponse);
  Future<void> applyToRequest(http.BaseRequest request);
  Future<void> applyToHeader(Map<String, String> headers);
  Future<void> logout(SsoConfig config);
}

/// Base class with shared implementation for OIDC authentication.
///
/// Provides common implementation for:
/// - [applyToRequest] - Apply auth token to HTTP request
/// - [applyToHeader] - Apply auth token to headers map
/// - [isTokenExpiring] - Check if token is near expiration
/// - Storage accessors (getTokenResponse, getRefreshToken, getSsoConfig, setSsoConfig)
///
/// Subclasses must implement platform-specific methods:
/// - [authorizeAndExchangeCode] - Initiate OAuth flow
/// - [refreshAccessToken] - Refresh expired token
/// - [logout] - End session
abstract class OidcAuthInteractorBase implements OidcAuthInteractor {
  final SecureSsoStorage ssoStorage;
  final SecureTokenStorage tokenStorage;
  final Duration tokenExpirationBuffer;

  OidcAuthInteractorBase({
    required this.ssoStorage,
    required this.tokenStorage,
    required this.tokenExpirationBuffer,
  });

  @override
  bool useAuth = false;

  // =========================================================================
  // Storage accessors (shared implementation)
  // =========================================================================

  @override
  Future<OidcAuthTokenResponse?> getTokenResponse() =>
      tokenStorage.getOidcAuthTokenResponse();

  @override
  Future<String?> getRefreshToken() => tokenStorage.getOidcRefreshToken();

  @override
  Future<SsoConfig?> getSsoConfig() => ssoStorage.getSsoConfig();

  @override
  Future<void> setSsoConfig(SsoConfig config) => ssoStorage.setSsoConfig(config);

  @override
  Future<void> clearSsoConfig() => ssoStorage.deleteSsoConfig();

  // =========================================================================
  // Token expiration check (shared implementation)
  // =========================================================================

  @override
  bool isTokenExpiring(OidcAuthTokenResponse? tokenResponse) {
    if (tokenResponse == null) return true;

    final expirationThreshold = DateTime.now().add(tokenExpirationBuffer);
    return tokenResponse.accessTokenExpiration.isBefore(expirationThreshold);
  }

  // =========================================================================
  // Token application (shared implementation)
  // =========================================================================

  @override
  Future<void> applyToRequest(http.BaseRequest request) async {
    if (!useAuth) {
      debugPrint('Request to apply token to request with disabled auth');
      return;
    }

    final headers = <String, String>{};
    await _applyTokenToHeaders(headers);
    request.headers.addAll(headers);
  }

  @override
  Future<void> applyToHeader(Map<String, String> headers) async {
    if (!useAuth) {
      debugPrint('Request to apply token to header with disabled auth');
      return;
    }

    await _applyTokenToHeaders(headers);
  }

  /// Internal implementation of token application logic.
  Future<void> _applyTokenToHeaders(Map<String, String> headers) async {
    final currentToken = await getTokenResponse();
    final expiring = isTokenExpiring(currentToken);

    if (expiring) {
      debugPrint('Token expired or expiring.');
      final token = await _refreshOrReauth();
      headers['authorization'] = 'Bearer $token';
    } else {
      debugPrint('Token not expired.');
      debugPrint('Current token expiration: ${currentToken!.accessTokenExpiration}');
      headers['authorization'] = 'Bearer ${currentToken.accessToken}';
    }
  }

  /// Attempt to refresh the token, falling back to re-authorization if needed.
  Future<String> _refreshOrReauth() async {
    final ssoConfig = await getSsoConfig();

    if (ssoConfig == null) {
      debugPrint('SSO config has not been set.');
      throw SsoConfigNotSetException();
    }

    // Try to refresh the token first
    OidcAuthTokenResponse? refreshResponse;
    try {
      debugPrint('Attempting token refresh...');
      refreshResponse = await refreshAccessToken(ssoConfig);
    } catch (e) {
      debugPrint('Token refresh failed: $e');
      refreshResponse = null;
    }

    if (refreshResponse != null) {
      debugPrint('Refresh successful');
      debugPrint('New token expiration: ${refreshResponse.accessTokenExpiration}');
      return refreshResponse.accessToken;
    }

    // Refresh failed, need to re-authenticate
    debugPrint('Refresh not successful, re-authenticating...');
    final newTokenResponse = await authorizeAndExchangeCode(ssoConfig);
    debugPrint('Signed in again. New expiration: ${newTokenResponse.accessTokenExpiration}');
    return newTokenResponse.accessToken;
  }

  // =========================================================================
  // Platform-specific methods (must be implemented by subclasses)
  // =========================================================================

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(SsoConfig config);

  @override
  Future<OidcAuthTokenResponse?> refreshAccessToken(SsoConfig config);

  @override
  Future<void> logout(SsoConfig config);
}
