import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_notifier.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';

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

/// Provider for fetching available OIDC issuers from the backend.
///
/// Uses core's [fetchAuthProviders] to get configured identity providers,
/// then wraps them in [OidcIssuer] for OIDC-specific functionality.
final oidcIssuersProvider =
    FutureProvider<List<OidcIssuer>>((ref) async {
  final config = ref.watch(configProvider);
  final transport = ref.watch(httpTransportProvider);

  final configs = await fetchAuthProviders(
    transport: transport,
    baseUrl: Uri.parse(config.baseUrl),
  );

  return configs.map(OidcIssuer.fromConfig).toList();
});
