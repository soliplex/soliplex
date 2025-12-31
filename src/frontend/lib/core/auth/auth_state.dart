import 'package:meta/meta.dart';

/// Authentication state for the application.
///
/// Uses sealed class pattern for exhaustive matching.
@immutable
sealed class AuthState {
  const AuthState();
}

/// User is not authenticated.
@immutable
class Unauthenticated extends AuthState {
  const Unauthenticated();

  @override
  bool operator ==(Object other) => other is Unauthenticated;

  @override
  int get hashCode => runtimeType.hashCode;
}

/// User is authenticated with valid tokens.
@immutable
class Authenticated extends AuthState {
  const Authenticated({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    required this.issuerId,
    required this.issuerDiscoveryUrl,
    this.idToken,
    this.userInfo,
  });

  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;
  final String issuerId;
  final String issuerDiscoveryUrl;
  final String? idToken;
  final Map<String, dynamic>? userInfo;

  /// Whether the access token has expired.
  bool get isExpired => DateTime.now().isAfter(expiresAt);

  /// Whether the access token needs refresh (within 1 minute of expiry).
  bool get needsRefresh => DateTime.now().isAfter(
        expiresAt.subtract(const Duration(minutes: 1)),
      );

  // userInfo excluded from equality: it's derived/optional data that may be
  // fetched lazily. Two auth states with same tokens are logically equal.
  @override
  bool operator ==(Object other) =>
      other is Authenticated &&
      other.accessToken == accessToken &&
      other.refreshToken == refreshToken &&
      other.expiresAt == expiresAt &&
      other.issuerId == issuerId &&
      other.issuerDiscoveryUrl == issuerDiscoveryUrl &&
      other.idToken == idToken;

  @override
  int get hashCode => Object.hash(
        accessToken,
        refreshToken,
        expiresAt,
        issuerId,
        issuerDiscoveryUrl,
        idToken,
      );
}

/// Authentication is being restored from storage.
@immutable
class AuthLoading extends AuthState {
  const AuthLoading();

  @override
  bool operator ==(Object other) => other is AuthLoading;

  @override
  int get hashCode => runtimeType.hashCode;
}
