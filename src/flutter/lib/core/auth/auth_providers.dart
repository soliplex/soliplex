import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/auth/oidc_auth_interactor.dart';
import 'package:soliplex/core/auth/secure_sso_storage.dart';
import 'package:soliplex/core/auth/secure_storage_gateway.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/auth/web_auth_pending_storage.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/services/secure_storage_service.dart'
    show secureStorageProvider;

/// Default token expiration buffer (refresh tokens 5 minutes before expiry)
const _tokenExpirationBuffer = Duration(minutes: 5);

/// Provider for SecureStorageGateway - uses the consolidated
/// SecureStorageService
final secureStorageGatewayProvider = Provider<SecureStorageGateway>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return SecureStorageGateway(storage);
});

/// Provider for SecureTokenStorage
final secureTokenStorageProvider = Provider<SecureTokenStorage>((ref) {
  final gateway = ref.watch(secureStorageGatewayProvider);
  return SecureTokenStorage(gateway);
});

/// Provider for SecureSsoStorage
final secureSsoStorageProvider = Provider<SecureSsoStorage>((ref) {
  final gateway = ref.watch(secureStorageGatewayProvider);
  return SecureSsoStorage(gateway);
});

/// Provider for FlutterAppAuth (only used on mobile/desktop)
final flutterAppAuthProvider = Provider<FlutterAppAuth>((ref) {
  return const FlutterAppAuth();
});

/// Provider for WebAuthPendingStorage (web only, but safe to access on all
/// platforms)
final webAuthPendingStorageProvider = Provider<WebAuthPendingStorage>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return WebAuthPendingStorage(storage);
});

/// Provider for WebAuthCallbackHandler (web only, but safe to access on all
/// platforms)
final webAuthCallbackHandlerProvider = Provider<WebAuthCallbackHandler>((ref) {
  final pendingStorage = ref.watch(webAuthPendingStorageProvider);
  final tokenStorage = ref.watch(secureTokenStorageProvider);
  final secureStorageService = ref.watch(secureStorageProvider);
  return WebAuthCallbackHandler(
    pendingStorage: pendingStorage,
    tokenStorage: tokenStorage,
    secureStorageService: secureStorageService,
  );
});

/// Provider for OidcAuthInteractor (platform-aware)
final oidcAuthInteractorProvider = Provider<OidcAuthInteractor>((ref) {
  final ssoStorage = ref.watch(secureSsoStorageProvider);
  final tokenStorage = ref.watch(secureTokenStorageProvider);
  final inspector = ref.read(networkInspectorProvider);

  if (kIsWeb) {
    final pendingStorage = ref.watch(webAuthPendingStorageProvider);
    return OidcWebAuthInteractor(
      ssoStorage,
      tokenStorage,
      _tokenExpirationBuffer,
      inspector: inspector,
      pendingStorage: pendingStorage,
    );
  } else {
    final appAuth = ref.watch(flutterAppAuthProvider);
    return OidcMobileAuthInteractor(
      appAuth,
      ssoStorage,
      tokenStorage,
      _tokenExpirationBuffer,
    );
  }
});
