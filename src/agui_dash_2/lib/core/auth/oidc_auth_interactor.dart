import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import 'oidc_auth_token_response.dart';
import 'oidc_token_application_mixin.dart';
import 'secure_sso_storage.dart';
import 'secure_token_storage.dart';
import 'sso_config.dart';

// Re-export the base class and interface for external use
export 'oidc_token_application_mixin.dart'
    show OidcAuthInteractor, OidcAuthInteractorBase, SsoConfigNotSetException;

/// Mobile/Desktop OIDC implementation using flutter_appauth.
///
/// Uses the native OAuth flow via ASWebAuthenticationSession (iOS/macOS)
/// or Chrome Custom Tabs (Android).
class OidcMobileAuthInteractor extends OidcAuthInteractorBase {
  final FlutterAppAuth _appAuth;

  OidcMobileAuthInteractor(
    this._appAuth,
    SecureSsoStorage ssoStorage,
    SecureTokenStorage tokenStorage,
    Duration tokenExpirationBuffer,
  ) : super(
          ssoStorage: ssoStorage,
          tokenStorage: tokenStorage,
          tokenExpirationBuffer: tokenExpirationBuffer,
        );

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    debugPrint('Signing in at ${DateTime.now()}');
    final response = await _authorizeAndExchangeCode(config);
    await tokenStorage.setOidcAuthTokenResponse(response);
    debugPrint('Expiration timestamp: ${response.accessTokenExpiration}');
    await setSsoConfig(config);
    return response;
  }

  Future<OidcAuthTokenResponse> _authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    debugPrint('_authorizeAndExchangeCode: calling flutter_appauth...');
    debugPrint('  clientId: ${config.clientId}');
    debugPrint('  redirectUrl: ${config.redirectUrl}');
    debugPrint('  issuer: ${config.endpoint}');
    debugPrint('  scopes: ${config.scopes}');

    try {
      final result = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          config.clientId,
          config.redirectUrl,
          scopes: config.scopes,
          issuer: config.endpoint,
          externalUserAgent: ExternalUserAgent.asWebAuthenticationSession,
        ),
      );

      debugPrint('_authorizeAndExchangeCode: got result from flutter_appauth');
      debugPrint('  idToken null? ${result.idToken == null}');
      debugPrint('  accessToken null? ${result.accessToken == null}');
      debugPrint('  expiration null? ${result.accessTokenExpirationDateTime == null}');
      debugPrint('  refreshToken null? ${result.refreshToken == null}');

      _validateTokenResult(
        idToken: result.idToken,
        accessToken: result.accessToken,
        expiration: result.accessTokenExpirationDateTime,
        refreshToken: result.refreshToken,
      );

      return OidcAuthTokenResponse(
        idToken: result.idToken!,
        accessToken: result.accessToken!,
        accessTokenExpiration: result.accessTokenExpirationDateTime!,
        refreshToken: result.refreshToken!,
      );
    } catch (e, stack) {
      debugPrint('_authorizeAndExchangeCode: EXCEPTION: $e');
      debugPrint('_authorizeAndExchangeCode: Stack: $stack');
      rethrow;
    }
  }

  @override
  Future<OidcAuthTokenResponse?> refreshAccessToken(SsoConfig config) async {
    debugPrint('Refreshing token.');
    final refreshToken = await tokenStorage.getOidcRefreshToken();
    if (refreshToken == null) {
      return null;
    }
    final response = await _refreshAccessToken(config, refreshToken);
    await tokenStorage.setOidcAuthTokenResponse(response);
    return response;
  }

  Future<OidcAuthTokenResponse> _refreshAccessToken(
    SsoConfig config,
    String refreshToken,
  ) async {
    final result = await _appAuth.token(
      TokenRequest(
        config.clientId,
        config.redirectUrl,
        scopes: config.scopes,
        issuer: config.endpoint,
        refreshToken: refreshToken,
      ),
    );

    _validateTokenResult(
      idToken: result.idToken,
      accessToken: result.accessToken,
      expiration: result.accessTokenExpirationDateTime,
      refreshToken: result.refreshToken,
    );

    return OidcAuthTokenResponse(
      idToken: result.idToken!,
      accessToken: result.accessToken!,
      accessTokenExpiration: result.accessTokenExpirationDateTime!,
      refreshToken: result.refreshToken!,
    );
  }

  @override
  Future<void> logout(SsoConfig config) async {
    final tokens = await tokenStorage.getOidcAuthTokenResponse();

    await _appAuth.endSession(
      EndSessionRequest(
        idTokenHint: tokens?.idToken,
        postLogoutRedirectUrl: config.redirectUrl,
        externalUserAgent: ExternalUserAgent.asWebAuthenticationSession,
        issuer: config.endpoint,
      ),
    );
    await tokenStorage.deleteOidcAuthTokenResponse();
    await ssoStorage.deleteSsoConfig();
  }

  /// Validate that all required token fields are present.
  void _validateTokenResult({
    required String? idToken,
    required String? accessToken,
    required DateTime? expiration,
    required String? refreshToken,
  }) {
    if (idToken == null ||
        accessToken == null ||
        expiration == null ||
        refreshToken == null) {
      throw OidcTokenValidationException(
        idTokenNull: idToken == null,
        accessTokenNull: accessToken == null,
        expirationNull: expiration == null,
        refreshTokenNull: refreshToken == null,
      );
    }
  }
}

/// Exception thrown when OIDC token response is missing required fields.
class OidcTokenValidationException implements Exception {
  final bool idTokenNull;
  final bool accessTokenNull;
  final bool expirationNull;
  final bool refreshTokenNull;

  OidcTokenValidationException({
    required this.idTokenNull,
    required this.accessTokenNull,
    required this.expirationNull,
    required this.refreshTokenNull,
  });

  @override
  String toString() => 'At least one of the values in oidc auth result is null:\n'
      'is id token null? $idTokenNull\n'
      'is access token null: $accessTokenNull\n'
      'is token expiration null: $expirationNull\n'
      'is refresh token null: $refreshTokenNull\n';
}

/// Web OIDC implementation using HTTP-based token refresh.
///
/// On web, the initial authorization redirects the browser to the OIDC provider,
/// then back to the app with tokens in the URL. Token refresh is handled via
/// direct HTTP POST to the token endpoint.
class OidcWebAuthInteractor extends OidcAuthInteractorBase {
  OidcWebAuthInteractor(
    SecureSsoStorage ssoStorage,
    SecureTokenStorage tokenStorage,
    Duration tokenExpirationBuffer,
  ) : super(
          ssoStorage: ssoStorage,
          tokenStorage: tokenStorage,
          tokenExpirationBuffer: tokenExpirationBuffer,
        );

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    debugPrint('Setting sso config');
    await setSsoConfig(config);
    await launchUrl(config.loginUrl, webOnlyWindowName: '_self');
    // On web, this returns immediately with empty values.
    // The actual tokens come via URL redirect handled elsewhere.
    return OidcAuthTokenResponse(
      idToken: '',
      accessToken: '',
      accessTokenExpiration: DateTime.now(),
      refreshToken: '',
    );
  }

  @override
  Future<OidcAuthTokenResponse?> refreshAccessToken(SsoConfig config) async {
    debugPrint('Refreshing token.');
    final refreshToken = await tokenStorage.getOidcRefreshToken();
    debugPrint('Refresh token retrieved.');
    if (refreshToken == null) {
      debugPrint('Refreshing token null.');
      return null;
    }
    final response = await _refreshAccessToken(config, refreshToken);
    await tokenStorage.setOidcAuthTokenResponse(response);
    debugPrint('Set new token response after refreshing token.');
    return response;
  }

  Future<OidcAuthTokenResponse> _refreshAccessToken(
    SsoConfig config,
    String refreshToken,
  ) async {
    final url = Uri.parse(config.tokenEndpoint);
    final headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    final body =
        'grant_type=refresh_token&refresh_token=$refreshToken&client_id=${config.clientId}';

    try {
      final response = await http.post(url, headers: headers, body: body);

      if (response.statusCode == 200) {
        debugPrint('Token refresh successful');
        final newTokens = json.decode(response.body);

        final expiration = DateTime.fromMillisecondsSinceEpoch(
          DateTime.now().millisecondsSinceEpoch +
              ((newTokens['expires_in'] ?? 0) as int) * 1000,
        );
        debugPrint('New expiration: $expiration');

        return OidcAuthTokenResponse(
          idToken: '',
          accessToken: newTokens['access_token'] as String,
          accessTokenExpiration: expiration,
          refreshToken: newTokens['refresh_token'] as String,
        );
      } else {
        debugPrint('Failed to refresh token: ${response.statusCode}');
        debugPrint('Response body: ${response.body}');
      }
    } catch (e) {
      debugPrint('An error occurred: $e');
      rethrow;
    }
    debugPrint('Refreshing token for ${config.id} with $refreshToken.');
    throw Exception('Refreshing token failed');
  }

  @override
  Future<void> logout(SsoConfig config) async {
    final refreshToken = await tokenStorage.getOidcRefreshToken();
    final url = Uri.parse('${config.endpoint}/protocol/openid-connect/logout');
    final headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    final body = 'refresh_token=$refreshToken&client_id=${config.clientId}';

    try {
      final response = await http.post(url, headers: headers, body: body);

      if (response.statusCode == 204) {
        debugPrint('Session logout successful');
        await tokenStorage.deleteOidcAuthTokenResponse();
        await ssoStorage.deleteSsoConfig();
        return;
      } else {
        debugPrint('Failed to logout of session: ${response.statusCode}');
        debugPrint('Response body: ${response.body}');
      }
    } catch (e) {
      debugPrint('An error occurred: $e');
      rethrow;
    }
    throw Exception('Session logout failed');
  }
}
