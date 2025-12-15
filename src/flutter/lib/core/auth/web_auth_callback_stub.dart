// Stub implementation for non-web platforms.
//
// These functions are no-ops on non-web platforms.
// On web, the actual implementation in web_auth_callback_web.dart is used.

/// Check if the current URL is an auth callback
bool isAuthCallback() => false;

/// Extract callback parameters from URL
/// Returns (code, state, error)
(String?, String?, String?) extractCallbackParams() => (null, null, null);

/// Get the current URL path
String getCurrentPath() => '';

/// Clear the URL query parameters (clean up after callback)
void clearUrlParams() {}
