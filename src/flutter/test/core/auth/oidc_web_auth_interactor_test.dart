import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/auth/oidc_auth_interactor.dart';
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_sso_storage.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/sso_config.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/auth/web_auth_pending_storage.dart';

class MockSecureSsoStorage extends Mock implements SecureSsoStorage {}

class MockSecureTokenStorage extends Mock implements SecureTokenStorage {}

class MockWebAuthPendingStorage extends Mock implements WebAuthPendingStorage {}

void main() {
  late MockSecureSsoStorage mockSsoStorage;
  late MockSecureTokenStorage mockTokenStorage;
  late MockWebAuthPendingStorage mockPendingStorage;
  late OidcWebAuthInteractor interactor;

  const testServerId = 'server-123';

  SsoConfig createConfig({String? serverBaseUrl}) {
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
      redirectUrl: 'https://app.example.com/callback',
      scopes: ['openid', 'profile', 'email'],
      serverBaseUrl: serverBaseUrl,
    );
  }

  setUp(() {
    mockSsoStorage = MockSecureSsoStorage();
    mockTokenStorage = MockSecureTokenStorage();
    mockPendingStorage = MockWebAuthPendingStorage();
    interactor = OidcWebAuthInteractor(
      mockSsoStorage,
      mockTokenStorage,
      const Duration(minutes: 5),
      pendingStorage: mockPendingStorage,
    );
  });

  setUpAll(() {
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
      PendingWebAuth(
        serverId: '',
        providerId: '',
        codeVerifier: '',
        state: '',
        tokenEndpoint: '',
        clientId: '',
        redirectUrl: '',
        createdAt: DateTime.now(),
      ),
    );
  });

  group('OidcWebAuthInteractor', () {
    group('authorizeAndExchangeCode', () {
      test('throws StateError when serverBaseUrl is null', () async {
        final config = createConfig(serverBaseUrl: null);

        expect(
          () => interactor.authorizeAndExchangeCode(testServerId, config),
          throwsA(
            isA<StateError>().having(
              (e) => e.message,
              'message',
              contains('serverBaseUrl is required'),
            ),
          ),
        );
      });

      test('stores SSO config before redirect', () async {
        final config = createConfig(serverBaseUrl: 'https://api.example.com');

        when(
          () => mockSsoStorage.setSsoConfig(any(), any()),
        ).thenAnswer((_) async {});
        when(
          () => mockPendingStorage.savePendingAuth(any()),
        ).thenAnswer((_) async {});

        // This will throw OidcWebRedirectException after storing configs
        // and attempting to launch URL
        try {
          await interactor.authorizeAndExchangeCode(testServerId, config);
        } on OidcWebRedirectException catch (_) {
          // Expected - this means it got past the config storage
        } on Object catch (_) {
          // URL launcher may fail in test environment - that's OK
          // We just want to verify the configs were stored
        }

        verify(
          () => mockSsoStorage.setSsoConfig(testServerId, config),
        ).called(1);
      });

      test('stores pending auth before redirect', () async {
        final config = createConfig(serverBaseUrl: 'https://api.example.com');

        when(
          () => mockSsoStorage.setSsoConfig(any(), any()),
        ).thenAnswer((_) async {});
        when(
          () => mockPendingStorage.savePendingAuth(any()),
        ).thenAnswer((_) async {});

        try {
          await interactor.authorizeAndExchangeCode(testServerId, config);
        } on OidcWebRedirectException catch (_) {
          // Expected
        } on Object catch (_) {
          // URL launcher may fail in test environment
        }

        verify(
          () => mockPendingStorage.savePendingAuth(
            any(
              that: isA<PendingWebAuth>()
                  .having((p) => p.serverId, 'serverId', testServerId)
                  .having((p) => p.providerId, 'providerId', 'keycloak'),
            ),
          ),
        ).called(1);
      });
    });

    group('refreshAccessToken', () {
      test('returns null when no refresh token exists', () async {
        final config = createConfig(serverBaseUrl: 'https://api.example.com');

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
    });

    group('base class functionality', () {
      test('getTokenResponse delegates to tokenStorage', () async {
        final expiration = DateTime.now().add(const Duration(hours: 1));
        final tokenResponse = OidcAuthTokenResponse(
          idToken: 'id-token',
          accessToken: 'access-token',
          accessTokenExpiration: expiration,
          refreshToken: 'refresh-token',
        );

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
        verify(() => mockTokenStorage.getOidcRefreshToken()).called(1);
      });

      test('getSsoConfig delegates to ssoStorage', () async {
        final config = createConfig(serverBaseUrl: 'https://api.example.com');

        when(
          () => mockSsoStorage.getSsoConfig(testServerId),
        ).thenAnswer((_) async => config);

        final result = await interactor.getSsoConfig(testServerId);

        expect(result, equals(config));
        verify(() => mockSsoStorage.getSsoConfig(testServerId)).called(1);
      });

      test('setSsoConfig delegates to ssoStorage', () async {
        final config = createConfig(serverBaseUrl: 'https://api.example.com');

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
          final expiredToken = OidcAuthTokenResponse(
            idToken: 'id',
            accessToken: 'access',
            accessTokenExpiration: DateTime.now().subtract(
              const Duration(hours: 1),
            ),
            refreshToken: 'refresh',
          );

          expect(interactor.isTokenExpiring(expiredToken), isTrue);
        });

        test('returns true when token is expiring within buffer', () {
          final expiringToken = OidcAuthTokenResponse(
            idToken: 'id',
            accessToken: 'access',
            accessTokenExpiration: DateTime.now().add(
              const Duration(minutes: 2),
            ),
            refreshToken: 'refresh',
          );

          // Buffer is 5 minutes, token expires in 2 minutes
          expect(interactor.isTokenExpiring(expiringToken), isTrue);
        });

        test('returns false when token is not expiring', () {
          final validToken = OidcAuthTokenResponse(
            idToken: 'id',
            accessToken: 'access',
            accessTokenExpiration: DateTime.now().add(const Duration(hours: 1)),
            refreshToken: 'refresh',
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

  group('OidcWebRedirectException', () {
    test('stores serverId', () {
      final exception = OidcWebRedirectException('server-123');

      expect(exception.serverId, equals('server-123'));
    });

    test('toString includes serverId', () {
      final exception = OidcWebRedirectException('server-123');

      expect(exception.toString(), contains('server-123'));
    });
  });

  group('OidcTokenValidationException', () {
    test('stores null flags', () {
      final exception = OidcTokenValidationException(
        idTokenNull: true,
        accessTokenNull: false,
        expirationNull: true,
        refreshTokenNull: false,
      );

      expect(exception.idTokenNull, isTrue);
      expect(exception.accessTokenNull, isFalse);
      expect(exception.expirationNull, isTrue);
      expect(exception.refreshTokenNull, isFalse);
    });

    test('toString includes all null flags', () {
      final exception = OidcTokenValidationException(
        idTokenNull: true,
        accessTokenNull: false,
        expirationNull: true,
        refreshTokenNull: false,
      );

      final str = exception.toString();
      expect(str, contains('id token null? true'));
      expect(str, contains('access token null: false'));
      expect(str, contains('token expiration null: true'));
      expect(str, contains('refresh token null: false'));
    });
  });

  group('SsoConfigNotSetException', () {
    test('has default message', () {
      final exception = SsoConfigNotSetException();

      expect(exception.message, contains('Single sign on config'));
    });

    test('allows custom message', () {
      final exception = SsoConfigNotSetException('Custom message');

      expect(exception.message, equals('Custom message'));
    });

    test('toString returns message', () {
      final exception = SsoConfigNotSetException('Test message');

      expect(exception.toString(), equals('Test message'));
    });
  });
}
