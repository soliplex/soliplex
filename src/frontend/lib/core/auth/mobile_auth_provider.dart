import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';

/// Result of a token refresh attempt.
sealed class RefreshResult {
  const RefreshResult();
}

/// Token refresh succeeded.
final class RefreshSuccess extends RefreshResult {
  const RefreshSuccess(this.token);
  final AuthToken token;
}

/// Token refresh was rejected by the server.
final class RefreshRejected extends RefreshResult {
  const RefreshRejected(this.exception);
  final Exception exception;
}

/// AuthProvider implementation for mobile platforms using PKCE flow.
///
/// Uses flutter_appauth for native OAuth handling on iOS, Android, and macOS.
/// Tokens are persisted via the injected [TokenStorage].
class MobileAuthProvider implements AuthProvider {
  /// Creates a mobile auth provider.
  ///
  /// The [redirectScheme] is used to construct the redirect URI for OAuth
  /// callbacks. The path `/oauthredirect` is appended automatically.
  /// Platform configurations (Info.plist, AndroidManifest.xml) must register
  /// this scheme.
  MobileAuthProvider({
    required TokenStorage tokenStorage,
    required FlutterAppAuth appAuth,
    required http.Client httpClient,
    String redirectScheme = 'com.soliplex.app',
  })  : _tokenStorage = tokenStorage,
        _appAuth = appAuth,
        _httpClient = httpClient,
        _redirectUri = '$redirectScheme:/oauthredirect';

  final TokenStorage _tokenStorage;
  final FlutterAppAuth _appAuth;
  final http.Client _httpClient;
  final String _redirectUri;

  /// Cached session data for logout operations.
  ///
  /// Populated during [login], cleared during [logout]. Used to locate the
  /// end-session endpoint when logging out.
  final Map<String, SsoConfig> _sessionCache = {};

  @override
  Future<AuthResult> getValidToken(String serverId, SsoConfig config) async {
    final result = await _tokenStorage.read(serverId);

    switch (result) {
      case TokenNotFound():
        return const NoToken();
      case TokenFound(:final token):
        if (!token.needsRefresh) {
          return Authenticated(token: token);
        }

        if (!token.canRefresh) {
          await _tokenStorage.delete(serverId);
          return const TokenExpired();
        }

        switch (await _attemptRefresh(token, config)) {
          case RefreshSuccess(:final token):
            await _tokenStorage.write(serverId, token);
            return Authenticated(token: token);
          case RefreshRejected(:final exception):
            await _tokenStorage.delete(serverId);
            return RefreshFailed(cause: exception.toString());
        }
    }
  }

  @override
  Future<AuthToken> login(String serverId, SsoConfig config) async {
    _sessionCache[serverId] = config;

    final AuthorizationTokenResponse response;
    try {
      response = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          config.clientId,
          _redirectUri,
          serviceConfiguration: AuthorizationServiceConfiguration(
            authorizationEndpoint: config.authorizationEndpoint,
            tokenEndpoint: config.tokenEndpoint,
            endSessionEndpoint: config.endSessionEndpoint,
          ),
          scopes: config.scope.split(' '),
        ),
      );
    } on FlutterAppAuthUserCancelledException {
      throw const AuthErrorCancelled();
    } on FlutterAppAuthPlatformException catch (e, st) {
      throw AuthErrorNetwork(
        message: 'Authorization request failed: ${e.message}',
        originalError: e,
        stackTrace: st,
      );
    } on Exception catch (e, st) {
      throw AuthErrorNetwork(
        message: 'Authorization request failed: $e',
        originalError: e,
        stackTrace: st,
      );
    }

    final token = _tokenFromResponse(response);
    await _tokenStorage.write(serverId, token);
    return token;
  }

  @override
  Future<void> logout(String serverId) async {
    final result = await _tokenStorage.read(serverId);

    if (result case TokenFound(:final token)) {
      final config = _sessionCache[serverId];

      if (config?.endSessionEndpoint != null && token.idToken != null) {
        try {
          await _appAuth.endSession(
            EndSessionRequest(
              idTokenHint: token.idToken,
              postLogoutRedirectUrl: _redirectUri,
              serviceConfiguration: AuthorizationServiceConfiguration(
                authorizationEndpoint: config!.authorizationEndpoint,
                tokenEndpoint: config.tokenEndpoint,
                endSessionEndpoint: config.endSessionEndpoint,
              ),
            ),
          );
        } on Exception catch (e) {
          // Remote end-session failed; local cleanup will proceed.
          debugPrint('End session failed for $serverId: $e');
        }
      }
    }

    await _tokenStorage.delete(serverId);
    _sessionCache.remove(serverId);
  }

  @override
  Future<UserInfo> getCurrentUser(String serverId, SsoConfig config) async {
    final result = await _tokenStorage.read(serverId);

    final token = switch (result) {
      TokenFound(:final token) => token,
      TokenNotFound() => throw const AuthErrorNotAuthenticated(),
    };

    if (config.userInfoEndpoint == null) {
      throw const AuthErrorConfiguration(
        message: 'No userinfo endpoint configured',
      );
    }

    final http.Response response;
    try {
      response = await _httpClient.get(
        Uri.parse(config.userInfoEndpoint!),
        headers: {'Authorization': 'Bearer ${token.accessToken}'},
      );
    } on Exception catch (e, st) {
      throw AuthErrorNetwork(
        message: 'Failed to fetch user info: $e',
        originalError: e,
        stackTrace: st,
      );
    }

    if (response.statusCode != 200) {
      throw AuthErrorServer(
        message: 'User info request failed',
        statusCode: response.statusCode,
        body: response.body,
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return UserInfo.fromJson(_normalizeUserInfoResponse(json));
  }

  Future<RefreshResult> _attemptRefresh(
    AuthToken token,
    SsoConfig config,
  ) async {
    try {
      final response = await _appAuth.token(
        TokenRequest(
          config.clientId,
          _redirectUri,
          refreshToken: token.refreshToken,
          serviceConfiguration: AuthorizationServiceConfiguration(
            authorizationEndpoint: config.authorizationEndpoint,
            tokenEndpoint: config.tokenEndpoint,
            endSessionEndpoint: config.endSessionEndpoint,
          ),
        ),
      );

      return RefreshSuccess(_tokenFromResponse(response));
    } on Exception catch (e) {
      return RefreshRejected(e);
    }
  }

  AuthToken _tokenFromResponse(TokenResponse response) {
    final accessToken = response.accessToken;
    if (accessToken == null) {
      throw const AuthErrorConfiguration(
        message: 'No access token in authorization response',
      );
    }

    final expiresAt = response.accessTokenExpirationDateTime;
    if (expiresAt == null) {
      throw const AuthErrorConfiguration(
        message: 'No expiration time in authorization response',
      );
    }

    return AuthToken(
      accessToken: accessToken,
      refreshToken: response.refreshToken,
      expiresAt: expiresAt.toUtc(),
      idToken: response.idToken,
    );
  }

  /// Normalizes OIDC userinfo response to match [UserInfo.fromJson].
  ///
  /// Different OIDC providers use different claim names:
  /// - Standard: `sub`, `email`, `name`
  /// - Some use: `preferred_username`, `given_name` + `family_name`
  Map<String, dynamic> _normalizeUserInfoResponse(Map<String, dynamic> json) {
    return {
      'id': json['sub'] as String? ?? json['id'] as String? ?? '',
      if (json['email'] != null) 'email': json['email'],
      if (json['name'] != null)
        'name': json['name']
      else if (json['given_name'] != null || json['family_name'] != null)
        'name': [
          json['given_name'] as String?,
          json['family_name'] as String?,
        ].whereType<String>().join(' ').trim(),
    };
  }
}
