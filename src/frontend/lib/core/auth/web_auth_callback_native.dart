import 'package:soliplex_frontend/core/auth/web_auth_callback.dart';

/// Capture callback params - no-op on native.
///
/// Native platforms use flutter_appauth which handles OAuth callbacks
/// in-process, so URL-based callback handling is not needed.
CallbackParams captureCallbackParamsNow() => const NoCallbackParams();

/// Creates the native platform implementation of [CallbackParamsService].
CallbackParamsService createCallbackParamsService() =>
    NativeCallbackParamsService();

/// Native implementation - all methods are no-ops.
///
/// Native platforms use flutter_appauth which handles OAuth callbacks
/// in-process, so URL-based callback handling is not needed.
class NativeCallbackParamsService implements CallbackParamsService {
  @override
  bool isAuthCallback() => false;

  @override
  CallbackParams extractParams() => const NoCallbackParams();

  @override
  void clearUrlParams() {}
}
