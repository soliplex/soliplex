// Stub implementation for non-web platforms.
//
// These functions are no-ops on non-web platforms.
// On web, the actual implementation in web_auth_callback_web.dart is used.

import 'package:soliplex/core/auth/callback_params.dart';

/// Capture callback params from URL at app startup.
/// On non-web platforms, this is a no-op.
void captureCallbackParamsEarly() {}

/// Get the cached callback params captured at startup.
/// On non-web platforms, this always returns null.
CallbackParams? getCachedCallbackParams() => null;

/// Clear the cached callback params after they've been processed.
/// On non-web platforms, this is a no-op.
void clearCachedCallbackParams() {}

/// Check if the current URL has auth callback tokens.
/// On non-web platforms, this always returns false.
bool isAuthCallback() => false;

/// Extract callback parameters from URL.
///
/// On non-web platforms, this always returns [NoCallbackParams].
CallbackParams extractCallbackParams() => const NoCallbackParams();

/// Get the current URL path
String getCurrentPath() => '';

/// Clear the URL query parameters (clean up after callback)
void clearUrlParams() {}
