import 'dart:js_interop';

import 'package:web/web.dart' as web;

/// Web implementation for auth callback URL handling.
///
/// Provides functions to detect and extract auth callback parameters from URL.

/// Check if the current URL is an auth callback
bool isAuthCallback() {
  final path = web.window.location.pathname;
  return path == '/auth/callback' || path.endsWith('/auth/callback');
}

/// Extract callback parameters from URL
/// Returns (code, state, error)
(String?, String?, String?) extractCallbackParams() {
  final search = web.window.location.search;
  if (search.isEmpty) return (null, null, null);

  final params = Uri.splitQueryString(
    search.substring(1),
  ); // Remove leading '?'

  final code = params['code'];
  final state = params['state'];
  final error = params['error'];

  return (code, state, error);
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
