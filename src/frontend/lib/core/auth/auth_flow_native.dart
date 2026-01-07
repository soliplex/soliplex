import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:soliplex_frontend/core/auth/auth_flow.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';

const _redirectUri = 'ai.soliplex.client://callback';

/// Creates the native platform implementation of [AuthFlow].
///
/// [backendBaseUrl] is ignored on native (only used by web BFF flow).
/// [appAuth] enables integration testing with a mock FlutterAppAuth.
/// For unit tests, override the auth flow provider in Riverpod to inject
/// a mock [AuthFlow] directly.
AuthFlow createAuthFlow({String? backendBaseUrl, FlutterAppAuth? appAuth}) =>
    NativeAuthFlow(appAuth: appAuth ?? const FlutterAppAuth());

/// Native implementation of OIDC authentication using flutter_appauth.
///
/// Opens system browser to IdP login page, handles PKCE automatically.
class NativeAuthFlow implements AuthFlow {
  NativeAuthFlow({required FlutterAppAuth appAuth}) : _appAuth = appAuth;

  final FlutterAppAuth _appAuth;

  @override
  bool get isWeb => false;

  @override
  Future<AuthResult> authenticate(OidcIssuer issuer) async {
    try {
      final result = await _appAuth.authorizeAndExchangeCode(
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

      final accessToken = result.accessToken;
      if (accessToken == null) {
        throw const AuthException('IdP returned success but no access token');
      }

      return AuthResult(
        accessToken: accessToken,
        refreshToken: result.refreshToken,
        idToken: result.idToken,
        expiresAt: result.accessTokenExpirationDateTime,
      );
    } on Exception catch (e) {
      // Log type only - exception details may contain sensitive data
      debugPrint('Authentication failed: ${e.runtimeType}');
      throw const AuthException('Authentication failed. Please try again.');
    }
  }

  @override
  Future<void> endSession({
    required String discoveryUrl,
    required String idToken,
  }) async {
    try {
      await _appAuth.endSession(
        EndSessionRequest(
          idTokenHint: idToken,
          discoveryUrl: discoveryUrl,
          postLogoutRedirectUrl: _redirectUri,
        ),
      );
    } on Exception catch (e) {
      // endSession failure shouldn't prevent local logout
      // Log type only - exception details may contain sensitive data
      debugPrint('IdP session termination failed: ${e.runtimeType}');
    }
  }
}
