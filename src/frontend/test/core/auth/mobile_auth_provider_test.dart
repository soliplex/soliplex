import 'dart:convert';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/mobile_auth_provider.dart';

class MockTokenStorage extends Mock implements TokenStorage {}

class MockFlutterAppAuth extends Mock implements FlutterAppAuth {}

class MockHttpClient extends Mock implements http.Client {}

class FakeAuthorizationTokenRequest extends Fake
    implements AuthorizationTokenRequest {}

class FakeTokenRequest extends Fake implements TokenRequest {}

class FakeEndSessionRequest extends Fake implements EndSessionRequest {}

class FakeUri extends Fake implements Uri {}

class FakeAuthToken extends Fake implements AuthToken {}

void main() {
  late MockTokenStorage mockStorage;
  late MockFlutterAppAuth mockAppAuth;
  late MockHttpClient mockHttpClient;
  late MobileAuthProvider provider;

  setUpAll(() {
    registerFallbackValue(FakeAuthorizationTokenRequest());
    registerFallbackValue(FakeTokenRequest());
    registerFallbackValue(FakeEndSessionRequest());
    registerFallbackValue(FakeUri());
    registerFallbackValue(FakeAuthToken());
  });

  setUp(() {
    mockStorage = MockTokenStorage();
    mockAppAuth = MockFlutterAppAuth();
    mockHttpClient = MockHttpClient();
    provider = MobileAuthProvider(
      tokenStorage: mockStorage,
      appAuth: mockAppAuth,
      httpClient: mockHttpClient,
    );
  });

  AuthToken createToken({
    String accessToken = 'access-123',
    String? refreshToken = 'refresh-456',
    DateTime? expiresAt,
    String? idToken,
  }) {
    return AuthToken(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: expiresAt ?? DateTime.now().add(const Duration(hours: 1)),
      idToken: idToken,
    );
  }

  SsoConfig createConfig({
    String? userInfoEndpoint,
    String? endSessionEndpoint,
  }) {
    return SsoConfig(
      authSystem: const OIDCAuthSystem(
        id: 'keycloak',
        title: 'Keycloak',
        serverUrl: 'https://auth.example.com',
        clientId: 'soliplex-client',
      ),
      authorizationEndpoint: 'https://auth.example.com/auth',
      tokenEndpoint: 'https://auth.example.com/token',
      endSessionEndpoint: endSessionEndpoint,
      userInfoEndpoint: userInfoEndpoint,
    );
  }

  AuthorizationTokenResponse createAuthResponse({
    String? accessToken = 'new-access',
    String? refreshToken = 'new-refresh',
    DateTime? expirationDateTime,
    String? idToken,
  }) {
    return AuthorizationTokenResponse(
      accessToken,
      refreshToken,
      expirationDateTime ?? DateTime.now().add(const Duration(hours: 1)),
      idToken,
      'Bearer',
      const <String>[],
      const <String, dynamic>{},
      const <String, dynamic>{},
    );
  }

  TokenResponse createTokenResponse({
    String? accessToken = 'refreshed-access',
    String? refreshToken = 'refreshed-refresh',
    DateTime? expirationDateTime,
    String? idToken,
  }) {
    return TokenResponse(
      accessToken,
      refreshToken,
      expirationDateTime ?? DateTime.now().add(const Duration(hours: 1)),
      idToken,
      'Bearer',
      const <String>[],
      const <String, dynamic>{},
    );
  }

  group('MobileAuthProvider', () {
    group('getValidToken', () {
      test('returns NoToken when no token stored', () async {
        final config = createConfig();
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => const TokenNotFound());

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<NoToken>());
      });

      test('returns Authenticated when token is valid', () async {
        final config = createConfig();
        final token = createToken();
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<Authenticated>());
        expect((result as Authenticated).token, equals(token));
      });

      test('returns TokenExpired when token expired without refresh token',
          () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
          refreshToken: null,
        );
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<TokenExpired>());
        verify(() => mockStorage.delete('server1')).called(1);
      });

      test('refreshes token when expired using provided config', () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
        );
        final refreshedResponse = createTokenResponse();

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(() => mockAppAuth.token(any()))
            .thenAnswer((_) async => refreshedResponse);
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<Authenticated>());
        final auth = result as Authenticated;
        expect(auth.token.accessToken, equals('refreshed-access'));
      });

      test('returns RefreshFailed when refresh throws exception', () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
        );

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(() => mockAppAuth.token(any()))
            .thenThrow(Exception('Refresh failed'));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<RefreshFailed>());
      });
    });

    group('login', () {
      test('calls authorizeAndExchangeCode with correct parameters', () async {
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenAnswer((_) async => createAuthResponse());
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        await provider.login('server1', config);

        final captured = verify(
          () => mockAppAuth.authorizeAndExchangeCode(captureAny()),
        ).captured.single as AuthorizationTokenRequest;

        expect(captured.clientId, equals('soliplex-client'));
        expect(captured.redirectUrl, equals('com.soliplex.app:/oauthredirect'));
        expect(captured.scopes, equals(['openid', 'profile', 'email']));
      });

      test('stores token on success', () async {
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenAnswer((_) async => createAuthResponse());
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final token = await provider.login('server1', config);

        expect(token.accessToken, equals('new-access'));
        verify(() => mockStorage.write('server1', any())).called(1);
      });

      test('throws AuthErrorCancelled when user cancels', () async {
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenThrow(
          FlutterAppAuthUserCancelledException(
            code: 'USER_CANCELLED',
            platformErrorDetails: FlutterAppAuthPlatformErrorDetails(),
          ),
        );

        expect(
          () => provider.login('server1', config),
          throwsA(isA<AuthErrorCancelled>()),
        );
      });

      test('throws AuthErrorConfiguration when accessToken is null', () async {
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenAnswer((_) async => createAuthResponse(accessToken: null));

        expect(
          () => provider.login('server1', config),
          throwsA(isA<AuthErrorConfiguration>()),
        );
      });

      test('throws AuthErrorNetwork on platform exception', () async {
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenThrow(
          FlutterAppAuthPlatformException(
            code: 'PLATFORM_ERROR',
            platformErrorDetails: FlutterAppAuthPlatformErrorDetails(),
          ),
        );

        expect(
          () => provider.login('server1', config),
          throwsA(isA<AuthErrorNetwork>()),
        );
      });

      test('throws AuthErrorNetwork on general exception', () async {
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenThrow(Exception('Network error'));

        expect(
          () => provider.login('server1', config),
          throwsA(isA<AuthErrorNetwork>()),
        );
      });

      test('uses custom redirect scheme', () async {
        final customProvider = MobileAuthProvider(
          tokenStorage: mockStorage,
          appAuth: mockAppAuth,
          httpClient: mockHttpClient,
          redirectScheme: 'com.custom.scheme',
        );
        final config = createConfig();
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenAnswer((_) async => createAuthResponse());
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        await customProvider.login('server1', config);

        final captured = verify(
          () => mockAppAuth.authorizeAndExchangeCode(captureAny()),
        ).captured.single as AuthorizationTokenRequest;

        expect(
          captured.redirectUrl,
          equals('com.custom.scheme:/oauthredirect'),
        );
      });
    });

    group('logout', () {
      test('deletes token from storage', () async {
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => const TokenNotFound());
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        await provider.logout('server1');

        verify(() => mockStorage.delete('server1')).called(1);
      });

      test('calls endSession when config and idToken available', () async {
        final config = createConfig(
          endSessionEndpoint: 'https://auth.example.com/logout',
        );
        final token = createToken(idToken: 'id-token-123');

        // Login to cache config
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenAnswer((_) async => createAuthResponse(idToken: 'id-token'));
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});
        await provider.login('server1', config);

        // Logout
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});
        when(() => mockAppAuth.endSession(any()))
            .thenAnswer((_) async => EndSessionResponse(''));

        await provider.logout('server1');

        verify(() => mockAppAuth.endSession(any())).called(1);
      });

      test('continues on endSession failure', () async {
        final config = createConfig(
          endSessionEndpoint: 'https://auth.example.com/logout',
        );
        final token = createToken(idToken: 'id-token-123');

        // Login to cache config
        when(() => mockAppAuth.authorizeAndExchangeCode(any()))
            .thenAnswer((_) async => createAuthResponse(idToken: 'id-token'));
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});
        await provider.login('server1', config);

        // Logout with endSession failure
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});
        when(() => mockAppAuth.endSession(any()))
            .thenThrow(Exception('End session failed'));

        // Should not throw
        await provider.logout('server1');

        verify(() => mockStorage.delete('server1')).called(1);
      });
    });

    group('getCurrentUser', () {
      test('throws AuthErrorNotAuthenticated when no token', () async {
        final config = createConfig(
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => const TokenNotFound());

        expect(
          () => provider.getCurrentUser('server1', config),
          throwsA(isA<AuthErrorNotAuthenticated>()),
        );
      });

      test('throws AuthErrorConfiguration when no userinfo endpoint', () async {
        final config = createConfig();
        final token = createToken();

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));

        expect(
          () => provider.getCurrentUser('server1', config),
          throwsA(isA<AuthErrorConfiguration>()),
        );
      });

      test('returns UserInfo on success', () async {
        final config = createConfig(
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );
        final token = createToken();

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockHttpClient.get(any(), headers: any(named: 'headers')))
            .thenAnswer(
          (_) async => http.Response(
            jsonEncode({
              'sub': 'user-123',
              'email': 'test@example.com',
              'name': 'Test User',
            }),
            200,
          ),
        );

        final user = await provider.getCurrentUser('server1', config);

        expect(user.id, equals('user-123'));
        expect(user.email, equals('test@example.com'));
        expect(user.name, equals('Test User'));
      });

      test('normalizes userinfo response with given_name/family_name',
          () async {
        final config = createConfig(
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );
        final token = createToken();

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockHttpClient.get(any(), headers: any(named: 'headers')))
            .thenAnswer(
          (_) async => http.Response(
            jsonEncode({
              'sub': 'user-456',
              'email': 'john@example.com',
              'given_name': 'John',
              'family_name': 'Doe',
            }),
            200,
          ),
        );

        final user = await provider.getCurrentUser('server1', config);

        expect(user.id, equals('user-456'));
        expect(user.name, equals('John Doe'));
      });

      test('throws AuthErrorServer on non-200 response', () async {
        final config = createConfig(
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );
        final token = createToken();

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockHttpClient.get(any(), headers: any(named: 'headers')))
            .thenAnswer(
          (_) async => http.Response('Unauthorized', 401),
        );

        expect(
          () => provider.getCurrentUser('server1', config),
          throwsA(isA<AuthErrorServer>()),
        );
      });

      test('throws AuthErrorNetwork on HTTP exception', () async {
        final config = createConfig(
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );
        final token = createToken();

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockHttpClient.get(any(), headers: any(named: 'headers')))
            .thenThrow(Exception('Connection refused'));

        expect(
          () => provider.getCurrentUser('server1', config),
          throwsA(isA<AuthErrorNetwork>()),
        );
      });

      test('includes Bearer token in Authorization header', () async {
        final config = createConfig(
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );
        final token = createToken(accessToken: 'my-access-token');

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));
        when(() => mockHttpClient.get(any(), headers: any(named: 'headers')))
            .thenAnswer(
          (_) async => http.Response(
            jsonEncode({'sub': 'user-123'}),
            200,
          ),
        );

        await provider.getCurrentUser('server1', config);

        final captured = verify(
          () => mockHttpClient.get(
            any(),
            headers: captureAny(named: 'headers'),
          ),
        ).captured.single as Map<String, String>;

        expect(captured['Authorization'], equals('Bearer my-access-token'));
      });
    });
  });
}
