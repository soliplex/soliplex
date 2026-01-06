import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_notifier.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';

/// Provider for secure token storage.
final authStorageProvider = Provider<AuthStorage>((ref) => AuthStorage());

/// Provider for token refresh service.
///
/// Uses the base HTTP client (without auth) to avoid circular dependencies
/// when refreshing tokens.
final tokenRefreshServiceProvider = Provider<TokenRefreshService>((ref) {
  final httpClient = ref.watch(baseHttpClientProvider);
  return TokenRefreshService(
    httpClient: httpClient,
    onDiagnostic: debugPrint,
  );
});

/// Provider for auth state and actions.
///
/// Manages OIDC authentication state. Use this to:
/// - Sign in with an OIDC provider
/// - Sign out
/// - Watch authentication status
///
/// Example:
/// ```dart
/// // Sign in
/// await ref.read(authProvider.notifier).signIn(provider);
///
/// // Watch state
/// final authState = ref.watch(authProvider);
/// if (authState is Authenticated) {
///   // User is logged in
/// }
/// ```
final authProvider =
    NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);

/// Provider indicating whether user is authenticated.
///
/// Example:
/// ```dart
/// final isLoggedIn = ref.watch(isAuthenticatedProvider);
/// ```
final isAuthenticatedProvider = Provider<bool>((ref) {
  final authState = ref.watch(authProvider);
  return authState is Authenticated;
});

/// Provider for the current access token.
///
/// Returns null if not authenticated.
final accessTokenProvider = Provider<String?>((ref) {
  final authState = ref.watch(authProvider);
  return authState is Authenticated ? authState.accessToken : null;
});

/// Listenable that fires only on auth status transitions (login/logout).
///
/// Use this with GoRouter's `refreshListenable` to trigger redirect
/// re-evaluation without recreating the router. Unlike watching
/// [authProvider] directly, this does NOT fire on token refresh.
///
/// This separation is critical: token refresh changes the auth state
/// (new tokens) but shouldn't cause navigation. Only actual login/logout
/// transitions should trigger route guards.
final authStatusListenableProvider = Provider<Listenable>((ref) {
  return _AuthStatusListenable(ref);
});

/// Notifies only when auth status transitions between authenticated/unauthenticated.
///
/// Filters out token refresh noise - when `Authenticated(oldTokens)` becomes
/// `Authenticated(newTokens)`, no notification fires because auth STATUS
/// (logged in vs logged out) hasn't changed.
class _AuthStatusListenable extends ChangeNotifier {
  _AuthStatusListenable(this._ref) {
    _previouslyAuthenticated = _isAuthenticated;
    _ref.listen<AuthState>(authProvider, (_, __) {
      final currentlyAuthenticated = _isAuthenticated;
      if (currentlyAuthenticated != _previouslyAuthenticated) {
        _previouslyAuthenticated = currentlyAuthenticated;
        notifyListeners();
      }
    });
  }

  final Ref _ref;
  late bool _previouslyAuthenticated;

  bool get _isAuthenticated => _ref.read(authProvider) is Authenticated;
}

/// Provider for fetching available OIDC issuers from the backend.
///
/// Uses core's [fetchAuthProviders] to get configured identity providers,
/// then wraps them in [OidcIssuer] for OIDC-specific functionality.
final oidcIssuersProvider = FutureProvider<List<OidcIssuer>>((ref) async {
  final config = ref.watch(configProvider);
  final transport = ref.watch(httpTransportProvider);

  final configs = await fetchAuthProviders(
    transport: transport,
    baseUrl: Uri.parse(config.baseUrl),
  );

  return configs.map(OidcIssuer.fromConfig).toList();
});
