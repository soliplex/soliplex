import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart' hide AuthException;
import 'package:soliplex_frontend/core/auth/auth_flow.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

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
      clientId: tokens.clientId,
      idToken: tokens.idToken,
    );
  }

  /// Sign in with the given OIDC issuer.
  ///
  /// Opens system browser for authentication, exchanges code for tokens,
  /// and persists tokens to secure storage.
  ///
  /// Throws [AuthException] if authentication fails or if the IdP doesn't
  /// return an id_token (required for proper OIDC logout).
  Future<void> signIn(OidcIssuer issuer) async {
    try {
      final result = await authenticate(issuer);

      final accessToken = result.accessToken;
      final refreshToken = result.refreshToken ?? '';
      final idToken = result.idToken;

      // id_token is required for proper OIDC logout
      if (idToken == null) {
        throw const AuthException('IdP did not return id_token');
      }

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
          clientId: issuer.clientId,
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
        clientId: issuer.clientId,
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

  /// Whether the current token needs refresh (expiring soon or expired).
  bool get needsRefresh {
    final current = state;
    return current is Authenticated && current.needsRefresh;
  }

  /// Refresh tokens if they are expiring soon.
  ///
  /// Call this proactively before making API requests to avoid 401s.
  /// Does nothing if not authenticated or tokens don't need refresh.
  Future<void> refreshIfExpiringSoon() async {
    if (needsRefresh) {
      await tryRefresh();
    }
  }

  /// Attempt to refresh the current tokens.
  ///
  /// Returns `true` if refresh succeeded, `false` if it failed.
  /// On [RefreshExpiredException] (invalid_grant), clears auth state.
  /// On network errors, returns `false` without clearing state.
  Future<bool> tryRefresh() async {
    final current = state;
    if (current is! Authenticated) {
      return false;
    }

    if (current.refreshToken.isEmpty) {
      debugPrint('AuthNotifier: No refresh token available');
      return false;
    }

    final httpClient = ref.read(baseHttpClientProvider);

    try {
      final result = await refreshTokens(
        discoveryUrl: current.issuerDiscoveryUrl,
        refreshToken: current.refreshToken,
        clientId: current.clientId,
        httpClient: httpClient,
      );

      final accessToken = result.accessToken;
      final refreshToken = result.refreshToken ?? current.refreshToken;
      // Preserve idToken through refresh (IdPs often don't return new one)
      final idToken = result.idToken ?? current.idToken;

      var expiresAt = result.expiresAt;
      if (expiresAt == null) {
        debugPrint(
          'AuthNotifier: Refresh response missing expires_in; '
          'using ${_fallbackTokenLifetime.inMinutes}min fallback',
        );
        expiresAt = DateTime.now().add(_fallbackTokenLifetime);
      }

      // Update storage
      try {
        await _storage.saveTokens(
          accessToken: accessToken,
          refreshToken: refreshToken,
          expiresAt: expiresAt,
          issuerId: current.issuerId,
          issuerDiscoveryUrl: current.issuerDiscoveryUrl,
          clientId: current.clientId,
          idToken: idToken,
        );
      } on Exception catch (e) {
        debugPrint('AuthNotifier: Failed to persist refreshed tokens: $e');
      }

      // Update state
      state = Authenticated(
        accessToken: accessToken,
        refreshToken: refreshToken,
        expiresAt: expiresAt,
        issuerId: current.issuerId,
        issuerDiscoveryUrl: current.issuerDiscoveryUrl,
        clientId: current.clientId,
        idToken: idToken,
        userInfo: current.userInfo,
      );

      debugPrint('AuthNotifier: Token refresh successful');
      return true;
    } on RefreshExpiredException catch (e) {
      // Refresh token is invalid/expired - user must re-authenticate
      debugPrint('AuthNotifier: Refresh token expired: $e');
      try {
        await _storage.clearTokens();
      } on Exception catch (e) {
        debugPrint('AuthNotifier: Failed to clear tokens: $e');
      }
      state = const Unauthenticated();
      return false;
    } on NetworkException catch (e) {
      // Network error - don't clear state, caller can retry
      debugPrint('AuthNotifier: Refresh failed due to network: $e');
      return false;
    } on Exception catch (e) {
      // Other errors (discovery failed, etc.) - don't clear state
      debugPrint('AuthNotifier: Refresh failed: $e');
      return false;
    }
  }
}
