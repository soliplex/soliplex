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
  /// Returns a valid access token for the given server.
  ///
  /// If a valid token exists in storage, returns it. If the token is expired
  /// but a refresh token is available, attempts to refresh using [config].
  ///
  /// The [config] must match the configuration used during [login] for this
  /// [serverId]. Passing a different configuration has undefined behavior.
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
  Future<AuthResult> getValidToken(String serverId, SsoConfig config);

  /// Authenticates with the OIDC provider and stores tokens.
  ///
  /// Opens a browser for user authentication via the authorization code flow.
  /// On success, stores tokens keyed by [serverId] and caches [config] for
  /// logout operations.
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

  /// Ends the session and clears stored tokens.
  ///
  /// Uses the cached [SsoConfig] from the prior [login] call to locate the
  /// end-session endpoint. If no config is cached (e.g., app restart),
  /// clears local tokens without server-side session termination.
  ///
  /// Never throws. Remote logout failures are logged but not propagated
  /// since local cleanup is sufficient for security purposes.
  Future<void> logout(String serverId);

  /// Retrieves user information from the OIDC provider.
  ///
  /// Uses [config] to locate the userinfo endpoint. Requires a valid token
  /// for [serverId].
  ///
  /// Throws [AuthErrorNotAuthenticated] if not logged in.
  /// Throws [AuthErrorConfiguration] if [config] has no userinfo endpoint.
  /// Throws [AuthError] subtypes on fetch failures (e.g., network failure
  /// while fetching user info from the OIDC provider).
  Future<UserInfo> getCurrentUser(String serverId, SsoConfig config);
}
