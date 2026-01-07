import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';
import 'package:web/web.dart' as web;

/// Creates the web platform implementation of [AuthStorage].
AuthStorage createAuthStorage() => WebAuthStorage();

/// No-op on web - browsers don't have the iOS Keychain persistence issue.
Future<void> clearOnReinstall() async {
  // Web browsers don't persist storage across "reinstalls" (clearing site data
  // clears localStorage). No action needed.
}

/// Web implementation using localStorage.
///
/// Security note: localStorage is accessible to JavaScript and vulnerable to
/// XSS attacks. This is acceptable for this internal tool because:
/// - CSP headers block XSS vectors
/// - Server validates tokens on every request
/// - Tokens have short expiry with refresh rotation
/// - sessionStorage would lose tokens on tab close, breaking legitimate
///   workflows (accidental refresh, opening new tabs)
class WebAuthStorage implements AuthStorage {
  web.Storage get _storage => web.window.localStorage;

  @override
  Future<void> saveTokens(Authenticated tokens) async {
    _storage
      ..setItem(AuthStorageKeys.accessToken, tokens.accessToken)
      ..setItem(AuthStorageKeys.refreshToken, tokens.refreshToken)
      ..setItem(AuthStorageKeys.expiresAt, tokens.expiresAt.toIso8601String())
      ..setItem(AuthStorageKeys.issuerId, tokens.issuerId)
      ..setItem(AuthStorageKeys.issuerDiscoveryUrl, tokens.issuerDiscoveryUrl)
      ..setItem(AuthStorageKeys.clientId, tokens.clientId)
      ..setItem(AuthStorageKeys.idToken, tokens.idToken);
  }

  @override
  Future<Authenticated?> loadTokens() async {
    final accessToken = _storage.getItem(AuthStorageKeys.accessToken);
    final refreshToken = _storage.getItem(AuthStorageKeys.refreshToken);
    final expiresAtStr = _storage.getItem(AuthStorageKeys.expiresAt);
    final issuerId = _storage.getItem(AuthStorageKeys.issuerId);
    final issuerDiscoveryUrl =
        _storage.getItem(AuthStorageKeys.issuerDiscoveryUrl);
    final clientId = _storage.getItem(AuthStorageKeys.clientId);
    final idToken = _storage.getItem(AuthStorageKeys.idToken);

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
    _storage
      ..removeItem(AuthStorageKeys.accessToken)
      ..removeItem(AuthStorageKeys.refreshToken)
      ..removeItem(AuthStorageKeys.idToken)
      ..removeItem(AuthStorageKeys.expiresAt)
      ..removeItem(AuthStorageKeys.issuerId)
      ..removeItem(AuthStorageKeys.issuerDiscoveryUrl)
      ..removeItem(AuthStorageKeys.clientId);
  }
}
