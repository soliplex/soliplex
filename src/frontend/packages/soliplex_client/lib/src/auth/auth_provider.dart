import 'package:soliplex_client/src/auth/auth_error.dart';
import 'package:soliplex_client/src/auth/auth_result.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';
import 'package:soliplex_client/src/auth/sso_config.dart';
import 'package:soliplex_client/src/auth/user_info.dart';

/// Provider interface for authentication operations.
///
/// Implementations handle platform-specific OIDC flows:
/// - Mobile: PKCE flow with system browser or in-app browser
/// - Web: Backend-mediated flow with redirects
///
/// Each server is identified by a unique `serverId` string (typically the
/// server URL or a derived stable identifier), supporting multi-server
/// scenarios where users may connect to different backend instances.
abstract interface class AuthProvider {
  /// Returns the current authentication status with automatic token refresh.
  ///
  /// This method handles token lifecycle internally:
  /// 1. Checks for a stored token
  /// 2. If token needs refresh, attempts to refresh it
  /// 3. Returns the valid (possibly refreshed) token
  ///
  /// Returns [Authenticated] with a valid token if the user is logged in
  /// and the token is still valid or was successfully refreshed.
  ///
  /// Returns [NotAuthenticated] subtype for permanent auth failures:
  /// - [NoToken] if no token is stored
  /// - [TokenExpired] if token expired with no refresh token available
  /// - [RefreshFailed] if refresh was permanently rejected (e.g., refresh
  ///   token revoked, `invalid_grant` response). The [RefreshFailed.cause]
  ///   field contains the original error. Callers should redirect to login.
  ///
  /// Throws [AuthError] subtypes for transient, retryable errors:
  /// - [AuthErrorNetwork] for network timeouts or connectivity issues
  /// - [AuthErrorServer] for server errors (5xx) that may resolve on retry
  ///
  /// The distinction: permanent failures return [NotAuthenticated] because
  /// the only remedy is re-authentication. Transient failures throw because
  /// the caller may want to retry or show a different error message.
  Future<AuthResult> getValidToken(String serverId);

  /// Initiates the login flow for `serverId` using `config`.
  ///
  /// Returns [AuthToken] directly on success because login either succeeds
  /// or throws — there is no "not authenticated" case like with
  /// [getValidToken].
  ///
  /// Throws [AuthError] subtypes on failure:
  /// - [AuthErrorCancelled] if user cancelled the login
  /// - [AuthErrorNetwork] for network failures
  /// - [AuthErrorInvalidState] for CSRF validation failures
  /// - [AuthErrorServer] for server errors during token exchange
  /// - [AuthErrorConfiguration] for invalid configuration
  Future<AuthToken> login(String serverId, SsoConfig config);

  /// Logs out from `serverId`.
  ///
  /// Clears stored tokens and optionally performs OIDC end-session.
  ///
  /// Throws [AuthError] subtypes on failure:
  /// - [AuthErrorNetwork] if end-session request fails due to network issues
  /// - [AuthErrorServer] if the server rejects the logout request
  Future<void> logout(String serverId);

  /// Returns information about the current user for `serverId`.
  ///
  /// Requires the user to be authenticated. Call [getValidToken] first to
  /// verify authentication status.
  ///
  /// Throws [AuthErrorNotAuthenticated] if not logged in.
  /// Throws [AuthError] subtypes on fetch failures (e.g., network failure
  /// while fetching user info from the OIDC provider).
  Future<UserInfo> getCurrentUser(String serverId);
}
