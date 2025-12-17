import 'dart:convert';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/oidc_token_application_mixin.dart';
import 'package:soliplex/core/auth/secure_sso_storage.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/sso_config.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/auth/web_auth_pending_storage.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/http_config.dart';
import 'package:soliplex/core/utils/url_builder.dart';
import 'package:url_launcher/url_launcher.dart';

// Re-export the base class and interface for external use
export 'oidc_token_application_mixin.dart'
    show OidcAuthInteractor, OidcAuthInteractorBase, SsoConfigNotSetException;

/// Mobile/Desktop OIDC implementation using flutter_appauth.
///
/// Uses the native OAuth flow via ASWebAuthenticationSession (iOS/macOS)
/// or Chrome Custom Tabs (Android).
class OidcMobileAuthInteractor extends OidcAuthInteractorBase {
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
  final FlutterAppAuth _appAuth;

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    String serverId,
    SsoConfig config,
  ) async {
    DebugLog.service(
      'OidcMobileAuthInteractor: Signing in at ${DateTime.now()}',
    );
    final response = await _authorizeAndExchangeCode(config);
    await tokenStorage.setOidcAuthTokenResponse(response);
    DebugLog.service(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'OidcMobileAuthInteractor: Expiration timestamp: ${response.accessTokenExpiration}',
    );
    await setSsoConfig(serverId, config);
    return response;
  }

  Future<OidcAuthTokenResponse> _authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    DebugLog.service('OidcMobileAuthInteractor: calling flutter_appauth...');
    DebugLog.service('  clientId: ${config.clientId}');
    DebugLog.service('  redirectUrl: ${config.redirectUrl}');
    DebugLog.service('  issuer: ${config.endpoint}');
    DebugLog.service('  scopes: ${config.scopes}');

    try {
      final result = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          config.clientId,
          config.redirectUrl,
          scopes: config.scopes,
          issuer: config.endpoint,
        ),
      );

      DebugLog.service(
        'OidcMobileAuthInteractor: got result from flutter_appauth',
      );
      DebugLog.service('  idToken null? ${result.idToken == null}');
      DebugLog.service('  accessToken null? ${result.accessToken == null}');
      DebugLog.service(
        '  expiration null? ${result.accessTokenExpirationDateTime == null}',
      );
      DebugLog.service('  refreshToken null? ${result.refreshToken == null}');

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
    } on Object catch (e, stack) {
      DebugLog.error('OidcMobileAuthInteractor: EXCEPTION: $e');
      DebugLog.error('OidcMobileAuthInteractor: Stack: $stack');
      rethrow;
    }
  }

  @override
  Future<OidcAuthTokenResponse?> refreshAccessToken(
    String serverId,
    SsoConfig config,
  ) async {
    DebugLog.service(
      'OidcMobileAuthInteractor: Refreshing token for $serverId.',
    );
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
  Future<void> logout(String serverId, SsoConfig config) async {
    final tokens = await tokenStorage.getOidcAuthTokenResponse();

    await _appAuth.endSession(
      EndSessionRequest(
        idTokenHint: tokens?.idToken,
        postLogoutRedirectUrl: config.redirectUrl,
        issuer: config.endpoint,
      ),
    );
    await tokenStorage.deleteOidcAuthTokenResponse();
    await ssoStorage.deleteSsoConfig(serverId);
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
  OidcTokenValidationException({
    required this.idTokenNull,
    required this.accessTokenNull,
    required this.expirationNull,
    required this.refreshTokenNull,
  });
  final bool idTokenNull;
  final bool accessTokenNull;
  final bool expirationNull;
  final bool refreshTokenNull;

  @override
  String toString() =>
      'At least one of the values in oidc auth result is null:\n'
      'is id token null? $idTokenNull\n'
      'is access token null: $accessTokenNull\n'
      'is token expiration null: $expirationNull\n'
      'is refresh token null: $refreshTokenNull\n';
}

/// Web OIDC implementation using backend-mediated OAuth flow.
///
/// Web authentication uses a backend-mediated flow to avoid CORS issues:
/// 1. **Redirect Out**: Redirect to backend `/api/login/{system}` endpoint
/// 2. **Backend Handles OAuth**: Backend redirects to OIDC provider, exchanges
///    code for tokens
/// 3. **Callback**: Backend redirects to app `/auth/callback` with tokens in URL
///
/// The two phases happen in different app instances (page reloads between
/// them).
///
/// Token refresh is handled via direct HTTP POST to the token endpoint.
///
/// Optionally accepts NetworkInspector for traffic observability.
class OidcWebAuthInteractor extends OidcAuthInteractorBase {
  OidcWebAuthInteractor(
    SecureSsoStorage ssoStorage,
    SecureTokenStorage tokenStorage,
    Duration tokenExpirationBuffer, {
    NetworkInspector? inspector,
    WebAuthPendingStorage? pendingStorage,
  }) : _inspector = inspector,
       _pendingStorage = pendingStorage,
       super(
         ssoStorage: ssoStorage,
         tokenStorage: tokenStorage,
         tokenExpirationBuffer: tokenExpirationBuffer,
       );
  final NetworkInspector? _inspector;
  final WebAuthPendingStorage? _pendingStorage;

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    String serverId,
    SsoConfig config,
  ) async {
    DebugLog.auth(
      'OidcWebAuthInteractor: Starting backend-mediated auth for $serverId',
    );

    // Validate we have the server base URL for backend-mediated flow
    final serverBaseUrl = config.serverBaseUrl;
    if (serverBaseUrl == null) {
      throw StateError(
        'serverBaseUrl is required for web authentication. '
        'Ensure AuthManager passes the server URL in SsoConfig.',
      );
    }

    // Store SSO config for use after callback
    await setSsoConfig(serverId, config);

    // Store pending auth for callback (simplified - backend handles PKCE)
    if (_pendingStorage != null) {
      await _pendingStorage.savePendingAuth(
        PendingWebAuth(
          serverId: serverId,
          providerId: config.id,
          codeVerifier: '', // Not needed - backend handles PKCE
          state: '', // Not needed - backend handles state
          tokenEndpoint: config.tokenEndpoint,
          clientId: config.clientId,
          redirectUrl: config.redirectUrl,
          createdAt: DateTime.now(),
        ),
      );
    }

    // Build backend-mediated auth URL
    final urlBuilder = UrlBuilder(serverBaseUrl);
    final authUrl = urlBuilder.loginWithProvider(
      config.id,
      returnTo: config.redirectUrl,
    );
    DebugLog.auth(
      'OidcWebAuthInteractor: Redirecting to backend: $authUrl',
    );

    // Launch auth URL in same window (replaces current page)
    await launchUrl(authUrl, webOnlyWindowName: '_self');

    // Signal that redirect is happening - the app will reload at /auth/callback
    // with tokens in URL params (backend handles the OAuth exchange)
    throw OidcWebRedirectException(serverId);
  }

  @override
  Future<OidcAuthTokenResponse?> refreshAccessToken(
    String serverId,
    SsoConfig config,
  ) async {
    DebugLog.service('OidcWebAuthInteractor: Refreshing token for $serverId.');
    final refreshToken = await tokenStorage.getOidcRefreshToken();
    DebugLog.service('OidcWebAuthInteractor: Refresh token retrieved.');
    if (refreshToken == null) {
      DebugLog.service('OidcWebAuthInteractor: Refreshing token null.');
      return null;
    }
    final response = await _refreshAccessToken(config, refreshToken);
    await tokenStorage.setOidcAuthTokenResponse(response);
    DebugLog.service(
      'OidcWebAuthInteractor: Set new token response after refreshing token.',
    );
    return response;
  }

  Future<OidcAuthTokenResponse> _refreshAccessToken(
    SsoConfig config,
    String refreshToken,
  ) async {
    final url = Uri.parse(config.tokenEndpoint);
    final headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    final body =
        // ignore: lines_longer_than_80_chars (auto-documented)
        'grant_type=refresh_token&refresh_token=$refreshToken&client_id=${config.clientId}';

    // Record request for Network Inspector
    final requestId = _inspector?.recordRequest(
      method: 'POST',
      uri: url,
      headers: headers,
      body: body,
    );

    try {
      final response = await http
          .post(url, headers: headers, body: body)
          .timeout(HttpConfig.oidcTimeout);

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
        DebugLog.service('OidcWebAuthInteractor: Token refresh successful');
        final newTokens = json.decode(response.body);

        final expiration = DateTime.fromMillisecondsSinceEpoch(
          DateTime.now().millisecondsSinceEpoch +
              ((newTokens['expires_in'] ?? 0) as int) * 1000,
        );
        DebugLog.service('OidcWebAuthInteractor: New expiration: $expiration');

        return OidcAuthTokenResponse(
          idToken: '',
          accessToken: newTokens['access_token'] as String,
          accessTokenExpiration: expiration,
          refreshToken: newTokens['refresh_token'] as String,
        );
      } else {
        DebugLog.error(
          // ignore: lines_longer_than_80_chars (auto-documented)
          'OidcWebAuthInteractor: Failed to refresh token: ${response.statusCode}',
        );
        DebugLog.error(
          'OidcWebAuthInteractor: Response body: ${response.body}',
        );
      }
    } on Object catch (e) {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      DebugLog.error('OidcWebAuthInteractor: An error occurred: $e');
      rethrow;
    }
    DebugLog.error(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'OidcWebAuthInteractor: Refreshing token for ${config.id} with $refreshToken.',
    );
    throw Exception('Refreshing token failed');
  }

  @override
  Future<void> logout(String serverId, SsoConfig config) async {
    DebugLog.service('OidcWebAuthInteractor: Logging out via redirect');

    // Get tokens to retrieve ID token for hint
    final tokens = await tokenStorage.getOidcAuthTokenResponse();

    // Clear local storage immediately
    await tokenStorage.deleteOidcAuthTokenResponse();
    await ssoStorage.deleteSsoConfig(serverId);

    // Build logout URL with redirect
    // We use the front-channel logout (redirect) to ensure cookies are cleared
    // at IdP
    final logoutUri = Uri.parse(
      '${config.endpoint}/protocol/openid-connect/logout',
    ).replace(
      queryParameters: {
        'post_logout_redirect_uri': config.redirectUrl,
        'client_id': config.clientId,
        if (tokens != null && tokens.idToken.isNotEmpty)
          'id_token_hint': tokens.idToken,
      },
    );

    DebugLog.service(
      'OidcWebAuthInteractor: Redirecting to logout: $logoutUri',
    );

    // Launch URL in self to redirect browser
    await launchUrl(logoutUri, webOnlyWindowName: '_self');

    // Signal that redirect is happening
    throw OidcWebRedirectException(serverId);
  }
}
