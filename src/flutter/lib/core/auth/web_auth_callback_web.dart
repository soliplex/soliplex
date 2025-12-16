import 'dart:js_interop';

import 'package:soliplex/core/auth/callback_params.dart';
import 'package:web/web.dart' as web;

/// Web implementation for auth callback URL handling.
///
/// Provides functions to detect and extract auth callback parameters from URL.

/// Check if the current URL has auth callback tokens.
///
/// With hash-based routing, OIDC redirects to /?token=... and the hash
/// handles client-side routing. We detect callbacks by token presence.
bool isAuthCallback() {
  final search = web.window.location.search;
  if (search.isEmpty) return false;
  final params = Uri.splitQueryString(search.substring(1));
  return params.containsKey('token') || params.containsKey('access_token');
}

/// Extract callback parameters from URL.
///
/// Detects the callback type based on URL parameters:
/// - If `token` or `access_token` is present: [BackendMediatedCallbackParams]
/// - If `code` is present: [PkceCallbackParams]
/// - Otherwise: [NoCallbackParams]
CallbackParams extractCallbackParams() {
  final search = web.window.location.search;
  if (search.isEmpty) return const NoCallbackParams();

  final params = Uri.splitQueryString(
    search.substring(1),
  ); // Remove leading '?'

  // Check for error first (applies to both flows)
  final error = params['error'];

  // Backend-mediated flow: tokens in URL
  // Support both backend names (token) and standard OAuth names (access_token)
  final accessToken = params['token'] ?? params['access_token'];
  if (accessToken != null || params.containsKey('token')) {
    return BackendMediatedCallbackParams(
      accessToken: accessToken,
      refreshToken: params['refresh_token'],
      expiresIn: _parseIntOrNull(params['expires_in']),
      refreshExpiresIn: _parseIntOrNull(params['refresh_expires_in']),
      error: error,
    );
  }

  // PKCE flow: authorization code in URL
  final code = params['code'];
  final state = params['state'];
  if (code != null || state != null || error != null) {
    return PkceCallbackParams(
      code: code,
      state: state,
      error: error,
    );
  }

  return const NoCallbackParams();
}

/// Parse an integer from a string, returning null if invalid.
int? _parseIntOrNull(String? value) {
  if (value == null) return null;
  return int.tryParse(value);
}

/// Get the current URL path
String getCurrentPath() {
  return web.window.location.pathname;
}

/// Clear the URL query parameters (clean up after callback)
void clearUrlParams() {
  // Replace current URL without query params to clean up
  final cleanUrl =
      '${web.window.location.origin}${web.window.location.pathname}';
  // Pass empty JSObject for state (null not directly usable with toJSBox)
  web.window.history.replaceState(JSObject(), '', cleanUrl);
}
