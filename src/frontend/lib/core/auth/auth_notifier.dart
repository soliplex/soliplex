import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/auth/auth_flow.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';

/// Fallback token lifetime when provider doesn't return expires_in.
/// Conservative value to ensure refresh happens before most real tokens expire.
const _fallbackTokenLifetime = Duration(minutes: 30);

/// Notifier for managing authentication state.
///
/// Handles sign in, sign out, and session restoration.
///
/// Note: Currently calls [authenticate] and [endSession] directly, making
/// unit testing difficult. For testability, consider injecting an AuthFlow
/// interface. Accepted for MVP; manual testing covers auth flows.
class AuthNotifier extends Notifier<AuthState> {
  AuthNotifier({AuthStorage? storage}) : _storage = storage ?? AuthStorage();

  final AuthStorage _storage;

  @override
  AuthState build() {
    // Start with loading, then restore session
    _restoreSession();
    return const AuthLoading();
  }

  Future<void> _restoreSession() async {
    final StoredTokens? tokens;
    try {
      tokens = await _storage.loadTokens();
    } on Exception catch (e) {
      // Storage unavailable (keychain locked, permissions, corruption)
      // Policy: treat as unauthenticated rather than stuck in loading
      debugPrint('AuthNotifier: Failed to restore session: $e');
      state = const Unauthenticated();
      return;
    }

    if (tokens == null) {
      state = const Unauthenticated();
      return;
    }

    // Check if tokens are expired
    if (DateTime.now().isAfter(tokens.expiresAt)) {
      // Tokens expired - clear and require re-login
      // (Token refresh will be implemented in Slice 3)
      try {
        await _storage.clearTokens();
      } on Exception catch (e) {
        debugPrint('AuthNotifier: Failed to clear expired tokens: $e');
      }
      state = const Unauthenticated();
      return;
    }

    state = Authenticated(
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      expiresAt: tokens.expiresAt,
      issuerId: tokens.issuerId,
      issuerDiscoveryUrl: tokens.issuerDiscoveryUrl,
      idToken: tokens.idToken,
    );
  }

  /// Sign in with the given OIDC issuer.
  ///
  /// Opens system browser for authentication, exchanges code for tokens,
  /// and persists tokens to secure storage.
  Future<void> signIn(OidcIssuer issuer) async {
    try {
      final result = await authenticate(issuer);

      final accessToken = result.accessToken;
      final refreshToken = result.refreshToken ?? '';
      final idToken = result.idToken;

      var expiresAt = result.expiresAt;
      if (expiresAt == null) {
        debugPrint(
          'AuthNotifier: Token response missing expires_in; '
          'using ${_fallbackTokenLifetime.inMinutes}min fallback',
        );
        expiresAt = DateTime.now().add(_fallbackTokenLifetime);
      }

      // Save tokens to secure storage (may fail on unsigned macOS builds)
      try {
        await _storage.saveTokens(
          accessToken: accessToken,
          refreshToken: refreshToken,
          expiresAt: expiresAt,
          issuerId: issuer.id,
          issuerDiscoveryUrl: issuer.discoveryUrl,
          idToken: idToken,
        );
      } on Exception catch (e) {
        debugPrint('AuthNotifier: Failed to persist tokens: $e');
        // Continue - auth works, just won't persist across restarts
      }

      state = Authenticated(
        accessToken: accessToken,
        refreshToken: refreshToken,
        expiresAt: expiresAt,
        issuerId: issuer.id,
        issuerDiscoveryUrl: issuer.discoveryUrl,
        idToken: idToken,
      );
    } on AuthException {
      // Auth failed or was cancelled - stay unauthenticated
      state = const Unauthenticated();
      rethrow;
    }
  }

  /// Sign out, end IdP session, and clear tokens.
  ///
  /// Calls the IdP's end_session_endpoint to fully log out, then clears
  /// local state and secure storage. If endSession fails, local logout
  /// still proceeds.
  Future<void> signOut() async {
    final current = state;
    if (current is Authenticated) {
      await endSession(
        discoveryUrl: current.issuerDiscoveryUrl,
        idToken: current.idToken,
      );
    }
    try {
      await _storage.clearTokens();
    } on Exception catch (e) {
      debugPrint('AuthNotifier: Failed to clear tokens on logout: $e');
    }
    state = const Unauthenticated();
  }

  /// Get the current access token if authenticated.
  String? get accessToken {
    final current = state;
    return current is Authenticated ? current.accessToken : null;
  }
}
