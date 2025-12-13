import 'package:equatable/equatable.dart';

class OidcAuthTokenResponse extends Equatable {
  final String idToken;
  final String accessToken;
  final DateTime accessTokenExpiration;
  final String refreshToken;

  const OidcAuthTokenResponse({
    required this.idToken,
    required this.accessToken,
    required this.accessTokenExpiration,
    required this.refreshToken,
  });

  @override
  List<Object?> get props => [
    idToken,
    accessToken,
    accessTokenExpiration,
    refreshToken,
  ];
}
