import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/server_config_service.dart';
import 'oidc_auth_interactor.dart';
import 'secure_sso_storage.dart';
import 'secure_storage_gateway.dart';
import 'secure_token_storage.dart';

/// Default token expiration buffer (refresh tokens 5 minutes before expiry)
const _tokenExpirationBuffer = Duration(minutes: 5);

/// Provider for SecureStorageGateway - uses the consolidated SecureStorageService
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

/// Provider for OidcAuthInteractor (platform-aware)
final oidcAuthInteractorProvider = Provider<OidcAuthInteractor>((ref) {
  final ssoStorage = ref.watch(secureSsoStorageProvider);
  final tokenStorage = ref.watch(secureTokenStorageProvider);

  if (kIsWeb) {
    return OidcWebAuthInteractor(ssoStorage, tokenStorage, _tokenExpirationBuffer);
  } else {
    final appAuth = ref.watch(flutterAppAuthProvider);
    return OidcMobileAuthInteractor(appAuth, ssoStorage, tokenStorage, _tokenExpirationBuffer);
  }
});
