import 'package:meta/meta.dart';

/// Represents an OAuth token with access and optional refresh tokens.
///
/// This is a value object where equality is based on all fields.
@immutable
class AuthToken {
  /// Creates an auth token.
  const AuthToken({
    required this.accessToken,
    required this.expiresAt,
    this.refreshToken,
    this.idToken,
  });

  /// Creates an auth token from JSON.
  factory AuthToken.fromJson(Map<String, dynamic> json) {
    return AuthToken(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String?,
      expiresAt: DateTime.parse(json['expires_at'] as String),
      idToken: json['id_token'] as String?,
    );
  }

  /// Default buffer before expiry to trigger refresh (5 minutes).
  static const Duration defaultRefreshBuffer = Duration(minutes: 5);

  /// The OAuth access token.
  final String accessToken;

  /// The OAuth refresh token, if provided.
  final String? refreshToken;

  /// When the access token expires.
  final DateTime expiresAt;

  /// The OpenID Connect ID token, if provided.
  final String? idToken;

  /// Whether the token has expired.
  bool get isExpired => DateTime.now().toUtc().isAfter(expiresAt);

  /// Whether the token needs to be refreshed using [defaultRefreshBuffer].
  ///
  /// Use [needsRefreshWithin] for a custom buffer duration.
  bool get needsRefresh => needsRefreshWithin(defaultRefreshBuffer);

  /// Whether the token needs to be refreshed within the given [buffer].
  ///
  /// Returns true if the token will expire within [buffer] duration.
  bool needsRefreshWithin(Duration buffer) {
    final now = DateTime.now().toUtc();
    final refreshThreshold = expiresAt.subtract(buffer);
    return now.isAfter(refreshThreshold);
  }

  /// Whether the token can be refreshed (has a refresh token).
  bool get canRefresh => refreshToken != null;

  /// Creates a copy of this token with the given fields replaced.
  AuthToken copyWith({
    String? accessToken,
    String? refreshToken,
    DateTime? expiresAt,
    String? idToken,
  }) {
    return AuthToken(
      accessToken: accessToken ?? this.accessToken,
      refreshToken: refreshToken ?? this.refreshToken,
      expiresAt: expiresAt ?? this.expiresAt,
      idToken: idToken ?? this.idToken,
    );
  }

  /// Converts this token to JSON.
  Map<String, dynamic> toJson() {
    return {
      'access_token': accessToken,
      if (refreshToken != null) 'refresh_token': refreshToken,
      'expires_at': expiresAt.toUtc().toIso8601String(),
      if (idToken != null) 'id_token': idToken,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AuthToken &&
        other.accessToken == accessToken &&
        other.refreshToken == refreshToken &&
        other.expiresAt == expiresAt &&
        other.idToken == idToken;
  }

  @override
  int get hashCode =>
      Object.hash(accessToken, refreshToken, expiresAt, idToken);

  @override
  String toString() => 'AuthToken(expiresAt: $expiresAt, '
      'hasRefreshToken: $canRefresh, isExpired: $isExpired)';
}
