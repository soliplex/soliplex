import 'package:flutter/foundation.dart';
import 'package:soliplex_frontend/core/auth/auth_flow.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';
import 'package:web/web.dart' as web;

/// Abstraction for URL navigation to enable testing.
abstract class UrlNavigator {
  /// Gets the current page origin (e.g., 'https://example.com').
  String get origin;

  /// Navigates to the given URL.
  void navigateTo(String url);
}

/// Default implementation using browser window.
class WindowUrlNavigator implements UrlNavigator {
  @override
  String get origin => web.window.location.origin;

  @override
  void navigateTo(String url) {
    web.window.location.href = url;
  }
}

/// Creates the web platform implementation of [AuthFlow].
///
/// [backendBaseUrl] is the backend server URL for BFF endpoints.
/// Defaults to same origin (production: frontend served by backend).
AuthFlow createAuthFlow({
  String? backendBaseUrl,
  UrlNavigator? navigator,
}) =>
    WebAuthFlow(backendBaseUrl: backendBaseUrl, navigator: navigator);

/// Web implementation of OIDC authentication using BFF pattern.
///
/// Redirects to backend OAuth endpoint which handles PKCE and token exchange.
/// Tokens are returned in the callback URL.
class WebAuthFlow implements AuthFlow {
  /// Creates a web auth flow.
  ///
  /// [backendBaseUrl] is the backend server URL for BFF endpoints.
  /// If null, uses the current origin (for production where frontend is
  /// served by backend).
  /// [navigator] is injected for testability. Defaults to [WindowUrlNavigator].
  @visibleForTesting
  WebAuthFlow({String? backendBaseUrl, UrlNavigator? navigator})
      : _backendBaseUrl = backendBaseUrl,
        _navigator = navigator ?? WindowUrlNavigator();

  final String? _backendBaseUrl;
  final UrlNavigator _navigator;

  @override
  bool get isWeb => true;

  @override
  Future<AuthResult> authenticate(OidcIssuer issuer) async {
    // Build the return URL for the callback (always frontend origin)
    final frontendOrigin = _navigator.origin;
    final returnTo = Uri.encodeFull('$frontendOrigin/#/auth/callback');

    // Use backend URL for BFF endpoints, fall back to same origin for prod
    final backendUrl = _backendBaseUrl ?? frontendOrigin;

    // Redirect to backend BFF login endpoint
    // Backend handles PKCE, token exchange, and redirects back with tokens
    final loginUrl = '$backendUrl/api/login/${issuer.id}?return_to=$returnTo';

    debugPrint('Web auth: Redirecting to $loginUrl');
    _navigator.navigateTo(loginUrl);

    // Browser navigates away; throw to make the type system honest.
    // Auth completion happens via callback URL → AuthNotifier.completeWebAuth.
    throw const AuthRedirectInitiated();
  }

  @override
  Future<void> endSession({
    required String discoveryUrl,
    required String idToken,
  }) async {
    // On web, we just clear local storage (done by caller).
    // No IdP session termination - would require redirect flow.
    debugPrint('Web auth: Local logout only (no IdP redirect)');
  }
}
