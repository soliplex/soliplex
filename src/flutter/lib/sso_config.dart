class SsoConfig {
  const SsoConfig({
    required this.id,
    required this.title,
    required this.endpoint,
    required this.tokenEndpoint,
    required this.loginUrl,
    required this.clientId,
    required this.redirectUrl,
    required this.scopes,
  });

  SsoConfig.newEndpoint(Uri newLoginUrl, SsoConfig old)
    : id = old.id,
      title = old.title,
      endpoint = old.endpoint,
      tokenEndpoint = old.tokenEndpoint,
      loginUrl = newLoginUrl,
      clientId = old.clientId,
      redirectUrl = old.redirectUrl,
      scopes = old.scopes;

  final String id;
  final String title;
  final String endpoint;
  final String tokenEndpoint;
  final Uri loginUrl;
  final String clientId;
  final String redirectUrl;
  final List<String> scopes;
}
