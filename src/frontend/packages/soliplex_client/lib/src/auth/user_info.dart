import 'package:meta/meta.dart';
import 'package:soliplex_client/src/auth/auth_error.dart';

/// Represents authenticated user information.
///
/// This is a value object where equality is based on all fields,
/// not just the id. Two UserInfo instances with the same id but
/// different names are considered different values.
@immutable
class UserInfo {
  /// Creates user info.
  const UserInfo({
    required this.id,
    this.email,
    this.name,
  });

  /// Creates user info from JSON.
  factory UserInfo.fromJson(Map<String, dynamic> json) {
    return UserInfo(
      id: json['id'] as String,
      email: json['email'] as String?,
      name: json['name'] as String?,
    );
  }

  /// Creates user info from OIDC userinfo endpoint claims.
  ///
  /// Normalizes different OIDC provider claim formats:
  /// - `sub` or `id` → [id]
  /// - `name` or `given_name`+`family_name` → [name]
  /// - `email` → [email]
  ///
  /// Throws [AuthErrorConfiguration] if neither `sub` nor `id` claim exists
  /// or if the value is empty.
  factory UserInfo.fromOidcClaims(Map<String, dynamic> claims) {
    final givenName = claims['given_name'] as String?;
    final familyName = claims['family_name'] as String?;

    var name = claims['name'] as String?;
    if (name == null && (givenName != null || familyName != null)) {
      name = [givenName, familyName].whereType<String>().join(' ').trim();
      if (name.isEmpty) name = null;
    }

    final id = claims['sub'] as String? ?? claims['id'] as String?;
    if (id == null || id.isEmpty) {
      throw const AuthErrorConfiguration(
        message: 'Userinfo response missing required "sub" or "id" claim',
      );
    }

    return UserInfo(
      id: id,
      email: claims['email'] as String?,
      name: name,
    );
  }

  /// Unique identifier for the user.
  final String id;

  /// User's email address, if available.
  final String? email;

  /// User's display name, if available.
  final String? name;

  /// Display name, falling back to email then id.
  String get displayName => name ?? email ?? id;

  /// Creates a copy of this user info with the given fields replaced.
  UserInfo copyWith({
    String? id,
    String? email,
    String? name,
  }) {
    return UserInfo(
      id: id ?? this.id,
      email: email ?? this.email,
      name: name ?? this.name,
    );
  }

  /// Converts this user info to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      if (email != null) 'email': email,
      if (name != null) 'name': name,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is UserInfo &&
        other.id == id &&
        other.email == email &&
        other.name == name;
  }

  @override
  int get hashCode => Object.hash(id, email, name);

  @override
  String toString() => 'UserInfo(id: $id)';
}
