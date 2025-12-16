// Stub implementation for non-web platforms.
//
// These functions are no-ops on non-web platforms.
// On web, the actual implementation in web_auth_callback_web.dart is used.

import 'package:soliplex/core/auth/callback_params.dart';

/// Check if the current URL is an auth callback
bool isAuthCallback() => false;

/// Extract the system/provider ID from the callback URL.
/// On non-web platforms, this always returns null.
String? extractSystemFromPath() => null;

/// Extract callback parameters from URL.
///
/// On non-web platforms, this always returns [NoCallbackParams].
CallbackParams extractCallbackParams() => const NoCallbackParams();

/// Get the current URL path
String getCurrentPath() => '';

/// Clear the URL query parameters (clean up after callback)
void clearUrlParams() {}
