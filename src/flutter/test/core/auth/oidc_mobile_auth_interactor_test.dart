import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/auth/oidc_auth_interactor.dart';
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_sso_storage.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/sso_config.dart';

class MockFlutterAppAuth extends Mock implements FlutterAppAuth {}

class MockSecureSsoStorage extends Mock implements SecureSsoStorage {}

class MockSecureTokenStorage extends Mock implements SecureTokenStorage {}

void main() {
  late MockFlutterAppAuth mockAppAuth;
  late MockSecureSsoStorage mockSsoStorage;
  late MockSecureTokenStorage mockTokenStorage;
  late OidcMobileAuthInteractor interactor;

  const testServerId = 'server-123';

  SsoConfig createConfig() {
    return SsoConfig(
      id: 'keycloak',
      title: 'Sign in with Keycloak',
      endpoint: 'https://auth.example.com/realms/myrealm',
      tokenEndpoint:
          'https://auth.example.com/realms/myrealm/protocol/openid-connect/token',
      loginUrl: Uri.parse(
        'https://auth.example.com/realms/myrealm/protocol/openid-connect/auth',
      ),
      clientId: 'my-client',
      redirectUrl: 'ai.soliplex.client://callback',
      scopes: ['openid', 'profile', 'email'],
    );
  }

  OidcAuthTokenResponse createTokenResponse({
    DateTime? expiration,
  }) {
    return OidcAuthTokenResponse(
      idToken: 'test-id-token',
      accessToken: 'test-access-token',
      accessTokenExpiration:
          expiration ??
          DateTime.now().add(
            const Duration(hours: 1),
          ),
      refreshToken: 'test-refresh-token',
    );
  }

  setUp(() {
    mockAppAuth = MockFlutterAppAuth();
    mockSsoStorage = MockSecureSsoStorage();
    mockTokenStorage = MockSecureTokenStorage();
    interactor = OidcMobileAuthInteractor(
      mockAppAuth,
      mockSsoStorage,
      mockTokenStorage,
      const Duration(minutes: 5),
    );
  });

  setUpAll(() {
    registerFallbackValue(
      AuthorizationTokenRequest(
        'client-id',
        'redirect-url',
        issuer: 'issuer',
        scopes: [],
      ),
    );
    registerFallbackValue(
      TokenRequest(
        'client-id',
        'redirect-url',
        issuer: 'issuer',
        scopes: [],
      ),
    );
    registerFallbackValue(
      EndSessionRequest(
        idTokenHint: 'fallback-id-token',
        postLogoutRedirectUrl: 'redirect-url',
        issuer: 'issuer',
      ),
    );
    registerFallbackValue(
      SsoConfig(
        id: '',
        title: '',
        endpoint: '',
        tokenEndpoint: '',
        loginUrl: Uri.parse('https://fallback.com'),
        clientId: '',
        redirectUrl: '',
        scopes: [],
      ),
    );
    registerFallbackValue(
      OidcAuthTokenResponse(
        idToken: '',
        accessToken: '',
        accessTokenExpiration: DateTime.now(),
        refreshToken: '',
      ),
    );
  });

  group('OidcMobileAuthInteractor', () {
    group('authorizeAndExchangeCode', () {
      test('successfully exchanges code for tokens', () async {
        final config = createConfig();
        final expiration = DateTime.now().add(const Duration(hours: 1));

        when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenAnswer(
          (_) async => AuthorizationTokenResponse(
            'test-access-token',
            'test-refresh-token',
            expiration,
            'test-id-token',
            null,
            null,
            null,
            null,
          ),
        );
        when(
          () => mockTokenStorage.setOidcAuthTokenResponse(any()),
        ).thenAnswer((_) async {});
        when(
          () => mockSsoStorage.setSsoConfig(any(), any()),
        ).thenAnswer((_) async {});

        final result = await interactor.authorizeAndExchangeCode(
          testServerId,
          config,
        );

        expect(result.idToken, equals('test-id-token'));
        expect(result.accessToken, equals('test-access-token'));
        expect(result.refreshToken, equals('test-refresh-token'));
        expect(result.accessTokenExpiration, equals(expiration));

        verify(
          () => mockTokenStorage.setOidcAuthTokenResponse(any()),
        ).called(1);
        verify(
          () => mockSsoStorage.setSsoConfig(testServerId, config),
        ).called(1);
      });

      test(
        'throws OidcTokenValidationException when idToken is null',
        () async {
          final config = createConfig();
          final expiration = DateTime.now().add(const Duration(hours: 1));

          when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenAnswer(
            (_) async => AuthorizationTokenResponse(
              'test-access-token',
              'test-refresh-token',
              expiration,
              null, // idToken is null
              null,
              null,
              null,
              null,
            ),
          );

          expect(
            () => interactor.authorizeAndExchangeCode(testServerId, config),
            throwsA(
              isA<OidcTokenValidationException>().having(
                (e) => e.idTokenNull,
                'idTokenNull',
                isTrue,
              ),
            ),
          );
        },
      );

      test(
        'throws OidcTokenValidationException when accessToken is null',
        () async {
          final config = createConfig();
          final expiration = DateTime.now().add(const Duration(hours: 1));

          when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenAnswer(
            (_) async => AuthorizationTokenResponse(
              null, // accessToken is null
              'test-refresh-token',
              expiration,
              'test-id-token',
              null,
              null,
              null,
              null,
            ),
          );

          expect(
            () => interactor.authorizeAndExchangeCode(testServerId, config),
            throwsA(
              isA<OidcTokenValidationException>().having(
                (e) => e.accessTokenNull,
                'accessTokenNull',
                isTrue,
              ),
            ),
          );
        },
      );

      test(
        'throws OidcTokenValidationException when expiration is null',
        () async {
          final config = createConfig();

          when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenAnswer(
            (_) async => AuthorizationTokenResponse(
              'test-access-token',
              'test-refresh-token',
              null, // expiration is null
              'test-id-token',
              null,
              null,
              null,
              null,
            ),
          );

          expect(
            () => interactor.authorizeAndExchangeCode(testServerId, config),
            throwsA(
              isA<OidcTokenValidationException>().having(
                (e) => e.expirationNull,
                'expirationNull',
                isTrue,
              ),
            ),
          );
        },
      );

      test(
        'throws OidcTokenValidationException when refreshToken is null',
        () async {
          final config = createConfig();
          final expiration = DateTime.now().add(const Duration(hours: 1));

          when(() => mockAppAuth.authorizeAndExchangeCode(any())).thenAnswer(
            (_) async => AuthorizationTokenResponse(
              'test-access-token',
              null, // refreshToken is null
              expiration,
              'test-id-token',
              null,
              null,
              null,
              null,
            ),
          );

          expect(
            () => interactor.authorizeAndExchangeCode(testServerId, config),
            throwsA(
              isA<OidcTokenValidationException>().having(
                (e) => e.refreshTokenNull,
                'refreshTokenNull',
                isTrue,
              ),
            ),
          );
        },
      );

      test('rethrows exceptions from flutter_appauth', () async {
        final config = createConfig();

        when(
          () => mockAppAuth.authorizeAndExchangeCode(any()),
        ).thenThrow(Exception('Auth failed'));

        expect(
          () => interactor.authorizeAndExchangeCode(testServerId, config),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('refreshAccessToken', () {
      test('returns null when no refresh token exists', () async {
        final config = createConfig();

        when(
          () => mockTokenStorage.getOidcRefreshToken(),
        ).thenAnswer((_) async => null);

        final result = await interactor.refreshAccessToken(
          testServerId,
          config,
        );

        expect(result, isNull);
        verify(() => mockTokenStorage.getOidcRefreshToken()).called(1);
      });

      test('successfully refreshes token', () async {
        final config = createConfig();
        final newExpiration = DateTime.now().add(const Duration(hours: 1));

        when(
          () => mockTokenStorage.getOidcRefreshToken(),
        ).thenAnswer((_) async => 'existing-refresh-token');
        when(() => mockAppAuth.token(any())).thenAnswer(
          (_) async => TokenResponse(
            'new-access-token',
            'new-refresh-token',
            newExpiration,
            'new-id-token',
            null,
            null,
            null,
          ),
        );
        when(
          () => mockTokenStorage.setOidcAuthTokenResponse(any()),
        ).thenAnswer((_) async {});

        final result = await interactor.refreshAccessToken(
          testServerId,
          config,
        );

        expect(result, isNotNull);
        expect(result!.accessToken, equals('new-access-token'));
        expect(result.refreshToken, equals('new-refresh-token'));
        expect(result.idToken, equals('new-id-token'));
        expect(result.accessTokenExpiration, equals(newExpiration));

        verify(
          () => mockTokenStorage.setOidcAuthTokenResponse(any()),
        ).called(1);
      });

      test(
        'throws OidcTokenValidationException on invalid token response',
        () async {
          final config = createConfig();

          when(
            () => mockTokenStorage.getOidcRefreshToken(),
          ).thenAnswer((_) async => 'existing-refresh-token');
          when(() => mockAppAuth.token(any())).thenAnswer(
            (_) async => TokenResponse(
              null, // accessToken is null
              'new-refresh-token',
              DateTime.now(),
              'new-id-token',
              null,
              null,
              null,
            ),
          );

          expect(
            () => interactor.refreshAccessToken(testServerId, config),
            throwsA(isA<OidcTokenValidationException>()),
          );
        },
      );
    });

    group('logout', () {
      test('ends session and clears storage', () async {
        final config = createConfig();
        final tokenResponse = createTokenResponse();

        when(
          () => mockTokenStorage.getOidcAuthTokenResponse(),
        ).thenAnswer((_) async => tokenResponse);
        when(
          () => mockAppAuth.endSession(any()),
        ).thenAnswer((_) async => EndSessionResponse(null));
        when(
          () => mockTokenStorage.deleteOidcAuthTokenResponse(),
        ).thenAnswer((_) async {});
        when(
          () => mockSsoStorage.deleteSsoConfig(any()),
        ).thenAnswer((_) async {});

        await interactor.logout(testServerId, config);

        verify(() => mockAppAuth.endSession(any())).called(1);
        verify(() => mockTokenStorage.deleteOidcAuthTokenResponse()).called(1);
        verify(() => mockSsoStorage.deleteSsoConfig(testServerId)).called(1);
      });

      // Note: flutter_appauth's EndSessionRequest requires both idTokenHint
      // and postLogoutRedirectUrl to be either both null or both non-null.
      // When no token exists, the logout will fail due to this constraint.
      // This is a known limitation of the library.
    });

    group('base class functionality', () {
      test('getTokenResponse delegates to tokenStorage', () async {
        final tokenResponse = createTokenResponse();

        when(
          () => mockTokenStorage.getOidcAuthTokenResponse(),
        ).thenAnswer((_) async => tokenResponse);

        final result = await interactor.getTokenResponse();

        expect(result, equals(tokenResponse));
        verify(() => mockTokenStorage.getOidcAuthTokenResponse()).called(1);
      });

      test('getRefreshToken delegates to tokenStorage', () async {
        when(
          () => mockTokenStorage.getOidcRefreshToken(),
        ).thenAnswer((_) async => 'refresh-token');

        final result = await interactor.getRefreshToken();

        expect(result, equals('refresh-token'));
      });

      test('getSsoConfig delegates to ssoStorage', () async {
        final config = createConfig();

        when(
          () => mockSsoStorage.getSsoConfig(testServerId),
        ).thenAnswer((_) async => config);

        final result = await interactor.getSsoConfig(testServerId);

        expect(result, equals(config));
      });

      test('setSsoConfig delegates to ssoStorage', () async {
        final config = createConfig();

        when(
          () => mockSsoStorage.setSsoConfig(any(), any()),
        ).thenAnswer((_) async {});

        await interactor.setSsoConfig(testServerId, config);

        verify(
          () => mockSsoStorage.setSsoConfig(testServerId, config),
        ).called(1);
      });

      test('clearSsoConfig delegates to ssoStorage', () async {
        when(
          () => mockSsoStorage.deleteSsoConfig(any()),
        ).thenAnswer((_) async {});

        await interactor.clearSsoConfig(testServerId);

        verify(() => mockSsoStorage.deleteSsoConfig(testServerId)).called(1);
      });

      group('isTokenExpiring', () {
        test('returns true when tokenResponse is null', () {
          expect(interactor.isTokenExpiring(null), isTrue);
        });

        test('returns true when token is expired', () {
          final expiredToken = createTokenResponse(
            expiration: DateTime.now().subtract(const Duration(hours: 1)),
          );

          expect(interactor.isTokenExpiring(expiredToken), isTrue);
        });

        test('returns true when token is expiring within buffer', () {
          final expiringToken = createTokenResponse(
            expiration: DateTime.now().add(const Duration(minutes: 2)),
          );

          // Buffer is 5 minutes, token expires in 2 minutes
          expect(interactor.isTokenExpiring(expiringToken), isTrue);
        });

        test('returns false when token is not expiring', () {
          final validToken = createTokenResponse(
            expiration: DateTime.now().add(const Duration(hours: 1)),
          );

          expect(interactor.isTokenExpiring(validToken), isFalse);
        });
      });
    });

    group('useAuth flag', () {
      test('defaults to false', () {
        expect(interactor.useAuth, isFalse);
      });

      test('can be set to true', () {
        interactor.useAuth = true;
        expect(interactor.useAuth, isTrue);
      });
    });
  });
}
