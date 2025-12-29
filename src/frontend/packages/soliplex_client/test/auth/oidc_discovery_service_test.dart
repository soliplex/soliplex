import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockHttpTransport extends Mock implements HttpTransport {}

void main() {
  late MockHttpTransport mockTransport;
  late OidcDiscoveryService service;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockTransport = MockHttpTransport();
    service = OidcDiscoveryService(transport: mockTransport);
  });

  OIDCAuthSystem createAuthSystem({
    String id = 'keycloak',
    String title = 'Login with Keycloak',
    String serverUrl = 'https://auth.example.com',
    String clientId = 'test-client',
    String scope = 'openid profile email',
  }) {
    return OIDCAuthSystem(
      id: id,
      title: title,
      serverUrl: serverUrl,
      clientId: clientId,
      scope: scope,
    );
  }

  Map<String, dynamic> createDiscoveryDocument({
    String authorizationEndpoint = 'https://auth.example.com/authorize',
    String tokenEndpoint = 'https://auth.example.com/token',
    String? endSessionEndpoint,
    String? userInfoEndpoint,
  }) {
    return {
      'authorization_endpoint': authorizationEndpoint,
      'token_endpoint': tokenEndpoint,
      if (endSessionEndpoint != null)
        'end_session_endpoint': endSessionEndpoint,
      if (userInfoEndpoint != null) 'userinfo_endpoint': userInfoEndpoint,
    };
  }

  group('OidcDiscoveryService', () {
    group('discover', () {
      test('fetches from well-known endpoint', () async {
        final authSystem = createAuthSystem();
        final document = createDiscoveryDocument();

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        await service.discover(authSystem);

        final captured = verify(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            captureAny(),
          ),
        ).captured;

        final url = captured.first as Uri;
        expect(
          url.toString(),
          equals('https://auth.example.com/.well-known/openid-configuration'),
        );
      });

      test('resolves well-known URL correctly when issuer has trailing slash',
          () async {
        final authSystem = createAuthSystem(
          serverUrl: 'https://auth.example.com/',
        );
        final document = createDiscoveryDocument();

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        await service.discover(authSystem);

        final captured = verify(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            captureAny(),
          ),
        ).captured;

        final url = captured.first as Uri;
        expect(
          url.toString(),
          equals('https://auth.example.com/.well-known/openid-configuration'),
        );
      });

      test('returns SsoConfig with all fields', () async {
        final authSystem = createAuthSystem();
        final document = createDiscoveryDocument(
          endSessionEndpoint: 'https://auth.example.com/logout',
          userInfoEndpoint: 'https://auth.example.com/userinfo',
        );

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        final config = await service.discover(authSystem);

        expect(config.authSystem, equals(authSystem));
        expect(
          config.authorizationEndpoint,
          equals('https://auth.example.com/authorize'),
        );
        expect(
          config.tokenEndpoint,
          equals('https://auth.example.com/token'),
        );
        expect(
          config.endSessionEndpoint,
          equals('https://auth.example.com/logout'),
        );
        expect(
          config.userInfoEndpoint,
          equals('https://auth.example.com/userinfo'),
        );
      });

      test('returns SsoConfig with optional fields null', () async {
        final authSystem = createAuthSystem();
        final document = createDiscoveryDocument();

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        final config = await service.discover(authSystem);

        expect(config.authorizationEndpoint, isNotNull);
        expect(config.tokenEndpoint, isNotNull);
        expect(config.endSessionEndpoint, isNull);
        expect(config.userInfoEndpoint, isNull);
      });

      test('throws AuthErrorConfiguration when authorization_endpoint missing',
          () async {
        final authSystem = createAuthSystem();
        final document = <String, dynamic>{
          'token_endpoint': 'https://auth.example.com/token',
        };

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        expect(
          () => service.discover(authSystem),
          throwsA(
            isA<AuthErrorConfiguration>().having(
              (e) => e.message,
              'message',
              contains('authorization_endpoint'),
            ),
          ),
        );
      });

      test('throws AuthErrorConfiguration when token_endpoint missing',
          () async {
        final authSystem = createAuthSystem();
        final document = <String, dynamic>{
          'authorization_endpoint': 'https://auth.example.com/authorize',
        };

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        expect(
          () => service.discover(authSystem),
          throwsA(
            isA<AuthErrorConfiguration>().having(
              (e) => e.message,
              'message',
              contains('token_endpoint'),
            ),
          ),
        );
      });

      test('throws AuthErrorConfiguration listing all missing fields',
          () async {
        final authSystem = createAuthSystem();
        final document = <String, dynamic>{};

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        expect(
          () => service.discover(authSystem),
          throwsA(
            isA<AuthErrorConfiguration>().having(
              (e) => e.message,
              'message',
              allOf(
                contains('authorization_endpoint'),
                contains('token_endpoint'),
              ),
            ),
          ),
        );
      });

      test('throws AuthErrorNetwork on transport exception', () async {
        final authSystem = createAuthSystem();

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenThrow(Exception('Connection refused'));

        expect(
          () => service.discover(authSystem),
          throwsA(
            isA<AuthErrorNetwork>().having(
              (e) => e.message,
              'message',
              contains('Failed to fetch OIDC discovery document'),
            ),
          ),
        );
      });

      test('preserves original error in AuthErrorNetwork', () async {
        final authSystem = createAuthSystem();
        final originalError = Exception('Connection refused');

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenThrow(originalError);

        try {
          await service.discover(authSystem);
          fail('Expected AuthErrorNetwork');
        } on AuthErrorNetwork catch (e) {
          expect(e.originalError, equals(originalError));
          expect(e.stackTrace, isNotNull);
        }
      });

      test('throws AuthErrorConfiguration when field has wrong type', () async {
        final authSystem = createAuthSystem();
        final document = <String, dynamic>{
          'authorization_endpoint': 123,
          'token_endpoint': 'https://auth.example.com/token',
        };

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'GET',
            any(),
          ),
        ).thenAnswer((_) async => document);

        expect(
          () => service.discover(authSystem),
          throwsA(
            isA<AuthErrorConfiguration>().having(
              (e) => e.message,
              'message',
              allOf(
                contains('authorization_endpoint'),
                contains('must be a string'),
                contains('int'),
              ),
            ),
          ),
        );
      });
    });
  });
}
