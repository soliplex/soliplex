import 'package:meta/meta.dart';

/// OIDC authentication system configuration from the backend.
///
/// This is the wire format returned by `GET /api/login`.
///
/// This is a value object where equality is based on all fields.
/// Two configs with the same id but different client IDs are different.
@immutable
class OIDCAuthSystem {
  /// Creates an OIDC auth system.
  const OIDCAuthSystem({
    required this.id,
    required this.title,
    required this.serverUrl,
    required this.clientId,
    this.scope = 'openid profile email',
  });

  /// Creates an OIDC auth system from JSON.
  factory OIDCAuthSystem.fromJson(Map<String, dynamic> json) {
    return OIDCAuthSystem(
      id: json['id'] as String,
      title: json['title'] as String,
      serverUrl: json['server_url'] as String,
      clientId: json['client_id'] as String,
      scope: json['scope'] as String? ?? 'openid profile email',
    );
  }

  /// Unique identifier for this auth system.
  final String id;

  /// Display title for the login button.
  final String title;

  /// OIDC server URL (issuer).
  final String serverUrl;

  /// OAuth client ID.
  final String clientId;

  /// OAuth scopes to request.
  final String scope;

  /// Creates a copy with the given fields replaced.
  OIDCAuthSystem copyWith({
    String? id,
    String? title,
    String? serverUrl,
    String? clientId,
    String? scope,
  }) {
    return OIDCAuthSystem(
      id: id ?? this.id,
      title: title ?? this.title,
      serverUrl: serverUrl ?? this.serverUrl,
      clientId: clientId ?? this.clientId,
      scope: scope ?? this.scope,
    );
  }

  /// Converts to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'server_url': serverUrl,
      'client_id': clientId,
      'scope': scope,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is OIDCAuthSystem &&
        other.id == id &&
        other.title == title &&
        other.serverUrl == serverUrl &&
        other.clientId == clientId &&
        other.scope == scope;
  }

  @override
  int get hashCode => Object.hash(id, title, serverUrl, clientId, scope);

  @override
  String toString() => 'OIDCAuthSystem(id: $id, title: $title)';
}
