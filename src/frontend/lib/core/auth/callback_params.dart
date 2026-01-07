/// Callback parameters extracted from the auth callback URL.
///
/// Two types of callbacks are supported:
/// - [WebCallbackParams]: Tokens directly in URL (web BFF flow)
/// - [NoCallbackParams]: No callback detected
sealed class CallbackParams {
  const CallbackParams();

  /// The error message if authentication failed.
  String? get error;

  /// Whether an error occurred.
  bool get hasError => error != null;
}

/// Callback parameters for web BFF OAuth flow.
///
/// The backend exchanges the authorization code for tokens and redirects
/// back with tokens in the URL query parameters.
class WebCallbackParams extends CallbackParams {
  const WebCallbackParams({
    this.accessToken,
    this.refreshToken,
    this.expiresIn,
    this.error,
    this.errorDescription,
  });

  /// The access token from the OIDC provider.
  final String? accessToken;

  /// The refresh token from the OIDC provider.
  final String? refreshToken;

  /// Token expiration in seconds.
  final int? expiresIn;

  @override
  final String? error;

  /// Additional error description from OAuth.
  final String? errorDescription;

  @override
  String toString() =>
      'WebCallbackParams('
      'hasAccessToken: ${accessToken != null}, '
      'hasRefreshToken: ${refreshToken != null}, '
      'expiresIn: $expiresIn, '
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
