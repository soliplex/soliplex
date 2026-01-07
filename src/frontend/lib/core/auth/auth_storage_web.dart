import 'package:flutter/foundation.dart';
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
/// - Tokens have short expiry (BFF refresh endpoint is pending implementation)
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

  @override
  Future<void> savePreAuthState(PreAuthState state) async {
    _storage
      ..setItem(AuthStorageKeys.preAuthIssuerId, state.issuerId)
      ..setItem(AuthStorageKeys.preAuthDiscoveryUrl, state.discoveryUrl)
      ..setItem(AuthStorageKeys.preAuthClientId, state.clientId)
      ..setItem(
        AuthStorageKeys.preAuthCreatedAt,
        state.createdAt.toIso8601String(),
      );
  }

  @override
  Future<PreAuthState?> loadPreAuthState() async {
    final issuerId = _storage.getItem(AuthStorageKeys.preAuthIssuerId);
    final discoveryUrl = _storage.getItem(AuthStorageKeys.preAuthDiscoveryUrl);
    final clientId = _storage.getItem(AuthStorageKeys.preAuthClientId);
    final createdAtStr = _storage.getItem(AuthStorageKeys.preAuthCreatedAt);

    if (issuerId == null ||
        discoveryUrl == null ||
        clientId == null ||
        createdAtStr == null) {
      return null;
    }

    final createdAt = DateTime.tryParse(createdAtStr);
    if (createdAt == null) return null;

    final state = PreAuthState(
      issuerId: issuerId,
      discoveryUrl: discoveryUrl,
      clientId: clientId,
      createdAt: createdAt,
    );

    // Reject expired pre-auth state
    if (state.isExpired) {
      try {
        await clearPreAuthState();
      } on Exception catch (e) {
        debugPrint('WebAuthStorage: Failed to clear expired pre-auth: $e');
      }
      return null;
    }

    return state;
  }

  @override
  Future<void> clearPreAuthState() async {
    _storage
      ..removeItem(AuthStorageKeys.preAuthIssuerId)
      ..removeItem(AuthStorageKeys.preAuthDiscoveryUrl)
      ..removeItem(AuthStorageKeys.preAuthClientId)
      ..removeItem(AuthStorageKeys.preAuthCreatedAt);
  }
}
