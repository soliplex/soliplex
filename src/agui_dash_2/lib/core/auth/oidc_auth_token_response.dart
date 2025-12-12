class OidcAuthTokenResponse {
  final String idToken;
  final String accessToken;
  final DateTime accessTokenExpiration;
  final String refreshToken;

  OidcAuthTokenResponse({
    required this.idToken,
    required this.accessToken,
    required this.accessTokenExpiration,
    required this.refreshToken,
  });
}
