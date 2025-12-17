import 'dart:js_interop';

import 'package:soliplex/core/auth/callback_params.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:web/web.dart' as web;

/// Cached callback params captured at app startup.
/// This is needed because GoRouter may modify window.location.hash before
/// we can read it in the AuthCallbackScreen.
CallbackParams? _cachedCallbackParams;

/// Capture callback params from URL at app startup.
/// Call this BEFORE GoRouter initializes to preserve the original URL params.
void captureCallbackParamsEarly() {
  DebugLog.auth('captureCallbackParamsEarly: Capturing URL params at startup');
  _cachedCallbackParams = extractCallbackParams();
  DebugLog.auth(
    'captureCallbackParamsEarly: Cached params: $_cachedCallbackParams',
  );
}

/// Get the cached callback params captured at startup.
/// Returns null if [captureCallbackParamsEarly] was not called.
CallbackParams? getCachedCallbackParams() => _cachedCallbackParams;

/// Clear the cached callback params after they've been processed.
void clearCachedCallbackParams() {
  DebugLog.auth('clearCachedCallbackParams: Clearing cached params');
  _cachedCallbackParams = null;
}

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
  DebugLog.auth('_getQueryParams: search="$search"');
  if (search.isNotEmpty) {
    final params = Uri.splitQueryString(search.substring(1));
    DebugLog.auth('_getQueryParams: Found params in search: ${params.keys}');
    return params;
  }

  // Check hash fragment for query params (hash routing: #/path?query)
  final hash = web.window.location.hash;
  DebugLog.auth('_getQueryParams: hash="$hash"');
  if (hash.isNotEmpty) {
    final queryIndex = hash.indexOf('?');
    DebugLog.auth('_getQueryParams: queryIndex=$queryIndex');
    if (queryIndex != -1) {
      final queryString = hash.substring(queryIndex + 1);
      DebugLog.auth('_getQueryParams: queryString="$queryString"');
      final params = Uri.splitQueryString(queryString);
      DebugLog.auth('_getQueryParams: Found params in hash: ${params.keys}');
      return params;
    }
  }

  DebugLog.auth('_getQueryParams: No params found');
  return {};
}

/// Check if the current URL has auth callback tokens.
///
/// With hash-based routing, tokens may be in hash: /#/auth/callback?token=...
bool isAuthCallback() {
  final params = _getQueryParams();
  final hasToken = params.containsKey('token');
  final hasAccessToken = params.containsKey('access_token');
  DebugLog.auth(
    'isAuthCallback: hasToken=$hasToken, hasAccessToken=$hasAccessToken',
  );
  return hasToken || hasAccessToken;
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
