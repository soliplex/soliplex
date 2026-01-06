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

  void _log(String message) => debugPrint('AuthNotifier: $message');

  @override
  AuthState build() {
    _storage = ref.read(authStorageProvider);
    _refreshService = ref.read(tokenRefreshServiceProvider);

    // Fire-and-forget: _restoreSession runs async while we return AuthLoading.
    // Any refresh calls during restore fail gracefully (state is not
    // Authenticated yet) and will succeed after restore completes.
    // Defense-in-depth: catch any unhandled errors to avoid silent failures.
    _restoreSession().catchError(
      (Object e) => _log('Unhandled restore error: ${e.runtimeType}'),
    );
    return const AuthLoading();
  }

  Future<void> _restoreSession() async {
    final Authenticated? tokens;
    try {
      tokens = await _storage.loadTokens();
    } on Exception catch (e) {
      // Storage unavailable (keychain locked, permissions, corruption)
      // Policy: treat as unauthenticated rather than stuck in loading
      _log('Failed to restore session: ${e.runtimeType}');
      state = const Unauthenticated();
      return;
    }

    if (tokens == null) {
      state = const Unauthenticated();
      return;
    }

    // Check if tokens are expired - attempt refresh before clearing
    if (tokens.isExpired) {
      _log('Stored tokens expired, attempting refresh');
      final refreshed = await _tryRefreshStoredTokens(tokens);
      if (refreshed) {
        return;
      }
      // Refresh failed - clear and require re-login
      try {
        await _storage.clearTokens();
      } on Exception catch (e) {
        _log('Failed to clear expired tokens: ${e.runtimeType}');
      }
      state = const Unauthenticated();
      return;
    }

    // Tokens already persisted—assign directly to state.
    state = tokens;
  }

  /// Attempt to refresh expired stored tokens during session restore.
  ///
  /// Returns `true` if refresh succeeded and state was updated
  /// (even if storage persistence failed—session works but won't survive
  /// restart).
  /// Returns `false` if refresh failed (caller should clear and logout).
  ///
  /// ## Failure Handling Policy (Startup vs Runtime)
  ///
  /// This method treats ALL failures the same (return false → logout), unlike
  /// [tryRefresh] which distinguishes between failure types. This asymmetry
  /// is intentional:
  ///
  /// **At startup:** We're trying to *establish* trust from stored credentials.
  /// If we can't validate tokens (for any reason—network, revoked, etc.), we
  /// have nothing useful. Failing fast with "please log in" is clearer than
  /// pretending auth succeeded when we can't verify it.
  ///
  /// **At runtime:** We already established trust. A transient network error
  /// shouldn't destroy a valid session. The user stays "authenticated" in
  /// local state and can retry when network returns.
  ///
  /// See OIDC spec section "Token Refresh Failure Handling Policy" for details.
  Future<bool> _tryRefreshStoredTokens(Authenticated tokens) async {
    final TokenRefreshResult result;
    try {
      result = await _refreshService.refresh(
        discoveryUrl: tokens.issuerDiscoveryUrl,
        refreshToken: tokens.refreshToken,
        clientId: tokens.clientId,
      );
    } on Exception catch (e) {
      _log('Refresh during restore threw: ${e.runtimeType}');
      return false;
    }

    if (result is! TokenRefreshSuccess) {
      final failure = result as TokenRefreshFailure;
      _log('Refresh during restore failed: ${failure.reason}');
      return false;
    }

    await _applyRefreshResult(
      result,
      issuerId: tokens.issuerId,
      issuerDiscoveryUrl: tokens.issuerDiscoveryUrl,
      clientId: tokens.clientId,
      fallbackIdToken: tokens.idToken,
    );

    _log('Session restored via token refresh');
    return true;
  }

  /// Apply a successful token refresh result to storage and state.
  ///
  /// Preserves idToken if the IdP didn't return a new one (per OIDC Core 1.0
  /// Section 12.2). Attempts to persist to storage but continues on failure
  /// (session works for current app run).
  Future<void> _applyRefreshResult(
    TokenRefreshSuccess result, {
    required String issuerId,
    required String issuerDiscoveryUrl,
    required String clientId,
    required String fallbackIdToken,
  }) async {
    final newState = Authenticated(
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      expiresAt: result.expiresAt,
      issuerId: issuerId,
      issuerDiscoveryUrl: issuerDiscoveryUrl,
      clientId: clientId,
      idToken: result.idToken ?? fallbackIdToken,
    );

    try {
      await _storage.saveTokens(newState);
    } on Exception catch (e) {
      _log('Failed to persist refreshed tokens: ${e.runtimeType}');
    }

    state = newState;
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
        _log(
          'Token response missing expires_in; '
          'using ${fallback.inMinutes}min fallback',
        );
        expiresAt = DateTime.now().add(fallback);
      }

      final newState = Authenticated(
        accessToken: accessToken,
        refreshToken: refreshToken,
        expiresAt: expiresAt,
        issuerId: issuer.id,
        issuerDiscoveryUrl: issuer.discoveryUrl,
        clientId: issuer.clientId,
        idToken: idToken,
      );

      // Save tokens to secure storage (may fail on unsigned macOS builds)
      try {
        await _storage.saveTokens(newState);
      } on Exception catch (e) {
        _log('Failed to persist tokens: ${e.runtimeType}');
        // Continue - auth works, just won't persist across restarts
      }

      state = newState;
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
      _log('Failed to clear tokens on logout: ${e.runtimeType}');
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
        _log('Proactive refresh failed');
      }
    }
  }

  /// Attempt to refresh the current tokens (runtime refresh).
  ///
  /// Returns `true` if refresh succeeded, `false` if it failed.
  ///
  /// Failure handling depends on the reason:
  /// - `invalidGrant`: Refresh token revoked/expired → clears auth state (logout)
  /// - `networkError`: Transient failure → preserves session, caller can retry
  /// - `noRefreshToken`: No token available → preserves session
  ///
  /// This is more lenient than [_tryRefreshStoredTokens] because at runtime we
  /// have an established session worth preserving through transient failures.
  ///
  /// See OIDC spec section "Token Refresh Failure Handling Policy" for details.
  @override
  Future<bool> tryRefresh() async {
    final current = state;
    if (current is! Authenticated) {
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

      case TokenRefreshFailure(
            reason: TokenRefreshFailureReason.noRefreshToken,
          ):
        _log('No refresh token available');
        return false;

      case TokenRefreshFailure(reason: TokenRefreshFailureReason.invalidGrant):
        _log('Refresh token expired, clearing auth state');
        await _clearAuthState();
        return false;

      case TokenRefreshFailure(reason: TokenRefreshFailureReason.networkError):
        _log('Refresh failed due to network error');
        return false;

      case TokenRefreshFailure():
        _log('Refresh failed');
        return false;
    }
  }

  Future<bool> _handleRefreshSuccess(
    TokenRefreshSuccess result,
    Authenticated current,
  ) async {
    await _applyRefreshResult(
      result,
      issuerId: current.issuerId,
      issuerDiscoveryUrl: current.issuerDiscoveryUrl,
      clientId: current.clientId,
      fallbackIdToken: current.idToken,
    );

    _log('Token refresh successful');
    return true;
  }

  Future<void> _clearAuthState() async {
    try {
      await _storage.clearTokens();
    } on Exception catch (e) {
      _log('Failed to clear tokens: ${e.runtimeType}');
    }
    state = const Unauthenticated();
  }
}
