import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
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
  } on Exception {
    // Note: Don't log exception details - may contain sensitive data
    debugPrint('Authentication failed');
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
  } on Exception {
    // endSession failure shouldn't prevent local logout
    // Note: Don't log exception details - may contain sensitive data
    debugPrint('IdP session termination failed (local logout proceeds)');
  }
}
