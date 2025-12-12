import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'oidc_auth_interactor.dart';
import 'secure_sso_storage.dart';
import 'secure_storage_gateway.dart';
import 'secure_token_storage.dart';

/// Default token expiration buffer (refresh tokens 5 minutes before expiry)
const _tokenExpirationBuffer = Duration(minutes: 5);

/// Provider for the underlying FlutterSecureStorage instance
final flutterSecureStorageProvider = Provider<FlutterSecureStorage>((ref) {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
    ),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
    mOptions: MacOsOptions(
      // Use unique account name to avoid keychain conflicts
      accountName: 'soliplex_oidc_tokens',
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
  );
});

/// Provider for SecureStorageGateway
final secureStorageGatewayProvider = Provider<SecureStorageGateway>((ref) {
  final storage = ref.watch(flutterSecureStorageProvider);
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
    return OidcWebAuthInteractor(
      ssoStorage,
      tokenStorage,
      _tokenExpirationBuffer,
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
