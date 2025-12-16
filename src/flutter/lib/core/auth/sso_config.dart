import 'package:equatable/equatable.dart';

class SsoConfig extends Equatable {
  const SsoConfig({
    required this.id,
    required this.title,
    required this.endpoint,
    required this.tokenEndpoint,
    required this.loginUrl,
    required this.clientId,
    required this.redirectUrl,
    required this.scopes,
    this.serverBaseUrl,
  });

  SsoConfig.newEndpoint(Uri newLoginUrl, SsoConfig old)
    : id = old.id,
      title = old.title,
      endpoint = old.endpoint,
      tokenEndpoint = old.tokenEndpoint,
      loginUrl = newLoginUrl,
      clientId = old.clientId,
      redirectUrl = old.redirectUrl,
      scopes = old.scopes,
      serverBaseUrl = old.serverBaseUrl;

  final String id;
  final String title;
  final String endpoint;
  final String tokenEndpoint;
  final Uri loginUrl;
  final String clientId;
  final String redirectUrl;
  final List<String> scopes;

  /// The Soliplex backend server URL.
  ///
  /// Used for web authentication to redirect through the backend-mediated
  /// OAuth flow instead of directly to the OIDC provider.
  final String? serverBaseUrl;

  @override
  List<Object?> get props => [
    id,
    title,
    endpoint,
    tokenEndpoint,
    loginUrl,
    clientId,
    redirectUrl,
    scopes,
    serverBaseUrl,
  ];
}
