import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/auth/oidc_auth_interactor.dart';
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/sso_config.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/services/auth_manager.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';

class MockSecureStorageService extends Mock implements SecureStorageService {}

class MockOidcAuthInteractor extends Mock implements OidcAuthInteractor {}

class MockSecureTokenStorage extends Mock implements SecureTokenStorage {}

void main() {
  late MockSecureStorageService mockStorage;
  late MockOidcAuthInteractor mockOidcInteractor;
  late MockSecureTokenStorage mockTokenStorage;
  late AuthManager authManager;
  late http.Client mockClient;

  const testServerId = 'server-123';

  ServerConnection createServer() {
    return ServerConnection.agUi(
      id: testServerId,
      url: 'https://api.example.com',
      lastConnected: DateTime.now(),
      displayName: 'Test Server',
    );
  }

  OIDCAuthSystem createProvider() {
    return const OIDCAuthSystem(
      id: 'keycloak',
      title: 'Sign in with Keycloak',
      serverUrl: 'https://auth.example.com/realms/myrealm',
      clientId: 'test-client',
      scope: 'openid profile email',
    );
  }

  OidcAuthTokenResponse createTokenResponse({
    DateTime? expiration,
  }) {
    return OidcAuthTokenResponse(
      idToken: 'test-id-token',
      accessToken: 'test-access-token',
      accessTokenExpiration:
          expiration ?? DateTime.now().add(const Duration(hours: 1)),
      refreshToken: 'test-refresh-token',
    );
  }

  /// Helper to setup read mock for access token
  void setupAccessTokenMock(String? token) {
    when(
      () => mockStorage.read('server_${testServerId}_access_token'),
    ).thenAnswer((_) async => token);
  }

  /// Helper to setup read mock for token expiry
  void setupTokenExpiryMock(DateTime? expiry) {
    when(
      () => mockStorage.read('server_${testServerId}_token_expiry'),
    ).thenAnswer((_) async => expiry?.toIso8601String());
  }

  /// Helper to setup storage write mock
  void setupStorageWriteMock() {
    when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});
  }

  /// Helper to setup storage delete mock
  void setupStorageDeleteMock() {
    when(() => mockStorage.delete(any())).thenAnswer((_) async {});
  }

  setUp(() {
    mockStorage = MockSecureStorageService();
    mockOidcInteractor = MockOidcAuthInteractor();
    mockTokenStorage = MockSecureTokenStorage();
    mockClient = MockClient((request) async {
      return http.Response('{}', 200);
    });
    authManager = AuthManager(
      storage: mockStorage,
      oidcInteractor: mockOidcInteractor,
      tokenStorage: mockTokenStorage,
      httpClient: mockClient,
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
      OidcAuthTokenResponse(
        idToken: '',
        accessToken: '',
        accessTokenExpiration: DateTime.now(),
        refreshToken: '',
      ),
    );
  });

  group('UserInfo', () {
    test('creates from constructor', () {
      const userInfo = UserInfo(
        id: 'user-123',
        name: 'John Doe',
        email: 'john@example.com',
      );

      expect(userInfo.id, equals('user-123'));
      expect(userInfo.name, equals('John Doe'));
      expect(userInfo.email, equals('john@example.com'));
    });

    test('creates from JSON', () {
      final json = {
        'sub': 'user-456',
        'name': 'Jane Doe',
        'email': 'jane@example.com',
      };

      final userInfo = UserInfo.fromJson(json);

      expect(userInfo.id, equals('user-456'));
      expect(userInfo.name, equals('Jane Doe'));
      expect(userInfo.email, equals('jane@example.com'));
    });

    test('handles null values in JSON', () {
      final json = <String, dynamic>{};

      final userInfo = UserInfo.fromJson(json);

      expect(userInfo.id, isNull);
      expect(userInfo.name, isNull);
      expect(userInfo.email, isNull);
    });
  });

  group('AuthManager', () {
    group('hasValidToken', () {
      test('returns false when no token exists', () async {
        setupAccessTokenMock(null);

        final result = await authManager.hasValidToken(testServerId);

        expect(result, isFalse);
      });

      test('returns true when token exists and not expired', () async {
        setupAccessTokenMock('valid-token');
        setupTokenExpiryMock(DateTime.now().add(const Duration(hours: 1)));

        final result = await authManager.hasValidToken(testServerId);

        expect(result, isTrue);
      });

      test('returns true when token exists and no expiry set', () async {
        setupAccessTokenMock('valid-token');
        setupTokenExpiryMock(null);

        final result = await authManager.hasValidToken(testServerId);

        expect(result, isTrue);
      });

      test('attempts refresh when token is expired', () async {
        setupAccessTokenMock('expired-token');
        setupTokenExpiryMock(DateTime.now().subtract(const Duration(hours: 1)));
        when(
          () => mockOidcInteractor.getSsoConfig(testServerId),
        ).thenAnswer((_) async => null);

        final result = await authManager.hasValidToken(testServerId);

        // Should return false since refresh failed (no SSO config)
        expect(result, isFalse);
        verify(() => mockOidcInteractor.getSsoConfig(testServerId)).called(1);
      });
    });

    group('getUserInfo', () {
      test('returns null when no token exists', () async {
        final server = createServer();
        setupAccessTokenMock(null);

        final result = await authManager.getUserInfo(server);

        expect(result, isNull);
      });

      test('returns UserInfo when token exists and API succeeds', () async {
        final server = createServer();
        final userInfoJson = jsonEncode({
          'sub': 'user-123',
          'name': 'Test User',
          'email': 'test@example.com',
        });

        final httpClient = MockClient((request) async {
          expect(request.url.toString(), contains('/user_info'));
          expect(request.headers['Authorization'], equals('Bearer test-token'));
          return http.Response(userInfoJson, 200);
        });

        final manager = AuthManager(
          storage: mockStorage,
          oidcInteractor: mockOidcInteractor,
          tokenStorage: mockTokenStorage,
          httpClient: httpClient,
        );

        setupAccessTokenMock('test-token');

        final result = await manager.getUserInfo(server);

        expect(result, isNotNull);
        expect(result!.id, equals('user-123'));
        expect(result.name, equals('Test User'));
        expect(result.email, equals('test@example.com'));
      });

      test('returns null when API returns non-200', () async {
        final server = createServer();

        final httpClient = MockClient((request) async {
          return http.Response('Unauthorized', 401);
        });

        final manager = AuthManager(
          storage: mockStorage,
          oidcInteractor: mockOidcInteractor,
          tokenStorage: mockTokenStorage,
          httpClient: httpClient,
        );

        setupAccessTokenMock('test-token');

        final result = await manager.getUserInfo(server);

        expect(result, isNull);
      });
    });

    group('login', () {
      test('successfully logs in and returns UserInfo', () async {
        final server = createServer();
        final provider = createProvider();
        final tokenResponse = createTokenResponse();
        final userInfoJson = jsonEncode({
          'sub': 'user-123',
          'name': 'Test User',
          'email': 'test@example.com',
        });

        final httpClient = MockClient((request) async {
          return http.Response(userInfoJson, 200);
        });

        final manager = AuthManager(
          storage: mockStorage,
          oidcInteractor: mockOidcInteractor,
          tokenStorage: mockTokenStorage,
          httpClient: httpClient,
        );

        when(
          () => mockTokenStorage.deleteOidcAuthTokenResponse(),
        ).thenAnswer((_) async {});
        when(
          () => mockOidcInteractor.clearSsoConfig(server.id),
        ).thenAnswer((_) async {});
        when(
          () => mockOidcInteractor.authorizeAndExchangeCode(
            server.id,
            any(),
          ),
        ).thenAnswer((_) async => tokenResponse);
        setupStorageWriteMock();

        final result = await manager.login(provider, server);

        expect(result, isNotNull);
        expect(result!.id, equals('user-123'));
        verify(() => mockTokenStorage.deleteOidcAuthTokenResponse()).called(1);
        verify(() => mockOidcInteractor.clearSsoConfig(server.id)).called(1);
        verify(() => mockOidcInteractor.useAuth = true).called(1);
      });

      test('rethrows exception on login failure', () async {
        final server = createServer();
        final provider = createProvider();

        when(
          () => mockTokenStorage.deleteOidcAuthTokenResponse(),
        ).thenAnswer((_) async {});
        when(
          () => mockOidcInteractor.clearSsoConfig(server.id),
        ).thenAnswer((_) async {});
        when(
          () => mockOidcInteractor.authorizeAndExchangeCode(
            server.id,
            any(),
          ),
        ).thenThrow(Exception('Auth failed'));

        expect(
          () => authManager.login(provider, server),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('logout', () {
      test('clears tokens and disables auth', () async {
        final server = createServer();

        when(
          () => mockOidcInteractor.getSsoConfig(server.id),
        ).thenAnswer((_) async => null);
        setupStorageDeleteMock();

        await authManager.logout(server);

        verify(() => mockOidcInteractor.useAuth = false).called(1);
      });

      test('calls OIDC logout when config exists', () async {
        final server = createServer();
        final ssoConfig = SsoConfig(
          id: 'keycloak',
          title: 'Keycloak',
          endpoint: 'https://auth.example.com',
          tokenEndpoint: 'https://auth.example.com/token',
          loginUrl: Uri.parse('https://auth.example.com/auth'),
          clientId: 'client',
          redirectUrl: 'app://callback',
          scopes: ['openid'],
        );

        when(
          () => mockOidcInteractor.getSsoConfig(server.id),
        ).thenAnswer((_) async => ssoConfig);
        when(
          () => mockOidcInteractor.logout(server.id, ssoConfig),
        ).thenAnswer((_) async {});
        setupStorageDeleteMock();

        await authManager.logout(server);

        verify(() => mockOidcInteractor.logout(server.id, ssoConfig)).called(1);
      });

      test('continues with local logout even if OIDC logout fails', () async {
        final server = createServer();
        final ssoConfig = SsoConfig(
          id: 'keycloak',
          title: 'Keycloak',
          endpoint: 'https://auth.example.com',
          tokenEndpoint: 'https://auth.example.com/token',
          loginUrl: Uri.parse('https://auth.example.com/auth'),
          clientId: 'client',
          redirectUrl: 'app://callback',
          scopes: ['openid'],
        );

        when(
          () => mockOidcInteractor.getSsoConfig(server.id),
        ).thenAnswer((_) async => ssoConfig);
        when(
          () => mockOidcInteractor.logout(server.id, ssoConfig),
        ).thenThrow(Exception('Logout failed'));
        setupStorageDeleteMock();

        // Should not throw
        await authManager.logout(server);
      });
    });

    group('clearTokens', () {
      test('delegates to storage', () async {
        setupStorageDeleteMock();

        await authManager.clearTokens(testServerId);

        // Verifies delete was called for the token keys
        verify(() => mockStorage.delete(any())).called(greaterThan(0));
      });
    });

    group('getAccessToken', () {
      test('returns token when not expiring', () async {
        setupTokenExpiryMock(DateTime.now().add(const Duration(hours: 1)));
        setupAccessTokenMock('valid-token');

        final result = await authManager.getAccessToken(testServerId);

        expect(result, equals('valid-token'));
      });

      test('attempts refresh when token expiring soon', () async {
        setupTokenExpiryMock(DateTime.now().add(const Duration(minutes: 2)));
        when(
          () => mockOidcInteractor.getSsoConfig(testServerId),
        ).thenAnswer((_) async => null); // Refresh fails
        setupAccessTokenMock('old-token');

        final result = await authManager.getAccessToken(testServerId);

        // Returns old token even if refresh fails
        expect(result, equals('old-token'));
        verify(() => mockOidcInteractor.getSsoConfig(testServerId)).called(1);
      });

      test('returns null when no token exists', () async {
        setupTokenExpiryMock(null);
        setupAccessTokenMock(null);

        final result = await authManager.getAccessToken(testServerId);

        expect(result, isNull);
      });
    });

    group('getAuthHeaders', () {
      test('returns empty map when no token', () async {
        setupTokenExpiryMock(null);
        setupAccessTokenMock(null);

        final result = await authManager.getAuthHeaders(testServerId);

        expect(result, isEmpty);
      });

      test('returns Authorization header when token exists', () async {
        setupTokenExpiryMock(DateTime.now().add(const Duration(hours: 1)));
        setupAccessTokenMock('valid-token');

        final result = await authManager.getAuthHeaders(testServerId);

        expect(result, containsPair('Authorization', 'Bearer valid-token'));
      });
    });

    group('dispose', () {
      test('closes http client', () {
        // This is mainly to ensure the method exists and doesn't throw
        authManager.dispose();
      });
    });
  });
}
