import 'dart:js_interop';

import 'package:soliplex/core/auth/callback_params.dart';
import 'package:web/web.dart' as web;

/// Web implementation for auth callback URL handling.
///
/// Provides functions to detect and extract auth callback parameters from URL.

/// Extract query params from URL, checking both search and hash fragment.
///
/// With hash-based routing (/#/path?query), params may be in the hash:
/// - `/?token=xxx` → params in window.location.search
/// - `/#/auth/callback?token=xxx` → params in window.location.hash
Map<String, String> _getQueryParams() {
  // First check regular query string
  final search = web.window.location.search;
  if (search.isNotEmpty) {
    return Uri.splitQueryString(search.substring(1));
  }

  // Check hash fragment for query params (hash routing: #/path?query)
  final hash = web.window.location.hash;
  if (hash.isNotEmpty) {
    final queryIndex = hash.indexOf('?');
    if (queryIndex != -1) {
      return Uri.splitQueryString(hash.substring(queryIndex + 1));
    }
  }

  return {};
}

/// Check if the current URL has auth callback tokens.
///
/// With hash-based routing, tokens may be in hash: /#/auth/callback?token=...
bool isAuthCallback() {
  final params = _getQueryParams();
  return params.containsKey('token') || params.containsKey('access_token');
}

/// Extract callback parameters from URL.
///
/// Detects the callback type based on URL parameters:
/// - If `token` or `access_token` is present: [BackendMediatedCallbackParams]
/// - If `code` is present: [PkceCallbackParams]
/// - Otherwise: [NoCallbackParams]
CallbackParams extractCallbackParams() {
  final params = _getQueryParams();
  if (params.isEmpty) return const NoCallbackParams();

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
  // With hash routing, clean up params from hash: #/path?query → #/path
  final hash = web.window.location.hash;
  var cleanHash = hash;
  if (hash.isNotEmpty) {
    final queryIndex = hash.indexOf('?');
    if (queryIndex != -1) {
      cleanHash = hash.substring(0, queryIndex);
    }
  }

  // Build clean URL without query params
  final cleanUrl =
      '${web.window.location.origin}${web.window.location.pathname}$cleanHash';
  web.window.history.replaceState(JSObject(), '', cleanUrl);
}
