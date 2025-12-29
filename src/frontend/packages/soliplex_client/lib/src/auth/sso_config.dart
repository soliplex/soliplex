import 'package:meta/meta.dart';

import 'package:soliplex_client/src/auth/oidc_auth_system.dart';

/// Full OIDC configuration after discovery.
///
/// Contains the original [OIDCAuthSystem] plus discovered endpoints.
///
/// This is a value object where equality is based on all fields.
@immutable
class SsoConfig {
  /// Creates an SSO config.
  const SsoConfig({
    required this.authSystem,
    required this.authorizationEndpoint,
    required this.tokenEndpoint,
    this.endSessionEndpoint,
    this.userInfoEndpoint,
  });

  /// Creates an SSO config from JSON.
  factory SsoConfig.fromJson(Map<String, dynamic> json) {
    return SsoConfig(
      authSystem: OIDCAuthSystem.fromJson(
        json['auth_system'] as Map<String, dynamic>,
      ),
      authorizationEndpoint: json['authorization_endpoint'] as String,
      tokenEndpoint: json['token_endpoint'] as String,
      endSessionEndpoint: json['end_session_endpoint'] as String?,
      userInfoEndpoint: json['userinfo_endpoint'] as String?,
    );
  }

  /// The original auth system configuration.
  final OIDCAuthSystem authSystem;

  /// OAuth authorization endpoint.
  final String authorizationEndpoint;

  /// OAuth token endpoint.
  final String tokenEndpoint;

  /// OIDC end session endpoint for logout.
  final String? endSessionEndpoint;

  /// OIDC userinfo endpoint.
  final String? userInfoEndpoint;

  /// Auth system identifier.
  String get id => authSystem.id;

  /// OAuth client ID.
  String get clientId => authSystem.clientId;

  /// OAuth scopes.
  String get scope => authSystem.scope;

  /// Creates a copy with the given fields replaced.
  SsoConfig copyWith({
    OIDCAuthSystem? authSystem,
    String? authorizationEndpoint,
    String? tokenEndpoint,
    String? endSessionEndpoint,
    String? userInfoEndpoint,
  }) {
    return SsoConfig(
      authSystem: authSystem ?? this.authSystem,
      authorizationEndpoint:
          authorizationEndpoint ?? this.authorizationEndpoint,
      tokenEndpoint: tokenEndpoint ?? this.tokenEndpoint,
      endSessionEndpoint: endSessionEndpoint ?? this.endSessionEndpoint,
      userInfoEndpoint: userInfoEndpoint ?? this.userInfoEndpoint,
    );
  }

  /// Converts to JSON.
  Map<String, dynamic> toJson() {
    return {
      'auth_system': authSystem.toJson(),
      'authorization_endpoint': authorizationEndpoint,
      'token_endpoint': tokenEndpoint,
      if (endSessionEndpoint != null)
        'end_session_endpoint': endSessionEndpoint,
      if (userInfoEndpoint != null) 'userinfo_endpoint': userInfoEndpoint,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is SsoConfig &&
        other.authSystem == authSystem &&
        other.authorizationEndpoint == authorizationEndpoint &&
        other.tokenEndpoint == tokenEndpoint &&
        other.endSessionEndpoint == endSessionEndpoint &&
        other.userInfoEndpoint == userInfoEndpoint;
  }

  @override
  int get hashCode => Object.hash(
        authSystem,
        authorizationEndpoint,
        tokenEndpoint,
        endSessionEndpoint,
        userInfoEndpoint,
      );

  @override
  String toString() => 'SsoConfig(id: $id)';
}
