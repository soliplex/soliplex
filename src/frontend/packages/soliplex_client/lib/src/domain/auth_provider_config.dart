import 'package:meta/meta.dart';

/// Authentication provider configuration from /api/login.
///
/// Represents an identity provider that can be used for authentication.
/// Core treats this as configuration data; frontends interpret it for
/// their specific auth flows (e.g., flutter_appauth for Flutter).
@immutable
class AuthProviderConfig {
  /// Creates an auth provider configuration.
  const AuthProviderConfig({
    required this.id,
    required this.name,
    required this.serverUrl,
    required this.clientId,
    required this.scope,
  });

  /// Unique identifier for the provider (e.g., "keycloak").
  final String id;

  /// Display name for the provider (e.g., "Authenticate with Keycloak").
  final String name;

  /// Identity provider server URL (e.g., "https://sso.domain.net/realms/app").
  final String serverUrl;

  /// OAuth client ID registered with the identity provider.
  final String clientId;

  /// OAuth scopes to request (space-separated, e.g., "openid email profile").
  final String scope;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AuthProviderConfig &&
        other.id == id &&
        other.name == name &&
        other.serverUrl == serverUrl &&
        other.clientId == clientId &&
        other.scope == scope;
  }

  @override
  int get hashCode => Object.hash(id, name, serverUrl, clientId, scope);

  @override
  String toString() => 'AuthProviderConfig(id: $id, name: $name)';
}
