/// Callback parameters extracted from the auth callback URL.
///
/// Two types of callbacks are supported:
/// - [BackendMediatedCallbackParams]: Tokens directly in URL (web flow)
/// - [PkceCallbackParams]: Authorization code and state (mobile/desktop flow)
sealed class CallbackParams {
  const CallbackParams();

  /// The error message if authentication failed.
  String? get error;

  /// Whether an error occurred.
  bool get hasError => error != null;
}

/// Callback parameters for backend-mediated OAuth flow.
///
/// The backend exchanges the authorization code for tokens and redirects
/// back with tokens in the URL query parameters.
///
/// Used on web to avoid CORS issues with direct token exchange.
class BackendMediatedCallbackParams extends CallbackParams {
  const BackendMediatedCallbackParams({
    this.accessToken,
    this.refreshToken,
    this.expiresIn,
    this.refreshExpiresIn,
    this.error,
  });

  /// The access token from the OIDC provider.
  final String? accessToken;

  /// The refresh token from the OIDC provider.
  final String? refreshToken;

  /// Token expiration in seconds.
  final int? expiresIn;

  /// Refresh token expiration in seconds.
  final int? refreshExpiresIn;

  @override
  final String? error;

  @override
  String toString() =>
      'BackendMediatedCallbackParams('
      'hasAccessToken: ${accessToken != null}, '
      'hasRefreshToken: ${refreshToken != null}, '
      'expiresIn: $expiresIn, '
      'error: $error)';
}

/// Callback parameters for PKCE OAuth flow.
///
/// The OIDC provider redirects back with an authorization code that
/// must be exchanged for tokens.
///
/// Used on mobile/desktop where native OAuth layers handle the exchange.
class PkceCallbackParams extends CallbackParams {
  const PkceCallbackParams({
    this.code,
    this.state,
    this.error,
  });

  /// The authorization code from the OIDC provider.
  final String? code;

  /// The state parameter for CSRF validation.
  final String? state;

  @override
  final String? error;

  @override
  String toString() =>
      'PkceCallbackParams('
      'hasCode: ${code != null}, '
      'hasState: ${state != null}, '
      'error: $error)';
}

/// No callback parameters detected.
///
/// Returned when the URL is not a callback URL or has no parameters.
class NoCallbackParams extends CallbackParams {
  const NoCallbackParams();

  @override
  String? get error => null;

  @override
  String toString() => 'NoCallbackParams()';
}
