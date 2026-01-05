import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// OIDC issuer configuration for Flutter frontend.
///
/// Wraps [AuthProviderConfig] from core and adds OIDC-specific
/// functionality like discovery URL derivation.
@immutable
class OidcIssuer {
  /// Creates an OIDC issuer from core's [AuthProviderConfig].
  const OidcIssuer.fromConfig(this._config);

  final AuthProviderConfig _config;

  /// Unique identifier for the issuer.
  String get id => _config.id;

  /// Display name for the issuer.
  String get title => _config.name;

  /// Identity provider server URL.
  String get serverUrl => _config.serverUrl;

  /// OAuth client ID.
  String get clientId => _config.clientId;

  /// OAuth scopes (space-separated).
  String get scope => _config.scope;

  /// OIDC discovery URL for this issuer.
  String get discoveryUrl => '$serverUrl/.well-known/openid-configuration';

  @override
  bool operator ==(Object other) =>
      other is OidcIssuer && other._config == _config;

  @override
  int get hashCode => _config.hashCode;
}
