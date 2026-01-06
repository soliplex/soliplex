import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Storage keys for authentication tokens.
abstract final class AuthStorageKeys {
  static const accessToken = 'auth_access_token';
  static const refreshToken = 'auth_refresh_token';
  static const idToken = 'auth_id_token';
  static const expiresAt = 'auth_expires_at';
  static const issuerId = 'auth_issuer_id';
  static const issuerDiscoveryUrl = 'auth_issuer_discovery_url';
}

/// Secure storage for authentication tokens.
///
/// Uses platform Keychain (iOS/macOS) with `first_unlock_this_device`
/// accessibility:
/// - Available after first device unlock (allows background token refresh)
/// - Not synced to iCloud Keychain or included in backups
/// - Tokens cannot be restored to a different device
class AuthStorage {
  AuthStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? _createSecureStorage();

  final FlutterSecureStorage _storage;

  static FlutterSecureStorage _createSecureStorage() {
    return const FlutterSecureStorage(
      iOptions: IOSOptions(
        accessibility: KeychainAccessibility.first_unlock_this_device,
      ),
      mOptions: MacOsOptions(
        accessibility: KeychainAccessibility.first_unlock_this_device,
      ),
    );
  }

  /// Clears stale tokens on first launch after app reinstall.
  ///
  /// iOS preserves Keychain data across app uninstall/reinstall. This can
  /// cause issues where a reinstalled app inherits tokens from a previous
  /// installation. Call this early in app initialization (e.g., main.dart).
  ///
  /// On macOS without code signing, Keychain access may fail. This is handled
  /// gracefully since macOS doesn't have the same reinstall persistence issue.
  static Future<void> clearOnReinstall() async {
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
        ]);
      } on Exception catch (e) {
        // Keychain may not be available (e.g., unsigned macOS builds).
        // This is acceptable since macOS doesn't persist Keychain across
        // uninstall like iOS does.
        debugPrint('AuthStorage: clearOnReinstall skipped: $e');
      }
      await prefs.setBool(key, true);
    }
  }

  /// Saves all authentication tokens to secure storage.
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
    required DateTime expiresAt,
    required String issuerId,
    required String issuerDiscoveryUrl,
    String? idToken,
  }) async {
    await Future.wait([
      _storage.write(key: AuthStorageKeys.accessToken, value: accessToken),
      _storage.write(key: AuthStorageKeys.refreshToken, value: refreshToken),
      _storage.write(
        key: AuthStorageKeys.expiresAt,
        value: expiresAt.toIso8601String(),
      ),
      _storage.write(key: AuthStorageKeys.issuerId, value: issuerId),
      _storage.write(
        key: AuthStorageKeys.issuerDiscoveryUrl,
        value: issuerDiscoveryUrl,
      ),
      if (idToken != null)
        _storage.write(key: AuthStorageKeys.idToken, value: idToken),
    ]);
  }

  /// Loads stored authentication tokens.
  ///
  /// Returns null if no tokens are stored or if required fields are missing.
  Future<StoredTokens?> loadTokens() async {
    final (
      accessToken,
      refreshToken,
      expiresAtStr,
      issuerId,
      issuerDiscoveryUrl,
      idToken
    ) = await (
      _storage.read(key: AuthStorageKeys.accessToken),
      _storage.read(key: AuthStorageKeys.refreshToken),
      _storage.read(key: AuthStorageKeys.expiresAt),
      _storage.read(key: AuthStorageKeys.issuerId),
      _storage.read(key: AuthStorageKeys.issuerDiscoveryUrl),
      _storage.read(key: AuthStorageKeys.idToken),
    ).wait;

    if (accessToken == null ||
        refreshToken == null ||
        expiresAtStr == null ||
        issuerId == null ||
        issuerDiscoveryUrl == null) {
      return null;
    }

    final expiresAt = DateTime.tryParse(expiresAtStr);
    if (expiresAt == null) return null;

    return StoredTokens(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: expiresAt,
      issuerId: issuerId,
      issuerDiscoveryUrl: issuerDiscoveryUrl,
      idToken: idToken,
    );
  }

  /// Clears all stored authentication tokens.
  Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: AuthStorageKeys.accessToken),
      _storage.delete(key: AuthStorageKeys.refreshToken),
      _storage.delete(key: AuthStorageKeys.idToken),
      _storage.delete(key: AuthStorageKeys.expiresAt),
      _storage.delete(key: AuthStorageKeys.issuerId),
      _storage.delete(key: AuthStorageKeys.issuerDiscoveryUrl),
    ]);
  }
}

/// Tokens loaded from secure storage.
class StoredTokens {
  const StoredTokens({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    required this.issuerId,
    required this.issuerDiscoveryUrl,
    this.idToken,
  });

  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;
  final String issuerId;
  final String issuerDiscoveryUrl;
  final String? idToken;
}
