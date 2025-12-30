import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';
import 'package:url_launcher/url_launcher.dart' as url_launcher;

class MockTokenStorage extends Mock implements TokenStorage {}

class MockWebAuthPendingStorage extends Mock implements WebAuthPendingStorage {}

class MockHttpClient extends Mock implements http.Client {}

class FakeUri extends Fake implements Uri {}

class FakeAuthToken extends Fake implements AuthToken {}

void main() {
  late MockTokenStorage mockStorage;
  late MockWebAuthPendingStorage mockPendingStorage;
  late MockHttpClient mockHttpClient;
  late WebAuthProvider provider;
  late bool urlLauncherCalled;
  late Uri? launchedUrl;

  setUpAll(() {
    registerFallbackValue(FakeUri());
    registerFallbackValue(FakeAuthToken());
  });

  setUp(() {
    mockStorage = MockTokenStorage();
    mockPendingStorage = MockWebAuthPendingStorage();
    mockHttpClient = MockHttpClient();
    urlLauncherCalled = false;
    launchedUrl = null;

    provider = WebAuthProvider(
      baseUrl: 'https://api.example.com',
      tokenStorage: mockStorage,
      pendingStorage: mockPendingStorage,
      httpClient: mockHttpClient,
      urlLauncher: (
        Uri url, {
        url_launcher.LaunchMode mode = url_launcher.LaunchMode.platformDefault,
        String? webOnlyWindowName,
      }) async {
        urlLauncherCalled = true;
        launchedUrl = url;
        return true;
      },
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

  group('WebAuthProvider', () {
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

      test('refreshes token via HTTP POST when expired', () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
        );

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(
          () => mockHttpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer(
          (_) async => http.Response(
            jsonEncode({
              'access_token': 'new-access',
              'refresh_token': 'new-refresh',
              'expires_in': 3600,
            }),
            200,
          ),
        );
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<Authenticated>());
        final auth = result as Authenticated;
        expect(auth.token.accessToken, equals('new-access'));

        // Verify HTTP POST was made to token endpoint
        final captured = verify(
          () => mockHttpClient.post(
            captureAny(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).captured.single as Uri;
        expect(captured.toString(), equals('https://auth.example.com/token'));
      });

      test('returns RefreshFailed when refresh returns error', () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
        );

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(
          () => mockHttpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer(
          (_) async => http.Response('{"error": "invalid_grant"}', 400),
        );
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<RefreshFailed>());
        verify(() => mockStorage.delete('server1')).called(1);
      });

      test('returns RefreshFailed when refresh throws exception', () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
        );

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(
          () => mockHttpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenThrow(Exception('Network error'));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<RefreshFailed>());
      });

      test('returns RefreshFailed when refresh response missing access_token',
          () async {
        final config = createConfig();
        final expiredToken = createToken(
          expiresAt: DateTime.now().subtract(const Duration(hours: 1)),
        );

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(
          () => mockHttpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer(
          (_) async => http.Response(
            jsonEncode({'expires_in': 3600}),
            200,
          ),
        );
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await provider.getValidToken('server1', config);

        expect(result, isA<RefreshFailed>());
        verify(() => mockStorage.delete('server1')).called(1);
      });
    });

    group('login', () {
      test('saves pending server ID and throws AuthFlowRedirect', () async {
        final config = createConfig();
        when(() => mockPendingStorage.savePendingServerId('server1'))
            .thenAnswer((_) async {});

        await expectLater(
          () => provider.login('server1', config),
          throwsA(isA<AuthFlowRedirect>()),
        );

        verify(() => mockPendingStorage.savePendingServerId('server1'))
            .called(1);
        expect(urlLauncherCalled, isTrue);
      });

      test('builds correct login URL with return_to parameter', () async {
        final config = createConfig();
        when(() => mockPendingStorage.savePendingServerId('server1'))
            .thenAnswer((_) async {});

        try {
          await provider.login('server1', config);
        } on AuthFlowRedirect {
          // Expected
        }

        expect(launchedUrl, isNotNull);
        expect(
          launchedUrl!.toString(),
          startsWith('https://api.example.com/api/login/keycloak'),
        );
        expect(
          launchedUrl!.queryParameters['return_to'],
          equals('/auth/callback'),
        );
      });

      test('throws AuthErrorNetwork when URL launch fails', () async {
        final failingProvider = WebAuthProvider(
          baseUrl: 'https://api.example.com',
          tokenStorage: mockStorage,
          pendingStorage: mockPendingStorage,
          httpClient: mockHttpClient,
          urlLauncher: (
            url, {
            mode = url_launcher.LaunchMode.platformDefault,
            webOnlyWindowName,
          }) async =>
              false,
        );
        final config = createConfig();
        when(() => mockPendingStorage.savePendingServerId('server1'))
            .thenAnswer((_) async {});

        await expectLater(
          () => failingProvider.login('server1', config),
          throwsA(isA<AuthErrorNetwork>()),
        );
      });
    });

    group('logout', () {
      test('deletes token and clears pending server ID', () async {
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});
        when(() => mockPendingStorage.clearPendingServerId())
            .thenAnswer((_) async {});

        await provider.logout('server1');

        verify(() => mockStorage.delete('server1')).called(1);
        verify(() => mockPendingStorage.clearPendingServerId()).called(1);
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
