import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';

/// AuthProvider implementation for mobile platforms using PKCE flow.
///
/// Uses flutter_appauth for native OAuth handling on iOS, Android, and macOS.
/// Tokens are persisted via the injected [TokenStorage].
class MobileAuthProvider implements AuthProvider {
  /// Creates a mobile auth provider.
  ///
  /// The [redirectScheme] is used to construct the redirect URI for OAuth
  /// callbacks. The path `/oauthredirect` is appended automatically.
  /// Platform configurations (Info.plist, AndroidManifest.xml) must register
  /// this scheme.
  MobileAuthProvider({
    required TokenStorage tokenStorage,
    required FlutterAppAuth appAuth,
    required http.Client httpClient,
    String redirectScheme = 'com.soliplex.app',
  })  : _tokenStorage = tokenStorage,
        _tokenValidator = TokenValidator(tokenStorage: tokenStorage),
        _appAuth = appAuth,
        _userInfoFetcher = UserInfoFetcher(
          tokenStorage: tokenStorage,
          httpClient: httpClient,
        ),
        _redirectUri = '$redirectScheme:/oauthredirect';

  final TokenStorage _tokenStorage;
  final TokenValidator _tokenValidator;
  final FlutterAppAuth _appAuth;
  final UserInfoFetcher _userInfoFetcher;
  final String _redirectUri;

  @override
  Future<AuthResult> getValidToken(String serverId, SsoConfig config) =>
      _tokenValidator.getValidToken(
        serverId,
        onRefresh: (token) => _attemptRefresh(token, config),
      );

  @override
  Future<LoginResult> login(String serverId, SsoConfig config) async {
    final AuthorizationTokenResponse response;
    try {
      response = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          config.clientId,
          _redirectUri,
          serviceConfiguration: AuthorizationServiceConfiguration(
            authorizationEndpoint: config.authorizationEndpoint,
            tokenEndpoint: config.tokenEndpoint,
            endSessionEndpoint: config.endSessionEndpoint,
          ),
          scopes: config.scope.split(' '),
        ),
      );
    } on FlutterAppAuthUserCancelledException {
      throw const AuthErrorCancelled();
    } on FlutterAppAuthPlatformException catch (e, st) {
      throw AuthErrorNetwork(
        message: 'Authorization request failed: ${e.message}',
        originalError: e,
        stackTrace: st,
      );
    }
    // No generic Exception catch: flutter_appauth only throws
    // FlutterAppAuthUserCancelledException and FlutterAppAuthPlatformException.
    // Any other exception indicates a bug that should propagate.

    final token = _tokenFromResponse(response);
    await _tokenStorage.write(serverId, token);
    return LoginSuccess(token);
  }

  @override
  Future<void> logout(String serverId, SsoConfig config) async {
    final result = await _tokenStorage.read(serverId);

    if (result case TokenFound(:final token)) {
      final idToken = token.idToken;
      final endSessionEndpoint = config.endSessionEndpoint;

      if (endSessionEndpoint != null && idToken != null) {
        try {
          await _appAuth.endSession(
            EndSessionRequest(
              idTokenHint: idToken,
              postLogoutRedirectUrl: _redirectUri,
              serviceConfiguration: AuthorizationServiceConfiguration(
                authorizationEndpoint: config.authorizationEndpoint,
                tokenEndpoint: config.tokenEndpoint,
                endSessionEndpoint: endSessionEndpoint,
              ),
            ),
          );
        } on Exception catch (e) {
          // Remote end-session failed; local cleanup will proceed.
          debugPrint('End session failed for $serverId: $e');
        }
      }
    }

    await _tokenStorage.delete(serverId);
  }

  @override
  Future<UserInfo> getCurrentUser(String serverId, SsoConfig config) =>
      _userInfoFetcher.fetch(serverId, config);

  Future<RefreshResult> _attemptRefresh(
    AuthToken token,
    SsoConfig config,
  ) async {
    try {
      final response = await _appAuth.token(
        TokenRequest(
          config.clientId,
          _redirectUri,
          refreshToken: token.refreshToken,
          serviceConfiguration: AuthorizationServiceConfiguration(
            authorizationEndpoint: config.authorizationEndpoint,
            tokenEndpoint: config.tokenEndpoint,
            endSessionEndpoint: config.endSessionEndpoint,
          ),
        ),
      );

      return RefreshSuccess(_tokenFromResponse(response));
    } on FlutterAppAuthPlatformException catch (e) {
      return RefreshRejected('Token refresh failed: ${e.message}');
    }
    // No generic Exception catch: _appAuth.token() only throws
    // FlutterAppAuthPlatformException. Any other exception indicates a bug.
  }

  AuthToken _tokenFromResponse(TokenResponse response) {
    final accessToken = response.accessToken;
    if (accessToken == null) {
      throw const AuthErrorConfiguration(
        message: 'No access token in authorization response',
      );
    }

    final expiresAt = response.accessTokenExpirationDateTime;
    if (expiresAt == null) {
      throw const AuthErrorConfiguration(
        message: 'No expiration time in authorization response',
      );
    }

    return AuthToken(
      accessToken: accessToken,
      refreshToken: response.refreshToken,
      // Normalize to UTC for consistent comparison across timezones.
      // flutter_appauth returns local time; WebAuthProvider also uses UTC.
      expiresAt: expiresAt.toUtc(),
      idToken: response.idToken,
    );
  }
}
