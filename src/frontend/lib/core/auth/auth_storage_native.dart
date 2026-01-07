import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';

/// Creates the native platform implementation of [AuthStorage].
AuthStorage createAuthStorage() => NativeAuthStorage();

/// Clears stale tokens on first launch after reinstall.
///
/// iOS preserves Keychain data across app uninstall/reinstall. This can
/// cause issues where a reinstalled app inherits tokens from a previous
/// installation. Call this early in app initialization (e.g., main.dart).
///
/// On macOS without code signing, Keychain access may fail. This is handled
/// gracefully since macOS doesn't have the same reinstall persistence issue.
Future<void> clearOnReinstall() async {
  const key = 'auth_storage_initialized';
  final prefs = await SharedPreferences.getInstance();

  if (!prefs.containsKey(key)) {
    // First launch after install - clear any stale keychain data
    try {
      final storage = _createSecureStorage();
      await Future.wait([
        storage.delete(key: AuthStorageKeys.accessToken),
        storage.delete(key: AuthStorageKeys.refreshToken),
        storage.delete(key: AuthStorageKeys.idToken),
        storage.delete(key: AuthStorageKeys.expiresAt),
        storage.delete(key: AuthStorageKeys.issuerId),
        storage.delete(key: AuthStorageKeys.issuerDiscoveryUrl),
        storage.delete(key: AuthStorageKeys.clientId),
      ]);
    } on Exception {
      // Keychain may not be available (e.g., unsigned macOS builds).
      // This is acceptable since macOS doesn't persist Keychain across
      // uninstall like iOS does.
      debugPrint('AuthStorage: clearOnReinstall skipped');
    }
    await prefs.setBool(key, true);
  }
}

FlutterSecureStorage _createSecureStorage() {
  return const FlutterSecureStorage(
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
    mOptions: MacOsOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
  );
}

/// Native implementation using platform Keychain (iOS/macOS).
///
/// Uses `first_unlock_this_device` accessibility:
/// - Available after first device unlock (allows background token refresh)
/// - Not synced to iCloud Keychain or included in backups
/// - Tokens cannot be restored to a different device
class NativeAuthStorage implements AuthStorage {
  NativeAuthStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? _createSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<void> saveTokens(Authenticated tokens) async {
    await Future.wait([
      _storage.write(
        key: AuthStorageKeys.accessToken,
        value: tokens.accessToken,
      ),
      _storage.write(
        key: AuthStorageKeys.refreshToken,
        value: tokens.refreshToken,
      ),
      _storage.write(
        key: AuthStorageKeys.expiresAt,
        value: tokens.expiresAt.toIso8601String(),
      ),
      _storage.write(key: AuthStorageKeys.issuerId, value: tokens.issuerId),
      _storage.write(
        key: AuthStorageKeys.issuerDiscoveryUrl,
        value: tokens.issuerDiscoveryUrl,
      ),
      _storage.write(key: AuthStorageKeys.clientId, value: tokens.clientId),
      _storage.write(key: AuthStorageKeys.idToken, value: tokens.idToken),
    ]);
  }

  @override
  Future<Authenticated?> loadTokens() async {
    final (
      accessToken,
      refreshToken,
      expiresAtStr,
      issuerId,
      issuerDiscoveryUrl,
      clientId,
      idToken
    ) = await (
      _storage.read(key: AuthStorageKeys.accessToken),
      _storage.read(key: AuthStorageKeys.refreshToken),
      _storage.read(key: AuthStorageKeys.expiresAt),
      _storage.read(key: AuthStorageKeys.issuerId),
      _storage.read(key: AuthStorageKeys.issuerDiscoveryUrl),
      _storage.read(key: AuthStorageKeys.clientId),
      _storage.read(key: AuthStorageKeys.idToken),
    ).wait;

    if (accessToken == null ||
        refreshToken == null ||
        expiresAtStr == null ||
        issuerId == null ||
        issuerDiscoveryUrl == null ||
        clientId == null ||
        idToken == null) {
      return null;
    }

    final expiresAt = DateTime.tryParse(expiresAtStr);
    if (expiresAt == null) return null;

    return Authenticated(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: expiresAt,
      issuerId: issuerId,
      issuerDiscoveryUrl: issuerDiscoveryUrl,
      clientId: clientId,
      idToken: idToken,
    );
  }

  @override
  Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: AuthStorageKeys.accessToken),
      _storage.delete(key: AuthStorageKeys.refreshToken),
      _storage.delete(key: AuthStorageKeys.idToken),
      _storage.delete(key: AuthStorageKeys.expiresAt),
      _storage.delete(key: AuthStorageKeys.issuerId),
      _storage.delete(key: AuthStorageKeys.issuerDiscoveryUrl),
      _storage.delete(key: AuthStorageKeys.clientId),
    ]);
  }

  /// No-op on native - flutter_appauth handles OAuth in-process.
  @override
  Future<void> savePreAuthState(PreAuthState state) async {}

  /// Always returns null on native - pre-auth state is web-only.
  @override
  Future<PreAuthState?> loadPreAuthState() async => null;

  /// No-op on native.
  @override
  Future<void> clearPreAuthState() async {}
}
