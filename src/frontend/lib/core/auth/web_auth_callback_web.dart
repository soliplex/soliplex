import 'dart:js_interop';

import 'package:flutter/foundation.dart';
import 'package:soliplex_frontend/core/auth/web_auth_callback.dart';
import 'package:web/web.dart' as web;

/// Capture callback params from current URL.
///
/// Used by [CallbackParamsCapture.captureNow] in main() before ProviderScope.
CallbackParams captureCallbackParamsNow() {
  debugPrint('Web auth: Capturing URL params at startup');
  debugPrint('Web auth: window.location.href = ${web.window.location.href}');
  debugPrint('Web auth: window.location.hash = ${web.window.location.hash}');
  final params = _extractParamsFromUrl();
  debugPrint('Web auth: Captured params: $params');
  return params;
}

/// Creates the web platform implementation of [CallbackParamsService].
CallbackParamsService createCallbackParamsService() =>
    WebCallbackParamsService();

/// Web implementation of [CallbackParamsService].
///
/// Handles OAuth callback URL operations: checking for callbacks,
/// extracting params, and cleaning up browser history.
class WebCallbackParamsService implements CallbackParamsService {
  @override
  bool isAuthCallback() {
    final params = _getQueryParams();
    return params.containsKey('token') || params.containsKey('access_token');
  }

  @override
  CallbackParams extractParams() => _extractParamsFromUrl();

  @override
  void clearUrlParams() {
    final origin = web.window.location.origin;
    final pathname = web.window.location.pathname;
    var hash = web.window.location.hash;

    // Clean params from hash if present: #/path?query → #/path
    if (hash.isNotEmpty) {
      final queryIndex = hash.indexOf('?');
      if (queryIndex != -1) {
        hash = hash.substring(0, queryIndex);
      }
    }

    // Build clean URL: origin + pathname + hash (no query string).
    // This clears both window.location.search AND any params in the hash.
    final cleanUrl = '$origin$pathname$hash';
    web.window.history.replaceState(JSObject(), '', cleanUrl);
  }
}

/// Extract callback params from URL.
CallbackParams _extractParamsFromUrl() {
  final params = _getQueryParams();
  if (params.isEmpty) return const NoCallbackParams();

  // Check for error first
  final error = params['error'];
  final errorDescription = params['error_description'];

  // Backend BFF may use either 'token' or 'access_token'
  final accessToken = params['token'] ?? params['access_token'];

  // If we have a token or an error, this is a callback
  if (accessToken != null || error != null) {
    return WebCallbackParams(
      accessToken: accessToken,
      refreshToken: params['refresh_token'],
      expiresIn: _parseIntOrNull(params['expires_in']),
      error: error,
      errorDescription: errorDescription,
    );
  }

  return const NoCallbackParams();
}

/// Extract query params from URL, checking both search and hash fragment.
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
      final queryString = hash.substring(queryIndex + 1);
      return Uri.splitQueryString(queryString);
    }
  }

  return {};
}

/// Parse an integer from a string, returning null if invalid.
int? _parseIntOrNull(String? value) {
  if (value == null) return null;
  return int.tryParse(value);
}
