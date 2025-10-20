import 'dart:convert';
import 'dart:developer';

import 'package:flutter/foundation.dart';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import 'oidc_auth_token_response.dart';
import 'secure_sso_storage.dart';
import 'secure_token_storage.dart';
import 'sso_config.dart';

abstract class OidcAuthInteractor {
  bool useAuth = false;
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(SsoConfig config);
  Future<OidcAuthTokenResponse?> refreshAccessToken(SsoConfig config);
  Future<OidcAuthTokenResponse?> getTokenResponse();
  Future<String?> getRefreshToken();
  Future<SsoConfig?> getSsoConfig();
  Future<void> setSsoConfig(SsoConfig config);
  bool isTokenExpiring(OidcAuthTokenResponse? tokenResponse);
  Future<void> applyToRequest(http.BaseRequest request);
  Future<void> applyToHeader(Map<String, String> headers);
  Future<void> logout(SsoConfig config);
}

class OidcMobileAuthInteractor implements OidcAuthInteractor {
  final FlutterAppAuth _appAuth;
  final SecureSsoStorage _ssoStorage;
  final SecureTokenStorage _tokenStorage;
  final Duration _tokenExpirationBuffer;

  OidcMobileAuthInteractor(
    this._appAuth,
    this._ssoStorage,
    this._tokenStorage,
    this._tokenExpirationBuffer,
  );

  @override
  bool useAuth = false;

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    debugPrint('Signing in at ${DateTime.now()}');
    final response = await _authorizeAndExchangeCode(config);
    await _tokenStorage.setOidcAuthTokenResponse(response);
    debugPrint('Expiration timestamp: ${response.accessTokenExpiration}');
    await setSsoConfig(config);
    return response;
  }

  Future<OidcAuthTokenResponse> _authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    final result = await _appAuth.authorizeAndExchangeCode(
      AuthorizationTokenRequest(
        config.clientId,
        config.redirectUrl,
        scopes: config.scopes,
        issuer: config.endpoint,
        externalUserAgent: ExternalUserAgent.asWebAuthenticationSession,
      ),
    );

    if (result.idToken == null ||
        result.accessToken == null ||
        result.accessTokenExpirationDateTime == null ||
        result.refreshToken == null) {
      throw Exception(
        'At least one of the values in oidc auth result is null:\n'
        'is id token null? ${result.idToken == null}\n'
        'is access token null: ${result.accessToken == null}\n'
        'is token expiration null: ${result.accessTokenExpirationDateTime == null}\n'
        'is refresh token null: ${result.refreshToken == null}\n',
      );
    }

    return OidcAuthTokenResponse(
      idToken: result.idToken!,
      accessToken: result.accessToken!,
      accessTokenExpiration: result.accessTokenExpirationDateTime!,
      refreshToken: result.refreshToken!,
    );
  }

  @override
  Future<OidcAuthTokenResponse?> refreshAccessToken(SsoConfig config) async {
    debugPrint('Refreshing token.');
    final refreshToken = await _tokenStorage.getOidcRefreshToken();
    if (refreshToken == null) {
      return null;
    }
    final response = await _refreshAccessToken(config, refreshToken);
    await _tokenStorage.setOidcAuthTokenResponse(response);
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

    if (result.idToken == null ||
        result.accessToken == null ||
        result.accessTokenExpirationDateTime == null ||
        result.refreshToken == null) {
      throw Exception(
        'At least one of the values in oidc auth result is null:\n'
        'is id token null? ${result.idToken == null}\n'
        'is access token null: ${result.accessToken == null}\n'
        'is token expiration null: ${result.accessTokenExpirationDateTime == null}\n'
        'is refresh token null: ${result.refreshToken == null}\n',
      );
    }

    return OidcAuthTokenResponse(
      idToken: result.idToken!,
      accessToken: result.accessToken!,
      accessTokenExpiration: result.accessTokenExpirationDateTime!,
      refreshToken: result.refreshToken!,
    );
  }

  @override
  Future<OidcAuthTokenResponse?> getTokenResponse() =>
      _tokenStorage.getOidcAuthTokenResponse();
  @override
  Future<String?> getRefreshToken() => _tokenStorage.getOidcRefreshToken();
  @override
  Future<SsoConfig?> getSsoConfig() => _ssoStorage.getSsoConfig();
  @override
  Future<void> setSsoConfig(SsoConfig config) =>
      _ssoStorage.setSsoConfig(config);

  // Check if token is expiring within buffered time from now
  @override
  bool isTokenExpiring(OidcAuthTokenResponse? tokenResponse) {
    if (tokenResponse == null ||
        tokenResponse.accessTokenExpiration.isBefore(
          DateTime.now().add(_tokenExpirationBuffer),
        )) {
      return true;
    }
    return false;
  }

  @override
  Future<void> applyToRequest(http.BaseRequest request) async {
    if (!useAuth) {
      debugPrint('Request to apply token to request with disabled auth');
      return;
    }
    final currentToken = await getTokenResponse();
    final expiring = isTokenExpiring(currentToken);
    if (expiring) {
      debugPrint('Token expired.');
      final ssoConfig = await getSsoConfig();

      if (ssoConfig == null) {
        throw Exception(
          'Single sign on config has not been selected. '
          'Please try again after selecting a SSO configuration.',
        );
      }

      late final OidcAuthTokenResponse? refreshResponse;
      try {
        refreshResponse = await refreshAccessToken(ssoConfig);
      } catch (e) {
        refreshResponse = null;
      }
      if (refreshResponse == null) {
        debugPrint('Refresh not successful');
        final newTokenResponse = await authorizeAndExchangeCode(ssoConfig);
        debugPrint(
          'Signed in again. New expiration: ${newTokenResponse.accessTokenExpiration}',
        );
        request.headers['authorization'] =
            'Bearer ${newTokenResponse.accessToken}';
      } else {
        debugPrint('Refresh successful');
        debugPrint(
          'New token expiration: ${refreshResponse.accessTokenExpiration}',
        );
        request.headers['authorization'] =
            'Bearer ${refreshResponse.accessToken}';
      }
    } else {
      debugPrint('Token not expired.');
      debugPrint(
        'Current token expiration: ${currentToken!.accessTokenExpiration}',
      );
      request.headers['authorization'] = 'Bearer ${currentToken.accessToken}';
    }
  }

  @override
  Future<void> applyToHeader(Map<String, String> headers) async {
    if (!useAuth) {
      debugPrint('Request to apply token to header with disabled auth');
      return;
    }
    final currentToken = await getTokenResponse();
    final expired = isTokenExpiring(currentToken);
    if (expired) {
      debugPrint('Token expired.');
      final ssoConfig = await getSsoConfig();

      if (ssoConfig == null) {
        throw Exception(
          'Single sign on config has not been selected. '
          'Please try again after selecting a SSO configuration.',
        );
      }

      late final OidcAuthTokenResponse? refreshResponse;
      try {
        refreshResponse = await refreshAccessToken(ssoConfig);
      } catch (e) {
        refreshResponse = null;
      }
      if (refreshResponse == null) {
        debugPrint('Refresh not successful');
        final newTokenResponse = await authorizeAndExchangeCode(ssoConfig);
        debugPrint(
          'Signed in again. New expiration: ${newTokenResponse.accessTokenExpiration}',
        );
        headers['authorization'] = 'Bearer ${newTokenResponse.accessToken}';
      } else {
        debugPrint('Refresh successful');
        debugPrint(
          'New token expiration: ${refreshResponse.accessTokenExpiration}',
        );
        headers['authorization'] = 'Bearer ${refreshResponse.accessToken}';
      }
    } else {
      debugPrint('Token not expired.');
      debugPrint(
        'Current token expiration: ${currentToken!.accessTokenExpiration}',
      );
      headers['authorization'] = 'Bearer ${currentToken.accessToken}';
    }
  }

  @override
  Future<void> logout(SsoConfig config) async {
    final tokens = await _tokenStorage.getOidcAuthTokenResponse();

    await _appAuth.endSession(
      EndSessionRequest(
        idTokenHint: tokens?.idToken,
        postLogoutRedirectUrl: config.redirectUrl,
        externalUserAgent: ExternalUserAgent.asWebAuthenticationSession,
        issuer: config.endpoint,
      ),
    );
    await _tokenStorage.deleteOidcAuthTokenResponse();
    await _ssoStorage.deleteSsoConfig();
  }
}

class OidcWebAuthInteractor implements OidcAuthInteractor {
  final SecureSsoStorage _ssoStorage;
  final SecureTokenStorage _tokenStorage;
  final Duration _tokenExpirationBuffer;

  OidcWebAuthInteractor(
    this._ssoStorage,
    this._tokenStorage,
    this._tokenExpirationBuffer,
  );

  @override
  bool useAuth = false;

  @override
  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    SsoConfig config,
  ) async {
    debugPrint('Setting sso config');
    await setSsoConfig(config);
    await launchUrl(config.loginUrl, webOnlyWindowName: '_self');
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
    final refreshToken = await _tokenStorage.getOidcRefreshToken();
    debugPrint('Refresh token retrieved.');
    if (refreshToken == null) {
      debugPrint('Refreshing token null.');
      return null;
    }
    final response = await _refreshAccessToken(config, refreshToken);
    await _tokenStorage.setOidcAuthTokenResponse(response);
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
        // Token refresh successful
        debugPrint('Token refresh successful');
        final newTokens = json.decode(response.body);

        debugPrint(
          'New expiration: ${DateTime.fromMillisecondsSinceEpoch(DateTime.now().millisecondsSinceEpoch + ((newTokens['expires_in'] ?? 0) as int) * 1000)}',
        );

        return OidcAuthTokenResponse(
          idToken: '',
          accessToken: newTokens['access_token'],
          accessTokenExpiration: DateTime.fromMillisecondsSinceEpoch(
            DateTime.now().millisecondsSinceEpoch +
                ((newTokens['expires_in'] ?? 0) as int) * 1000,
          ),
          refreshToken: newTokens['refresh_token'],
        );
      } else {
        // Handle errors
        debugPrint('Failed to refresh token: ${response.statusCode}');
        debugPrint('Response body: ${response.body}');
      }
    } catch (e) {
      // Handle network or other errors
      debugPrint('An error occurred: $e');
      rethrow;
    }
    debugPrint('Refreshing token for ${config.id} with $refreshToken.');
    throw Exception('Refreshing token failed');
  }

  @override
  Future<OidcAuthTokenResponse?> getTokenResponse() =>
      _tokenStorage.getOidcAuthTokenResponse();
  @override
  Future<String?> getRefreshToken() => _tokenStorage.getOidcRefreshToken();
  @override
  Future<SsoConfig?> getSsoConfig() => _ssoStorage.getSsoConfig();
  @override
  Future<void> setSsoConfig(SsoConfig config) =>
      _ssoStorage.setSsoConfig(config);

  // Check if token is expiring within buffered time from now
  @override
  bool isTokenExpiring(OidcAuthTokenResponse? tokenResponse) {
    if (tokenResponse == null ||
        tokenResponse.accessTokenExpiration.isBefore(
          DateTime.now().add(_tokenExpirationBuffer),
        )) {
      return true;
    }
    return false;
  }

  @override
  Future<void> applyToRequest(http.BaseRequest request) async {
    if (!useAuth) {
      debugPrint('Request to apply token to request with disabled auth');
      return;
    }
    debugPrint('Applying token to request');
    final currentToken = await getTokenResponse();
    final expiring = isTokenExpiring(currentToken);
    if (expiring) {
      debugPrint('Token expired.');
      final ssoConfig = await getSsoConfig();

      if (ssoConfig == null) {
        debugPrint('Sso config has not been set.');
        throw Exception(
          'Single sign on config has not been selected. '
          'Please try again after selecting a SSO configuration.',
        );
      }

      late final OidcAuthTokenResponse? refreshResponse;
      try {
        debugPrint('Refreshing token');
        refreshResponse = await refreshAccessToken(ssoConfig);
      } catch (e) {
        debugPrint('Refresh response null');
        refreshResponse = null;
      }
      if (refreshResponse == null) {
        debugPrint('Refresh not successful');
        final newTokenResponse = await authorizeAndExchangeCode(ssoConfig);
        debugPrint(
          'Signed in again. New expiration: ${newTokenResponse.accessTokenExpiration}',
        );
        debugPrint('current time: ${DateTime.now()}');
        request.headers['authorization'] =
            'Bearer ${newTokenResponse.accessToken}';
      } else {
        debugPrint('Refresh successful');
        debugPrint(
          'New token expiration: ${refreshResponse.accessTokenExpiration}',
        );
        request.headers['authorization'] =
            'Bearer ${refreshResponse.accessToken}';
      }
    } else {
      debugPrint('Token not expired.');
      debugPrint(
        'Current token expiration: ${currentToken!.accessTokenExpiration}',
      );
      request.headers['authorization'] = 'Bearer ${currentToken.accessToken}';
    }
  }

  @override
  Future<void> applyToHeader(Map<String, String> headers) async {
    if (!useAuth) {
      debugPrint('Request to apply token to header with disabled auth');
      return;
    }
    final currentToken = await getTokenResponse();
    final expired = isTokenExpiring(currentToken);
    if (expired) {
      debugPrint('Token expired.');
      final ssoConfig = await getSsoConfig();

      if (ssoConfig == null) {
        throw Exception(
          'Single sign on config has not been selected. '
          'Please try again after selecting a SSO configuration.',
        );
      }

      late final OidcAuthTokenResponse? refreshResponse;
      try {
        refreshResponse = await refreshAccessToken(ssoConfig);
      } catch (e) {
        refreshResponse = null;
      }
      if (refreshResponse == null) {
        debugPrint('Refresh not successful');
        final newTokenResponse = await authorizeAndExchangeCode(ssoConfig);
        debugPrint(
          'Signed in again. New expiration: ${newTokenResponse.accessTokenExpiration}',
        );
        headers['authorization'] = 'Bearer ${newTokenResponse.accessToken}';
      } else {
        debugPrint('Refresh successful');
        debugPrint(
          'New token expiration: ${refreshResponse.accessTokenExpiration}',
        );
        headers['authorization'] = 'Bearer ${refreshResponse.accessToken}';
      }
    } else {
      debugPrint('Token not expired.');
      debugPrint(
        'Current token expiration: ${currentToken!.accessTokenExpiration}',
      );
      headers['authorization'] = 'Bearer ${currentToken.accessToken}';
    }
  }

  @override
  Future<void> logout(SsoConfig config) async {
    final refreshToken = await _tokenStorage.getOidcRefreshToken();
    final url = Uri.parse('${config.endpoint}/protocol/openid-connect/logout');
    final headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    final body = 'refresh_token=$refreshToken&client_id=${config.clientId}';

    try {
      final response = await http.post(url, headers: headers, body: body);

      if (response.statusCode == 204) {
        // Logout successful
        debugPrint('Session logout successful');

        await _tokenStorage.deleteOidcAuthTokenResponse();
        await _ssoStorage.deleteSsoConfig();

        return;
      } else {
        // Handle errors
        debugPrint('Failed to logout of session: ${response.statusCode}');
        debugPrint('Response body: ${response.body}');
      }
    } catch (e) {
      // Handle network or other errors
      debugPrint('An error occurred: $e');
      rethrow;
    }
    throw Exception('Session logout failed');
  }
}
