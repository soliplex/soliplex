import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart' hide AuthException;
import 'package:soliplex_frontend/core/auth/auth_flow.dart';
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';

/// Notifier for managing authentication state.
///
/// Handles sign in, sign out, session restoration, and token refresh.
///
/// Implements [TokenRefresher] to provide refresh capabilities to
/// RefreshingHttpClient without tight coupling.
///
/// ## Dependency Injection Pattern
///
/// Dependencies use `late final` fields initialized at the start of [build]:
///
/// ```dart
/// late final AuthStorage _storage;
/// late final TokenRefreshService _refreshService;
///
/// @override
/// AuthState build() {
///   _storage = ref.read(authStorageProvider);
///   _refreshService = ref.read(tokenRefreshServiceProvider);
///   // ...
/// }
/// ```
///
/// **Why not constructor injection?** Riverpod's [NotifierProvider] uses
/// `AuthNotifier.new` (the default constructor), so parameters can't be passed.
/// The `ref` object is only available inside [build] and instance methods.
///
/// **Lifecycle guarantee:** Riverpod calls [build] before exposing the
/// Notifier. No instance method can be called until [build] completes and
/// returns the initial state. The `late final` fields are always initialized
/// before use.
///
/// **Testing:** Override [authStorageProvider] and
/// [tokenRefreshServiceProvider] in tests to inject mocks.
class AuthNotifier extends Notifier<AuthState> implements TokenRefresher {
  late final AuthStorage _storage;
  late final TokenRefreshService _refreshService;

  @override
  AuthState build() {
    _storage = ref.read(authStorageProvider);
    _refreshService = ref.read(tokenRefreshServiceProvider);

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
        const fallback = TokenRefreshService.fallbackTokenLifetime;
        debugPrint(
          'AuthNotifier: Token response missing expires_in; '
          'using ${fallback.inMinutes}min fallback',
        );
        expiresAt = DateTime.now().add(fallback);
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
  @override
  bool get needsRefresh {
    final current = state;
    return current is Authenticated && current.needsRefresh;
  }

  /// Refresh tokens if they are expiring soon.
  ///
  /// Call this proactively before making API requests to avoid 401s.
  /// Does nothing if not authenticated or tokens don't need refresh.
  /// On failure, logs and proceeds (request will use current token).
  @override
  Future<void> refreshIfExpiringSoon() async {
    if (needsRefresh) {
      final success = await tryRefresh();
      if (!success) {
        debugPrint('AuthNotifier: Proactive refresh failed');
      }
    }
  }

  /// Attempt to refresh the current tokens.
  ///
  /// Returns `true` if refresh succeeded, `false` if it failed.
  /// On invalid_grant (expired/revoked refresh token), clears auth state.
  /// On network errors, returns `false` without clearing state.
  @override
  Future<bool> tryRefresh() async {
    final current = state;
    if (current is! Authenticated) {
      return false;
    }

    if (current.refreshToken.isEmpty) {
      debugPrint('AuthNotifier: No refresh token available');
      return false;
    }

    final result = await _refreshService.refresh(
      discoveryUrl: current.issuerDiscoveryUrl,
      refreshToken: current.refreshToken,
      clientId: current.clientId,
    );

    switch (result) {
      case TokenRefreshSuccess():
        return _handleRefreshSuccess(result, current);

      case TokenRefreshFailure(reason: TokenRefreshFailureReason.invalidGrant):
        debugPrint('AuthNotifier: Refresh token expired, clearing auth state');
        await _clearAuthState();
        return false;

      case TokenRefreshFailure(reason: TokenRefreshFailureReason.networkError):
        debugPrint('AuthNotifier: Refresh failed due to network error');
        return false;

      case TokenRefreshFailure():
        debugPrint('AuthNotifier: Refresh failed');
        return false;
    }
  }

  Future<bool> _handleRefreshSuccess(
    TokenRefreshSuccess result,
    Authenticated current,
  ) async {
    // Preserve idToken through refresh (IdPs often don't return new one)
    final idToken = result.idToken ?? current.idToken;

    // Update storage
    try {
      await _storage.saveTokens(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        expiresAt: result.expiresAt,
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
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      expiresAt: result.expiresAt,
      issuerId: current.issuerId,
      issuerDiscoveryUrl: current.issuerDiscoveryUrl,
      clientId: current.clientId,
      idToken: idToken,
      userInfo: current.userInfo,
    );

    debugPrint('AuthNotifier: Token refresh successful');
    return true;
  }

  Future<void> _clearAuthState() async {
    try {
      await _storage.clearTokens();
    } on Exception catch (e) {
      debugPrint('AuthNotifier: Failed to clear tokens: $e');
    }
    state = const Unauthenticated();
  }
}
