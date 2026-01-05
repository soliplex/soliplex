import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';

/// Result of a successful authentication.
class AuthResult {
  const AuthResult({
    required this.accessToken,
    this.refreshToken,
    this.idToken,
    this.expiresAt,
  });

  final String accessToken;
  final String? refreshToken;
  final String? idToken;
  final DateTime? expiresAt;
}

/// Authentication exception.
class AuthException implements Exception {
  const AuthException(this.message);

  final String message;

  @override
  String toString() => 'AuthException: $message';
}

/// Thrown when refresh token is expired or revoked.
///
/// Callers should clear auth state and redirect to login.
class RefreshExpiredException implements Exception {
  const RefreshExpiredException([this.message = 'Refresh token expired']);

  final String message;

  @override
  String toString() => 'RefreshExpiredException: $message';
}

const _redirectUri = 'ai.soliplex.client://callback';

/// Authenticate using OIDC via flutter_appauth.
///
/// Opens system browser to IdP login page, handles PKCE automatically.
/// The [appAuth] parameter allows injection for testing.
Future<AuthResult> authenticate(
  OidcIssuer issuer, {
  FlutterAppAuth appAuth = const FlutterAppAuth(),
}) async {
  try {
    final result = await appAuth.authorizeAndExchangeCode(
      AuthorizationTokenRequest(
        issuer.clientId,
        _redirectUri,
        discoveryUrl: issuer.discoveryUrl,
        scopes: issuer.scope.split(' '),
        // Use ephemeral session to avoid "wants to sign in" prompts
        externalUserAgent:
            ExternalUserAgent.ephemeralAsWebAuthenticationSession,
      ),
    );

    return AuthResult(
      accessToken: result.accessToken!,
      refreshToken: result.refreshToken,
      idToken: result.idToken,
      expiresAt: result.accessTokenExpirationDateTime,
    );
  } on Exception catch (e) {
    debugPrint('Authentication failed: $e');
    throw const AuthException('Authentication failed. Please try again.');
  }
}

/// End the OIDC session at the IdP.
///
/// Opens system browser to IdP's end_session_endpoint.
/// The [appAuth] parameter allows injection for testing.
Future<void> endSession({
  required String discoveryUrl,
  required String idToken,
  FlutterAppAuth appAuth = const FlutterAppAuth(),
}) async {
  try {
    await appAuth.endSession(
      EndSessionRequest(
        idTokenHint: idToken,
        discoveryUrl: discoveryUrl,
        postLogoutRedirectUrl: _redirectUri,
      ),
    );
  } on Exception catch (e) {
    // endSession failure shouldn't prevent local logout
    debugPrint('IdP session termination failed (local logout proceeds): $e');
  }
}

/// Fetch the token endpoint URL from an OIDC discovery document.
///
/// Fetches the discovery document at [discoveryUrl] and extracts the
/// `token_endpoint` field. Validates that the token endpoint host matches
/// the discovery URL host (SSRF prevention).
///
/// Throws [NetworkException] on connection failures.
/// Throws [AuthException] if discovery fails or is invalid.
Future<Uri> fetchTokenEndpoint({
  required Uri discoveryUrl,
  required SoliplexHttpClient httpClient,
}) async {
  final HttpResponse response;
  try {
    response = await httpClient.request(
      'GET',
      discoveryUrl,
      timeout: const Duration(seconds: 10),
    );
  } on Exception catch (e) {
    debugPrint('Failed to fetch OIDC discovery: $e');
    throw NetworkException(
      message: 'Failed to fetch OIDC configuration',
      originalError: e,
    );
  }

  if (response.statusCode != 200) {
    throw AuthException('OIDC discovery failed: ${response.statusCode}');
  }

  final Map<String, dynamic> discovery;
  try {
    discovery = jsonDecode(response.body) as Map<String, dynamic>;
  } on FormatException catch (e) {
    throw AuthException('Invalid OIDC discovery document: $e');
  }

  final tokenEndpoint = discovery['token_endpoint'] as String?;
  if (tokenEndpoint == null) {
    throw const AuthException('OIDC discovery missing token_endpoint');
  }

  final tokenUri = Uri.parse(tokenEndpoint);

  // Validate token endpoint origin matches discovery origin
  if (tokenUri.host != discoveryUrl.host ||
      tokenUri.scheme != discoveryUrl.scheme) {
    throw AuthException(
      'Token endpoint origin mismatch: expected '
      '${discoveryUrl.scheme}://${discoveryUrl.host}, '
      'got ${tokenUri.scheme}://${tokenUri.host}',
    );
  }

  return tokenUri;
}

/// Refresh tokens using the IdP's token endpoint.
///
/// Uses HTTP client directly (not flutter_appauth) so refresh calls appear
/// in HTTP logs. Fetches the OIDC discovery document to find the token
/// endpoint, then POSTs a refresh_token grant.
///
/// Throws [RefreshExpiredException] if the refresh token is invalid/expired.
/// Throws [NetworkException] on connection failures.
/// Throws [AuthException] for other token endpoint errors.
Future<AuthResult> refreshTokens({
  required String discoveryUrl,
  required String refreshToken,
  required String clientId,
  required SoliplexHttpClient httpClient,
}) async {
  final discoveryUri = Uri.parse(discoveryUrl);
  final tokenUri = await fetchTokenEndpoint(
    discoveryUrl: discoveryUri,
    httpClient: httpClient,
  );

  final HttpResponse tokenResponse;
  try {
    tokenResponse = await httpClient.request(
      'POST',
      tokenUri,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: Uri(
        queryParameters: {
          'grant_type': 'refresh_token',
          'refresh_token': refreshToken,
          'client_id': clientId,
        },
      ).query,
      timeout: const Duration(seconds: 30),
    );
  } on Exception catch (e) {
    debugPrint('Token refresh request failed: $e');
    throw NetworkException(
      message: 'Token refresh request failed',
      originalError: e,
    );
  }

  final Map<String, dynamic> tokenData;
  try {
    tokenData = jsonDecode(tokenResponse.body) as Map<String, dynamic>;
  } on FormatException catch (e) {
    throw AuthException('Invalid token response: $e');
  }

  // Handle error responses
  if (tokenResponse.statusCode != 200) {
    final error = tokenData['error'] as String?;
    final errorDescription = tokenData['error_description'] as String?;

    debugPrint('Token refresh error: $error - $errorDescription');

    if (error == 'invalid_grant') {
      throw RefreshExpiredException(
        errorDescription ?? 'Refresh token expired or revoked',
      );
    }

    throw AuthException(
      errorDescription ?? error ?? 'Token refresh failed',
    );
  }

  // Parse successful response
  final accessToken = tokenData['access_token'] as String?;
  if (accessToken == null) {
    throw const AuthException('Token response missing access_token');
  }

  DateTime? expiresAt;
  final expiresIn = tokenData['expires_in'] as int?;
  if (expiresIn != null) {
    expiresAt = DateTime.now().add(Duration(seconds: expiresIn));
  }

  return AuthResult(
    accessToken: accessToken,
    refreshToken: tokenData['refresh_token'] as String? ?? refreshToken,
    idToken: tokenData['id_token'] as String?,
    expiresAt: expiresAt,
  );
}
