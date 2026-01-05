import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/auth/auth_flow.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';

/// Notifier for managing authentication state.
///
/// Handles sign in, sign out, and session restoration.
///
/// Note: Currently calls [authenticate] and [endSession] directly, making
/// unit testing difficult. For testability, consider injecting an AuthFlow
/// interface. Accepted for MVP; manual testing covers auth flows.
class AuthNotifier extends Notifier<AuthState> {
  @override
  AuthState build() {
    return const Unauthenticated();
  }

  /// Sign in with the given OIDC issuer.
  ///
  /// Opens system browser for authentication, exchanges code for tokens.
  Future<void> signIn(OidcIssuer issuer) async {
    try {
      final result = await authenticate(issuer);

      state = Authenticated(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken ?? '',
        expiresAt: result.expiresAt ?? DateTime.now().add(
          const Duration(hours: 1),
        ),
        issuerId: issuer.id,
        issuerDiscoveryUrl: issuer.discoveryUrl,
        idToken: result.idToken,
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
  /// local state. If endSession fails, local logout still proceeds.
  Future<void> signOut() async {
    final current = state;
    if (current is Authenticated) {
      await endSession(
        discoveryUrl: current.issuerDiscoveryUrl,
        idToken: current.idToken,
      );
    }
    state = const Unauthenticated();
  }

  /// Get the current access token if authenticated.
  String? get accessToken {
    final current = state;
    return current is Authenticated ? current.accessToken : null;
  }
}
