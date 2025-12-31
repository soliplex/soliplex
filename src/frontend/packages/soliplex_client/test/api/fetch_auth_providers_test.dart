import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockHttpTransport extends Mock implements HttpTransport {}

void main() {
  late MockHttpTransport mockTransport;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockTransport = MockHttpTransport();
    when(() => mockTransport.close()).thenReturn(null);
  });

  tearDown(() {
    reset(mockTransport);
  });

  group('fetchAuthProviders', () {
    test('returns list of providers from backend response', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenAnswer(
        (_) async => {
          'keycloak': {
            'title': 'Authenticate with Keycloak',
            'server_url': 'https://sso.example.com/realms/app',
            'client_id': 'my-client',
            'scope': 'openid email profile',
          },
          'pydio': {
            'title': 'Pydio SSO',
            'server_url': 'https://sso.pydio.com/auth',
            'client_id': 'pydio-client',
            'scope': 'openid',
          },
        },
      );

      final providers = await fetchAuthProviders(
        transport: mockTransport,
        baseUrl: Uri.parse('https://api.example.com'),
      );

      expect(providers, hasLength(2));

      final keycloak = providers.firstWhere((p) => p.id == 'keycloak');
      expect(keycloak.name, equals('Authenticate with Keycloak'));
      expect(keycloak.serverUrl, equals('https://sso.example.com/realms/app'));
      expect(keycloak.clientId, equals('my-client'));
      expect(keycloak.scope, equals('openid email profile'));

      final pydio = providers.firstWhere((p) => p.id == 'pydio');
      expect(pydio.name, equals('Pydio SSO'));
      expect(pydio.serverUrl, equals('https://sso.pydio.com/auth'));
      expect(pydio.clientId, equals('pydio-client'));
      expect(pydio.scope, equals('openid'));
    });

    test('returns empty list when no providers configured', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenAnswer((_) async => <String, dynamic>{});

      final providers = await fetchAuthProviders(
        transport: mockTransport,
        baseUrl: Uri.parse('https://api.example.com'),
      );

      expect(providers, isEmpty);
    });

    test('calls correct endpoint /api/login', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenAnswer((_) async => <String, dynamic>{});

      await fetchAuthProviders(
        transport: mockTransport,
        baseUrl: Uri.parse('https://api.example.com'),
      );

      verify(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          Uri.parse('https://api.example.com/api/login'),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).called(1);
    });

    test('handles base URL with trailing slash', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenAnswer((_) async => <String, dynamic>{});

      await fetchAuthProviders(
        transport: mockTransport,
        baseUrl: Uri.parse('https://api.example.com/'),
      );

      verify(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          Uri.parse('https://api.example.com/api/login'),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).called(1);
    });

    test('propagates network exceptions', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenThrow(const NetworkException(message: 'Connection failed'));

      await expectLater(
        fetchAuthProviders(
          transport: mockTransport,
          baseUrl: Uri.parse('https://api.example.com'),
        ),
        throwsA(isA<NetworkException>()),
      );
    });

    test('propagates API exceptions', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenThrow(const ApiException(message: 'Server error', statusCode: 500));

      await expectLater(
        fetchAuthProviders(
          transport: mockTransport,
          baseUrl: Uri.parse('https://api.example.com'),
        ),
        throwsA(isA<ApiException>()),
      );
    });

    test('returns single provider correctly', () async {
      when(
        () => mockTransport.request<Map<String, dynamic>>(
          'GET',
          any(),
          body: any(named: 'body'),
          headers: any(named: 'headers'),
          timeout: any(named: 'timeout'),
          cancelToken: any(named: 'cancelToken'),
          fromJson: any(named: 'fromJson'),
        ),
      ).thenAnswer(
        (_) async => {
          'single': {
            'title': 'Single Provider',
            'server_url': 'https://auth.example.com',
            'client_id': 'client',
            'scope': 'openid',
          },
        },
      );

      final providers = await fetchAuthProviders(
        transport: mockTransport,
        baseUrl: Uri.parse('https://api.example.com'),
      );

      expect(providers, hasLength(1));
      expect(providers.first.id, equals('single'));
      expect(providers.first.name, equals('Single Provider'));
    });
  });
}
