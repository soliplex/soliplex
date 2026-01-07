import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage_native.dart'
    if (dart.library.js_interop) 'package:soliplex_frontend/core/auth/auth_storage_web.dart'
    as impl;

/// Storage keys for authentication tokens.
abstract final class AuthStorageKeys {
  static const accessToken = 'auth_access_token';
  static const refreshToken = 'auth_refresh_token';
  static const idToken = 'auth_id_token';
  static const expiresAt = 'auth_expires_at';
  static const issuerId = 'auth_issuer_id';
  static const issuerDiscoveryUrl = 'auth_issuer_discovery_url';
  static const clientId = 'auth_client_id';
}

/// Secure storage for authentication tokens.
///
/// Platform implementations:
/// - Native (iOS/macOS): Uses Keychain via flutter_secure_storage
/// - Web: Uses localStorage
abstract class AuthStorage {
  /// Saves authentication state to storage.
  Future<void> saveTokens(Authenticated tokens);

  /// Loads stored authentication state.
  ///
  /// Returns null if no tokens are stored or if required fields are missing.
  Future<Authenticated?> loadTokens();

  /// Clears all stored authentication tokens.
  Future<void> clearTokens();
}

/// Creates a platform-appropriate [AuthStorage] implementation.
AuthStorage createAuthStorage() => impl.createAuthStorage();

/// Clears stale tokens on first launch after reinstall.
///
/// On iOS, Keychain data persists across app uninstall/reinstall. This can
/// cause issues where a reinstalled app inherits tokens from a previous
/// installation. Call this early in app initialization (e.g., main.dart).
///
/// On web, this is a no-op since browsers don't have this persistence issue.
Future<void> clearAuthStorageOnReinstall() => impl.clearOnReinstall();
