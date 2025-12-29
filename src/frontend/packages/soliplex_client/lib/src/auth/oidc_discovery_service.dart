import 'package:soliplex_client/src/auth/auth_error.dart';
import 'package:soliplex_client/src/auth/oidc_auth_system.dart';
import 'package:soliplex_client/src/auth/sso_config.dart';
import 'package:soliplex_client/src/http/http_transport.dart';

/// Discovers OIDC configuration from a provider's well-known endpoint.
///
/// Fetches the OpenID Connect discovery document from
/// `{issuerUrl}/.well-known/openid-configuration` and parses it into
/// an [SsoConfig].
///
/// Example:
/// ```dart
/// final service = OidcDiscoveryService(transport: transport);
/// final config = await service.discover(authSystem);
/// ```
class OidcDiscoveryService {
  /// Creates an OIDC discovery service.
  OidcDiscoveryService({required HttpTransport transport})
      : _transport = transport;

  final HttpTransport _transport;

  /// Discovers OIDC configuration for the given [authSystem].
  ///
  /// Fetches the discovery document from the auth system's issuer URL
  /// and combines it with the auth system to create an [SsoConfig].
  ///
  /// Throws:
  /// - [AuthErrorNetwork] on connection failures or timeouts
  /// - [AuthErrorServer] if the discovery endpoint returns non-2xx
  /// - [AuthErrorConfiguration] if the document is invalid or missing
  ///   required fields
  Future<SsoConfig> discover(OIDCAuthSystem authSystem) async {
    final issuerUrl = Uri.parse(authSystem.serverUrl);
    final discoveryUrl = issuerUrl.resolve('.well-known/openid-configuration');

    final Map<String, dynamic> document;
    try {
      document = await _transport.request<Map<String, dynamic>>(
        'GET',
        discoveryUrl,
      );
    } on Exception catch (e, stack) {
      throw AuthErrorNetwork(
        message: 'Failed to fetch OIDC discovery document',
        originalError: e,
        stackTrace: stack,
      );
    }

    return _parseDiscoveryDocument(document, authSystem);
  }

  SsoConfig _parseDiscoveryDocument(
    Map<String, dynamic> document,
    OIDCAuthSystem authSystem,
  ) {
    final authorizationEndpoint =
        _extractString(document, 'authorization_endpoint');
    final tokenEndpoint = _extractString(document, 'token_endpoint');

    final missingFields = <String>[];
    if (authorizationEndpoint == null) {
      missingFields.add('authorization_endpoint');
    }
    if (tokenEndpoint == null) {
      missingFields.add('token_endpoint');
    }

    if (missingFields.isNotEmpty) {
      throw AuthErrorConfiguration(
        message: 'OIDC discovery document missing required fields: '
            '${missingFields.join(', ')}',
      );
    }

    return SsoConfig(
      authSystem: authSystem,
      authorizationEndpoint: authorizationEndpoint!,
      tokenEndpoint: tokenEndpoint!,
      endSessionEndpoint: _extractString(document, 'end_session_endpoint'),
      userInfoEndpoint: _extractString(document, 'userinfo_endpoint'),
    );
  }

  String? _extractString(Map<String, dynamic> document, String key) {
    final value = document[key];
    if (value == null) return null;
    if (value is! String) {
      throw AuthErrorConfiguration(
        message: 'OIDC discovery document field "$key" must be a string, '
            'got ${value.runtimeType}',
      );
    }
    return value;
  }
}
