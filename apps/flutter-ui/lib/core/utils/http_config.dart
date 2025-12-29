/// Shared HTTP configuration constants.
///
/// Centralizes timeout values across all HTTP services to ensure
/// consistent behavior and easy tuning.
class HttpConfig {
  HttpConfig._();

  /// Default timeout for HTTP requests.
  ///
  /// Used by services that communicate with the Soliplex server.
  static const Duration defaultTimeout = Duration(seconds: 10);

  /// Timeout for server probing (discovery).
  ///
  /// Used by ServerRegistry when probing unknown servers.
  static const Duration probeTimeout = Duration(seconds: 10);

  /// Timeout for OIDC operations.
  ///
  /// Used by OidcWebAuthInteractor for token refresh and logout.
  static const Duration oidcTimeout = Duration(seconds: 10);

  /// Timeout for completions API probing.
  ///
  /// Used by CompletionsProbe when checking OpenAI-compatible endpoints.
  static const Duration completionsProbeTimeout = Duration(seconds: 10);
}
