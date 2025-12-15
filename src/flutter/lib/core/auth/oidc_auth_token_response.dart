import 'package:equatable/equatable.dart';

class OidcAuthTokenResponse extends Equatable {
  const OidcAuthTokenResponse({
    required this.idToken,
    required this.accessToken,
    required this.accessTokenExpiration,
    required this.refreshToken,
  });
  final String idToken;
  final String accessToken;
  final DateTime accessTokenExpiration;
  final String refreshToken;

  @override
  List<Object?> get props => [
    idToken,
    accessToken,
    accessTokenExpiration,
    refreshToken,
  ];
}
