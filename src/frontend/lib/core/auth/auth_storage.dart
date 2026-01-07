import 'package:meta/meta.dart';
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

  // Pre-auth state keys (web only - stores issuer before OAuth redirect)
  static const preAuthIssuerId = 'pre_auth_issuer_id';
  static const preAuthDiscoveryUrl = 'pre_auth_discovery_url';
  static const preAuthClientId = 'pre_auth_client_id';
  static const preAuthCreatedAt = 'pre_auth_created_at';
}

/// Issuer state saved before OAuth redirect (web BFF flow only).
///
/// On web, the OAuth callback doesn't include issuer metadata, so we store
/// the selected issuer before redirect and retrieve it after callback.
///
/// Security: Includes [createdAt] timestamp to prevent stale state attacks.
/// Pre-auth state older than [maxAge] should be rejected.
@immutable
class PreAuthState {
  const PreAuthState({
    required this.issuerId,
    required this.discoveryUrl,
    required this.clientId,
    required this.createdAt,
  });

  final String issuerId;
  final String discoveryUrl;
  final String clientId;
  final DateTime createdAt;

  /// Maximum age for valid pre-auth state.
  static const maxAge = Duration(minutes: 5);

  /// Whether this pre-auth state has expired.
  bool get isExpired => DateTime.now().difference(createdAt) > maxAge;

  @override
  bool operator ==(Object other) =>
      other is PreAuthState &&
      other.issuerId == issuerId &&
      other.discoveryUrl == discoveryUrl &&
      other.clientId == clientId &&
      other.createdAt == createdAt;

  @override
  int get hashCode => Object.hash(issuerId, discoveryUrl, clientId, createdAt);

  @override
  String toString() =>
      'PreAuthState(issuerId: $issuerId, createdAt: $createdAt)';
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

  /// Saves pre-auth state before OAuth redirect (web BFF flow only).
  ///
  /// Required because the BFF callback URL only includes tokens, not issuer
  /// metadata (issuerId, discoveryUrl, clientId). We need these for token
  /// refresh, so we save them before redirect and retrieve after callback.
  ///
  /// On native platforms, this is a no-op since flutter_appauth handles
  /// the full OAuth flow in-process without page redirects.
  Future<void> savePreAuthState(PreAuthState state);

  /// Loads pre-auth state saved before OAuth redirect.
  ///
  /// Returns null if no pre-auth state is stored or if it has expired.
  /// On native platforms, always returns null.
  Future<PreAuthState?> loadPreAuthState();

  /// Clears pre-auth state after processing OAuth callback.
  ///
  /// Should be called immediately after [loadPreAuthState] to prevent reuse.
  Future<void> clearPreAuthState();
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
