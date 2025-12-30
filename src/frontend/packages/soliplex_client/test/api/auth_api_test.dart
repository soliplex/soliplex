import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  const testProviderJson = {
    'id': 'keycloak',
    'title': 'Keycloak',
    'server_url': 'https://auth.example.com',
    'client_id': 'test-client',
  };

  const testProvider = OIDCAuthSystem(
    id: 'keycloak',
    title: 'Keycloak',
    serverUrl: 'https://auth.example.com',
    clientId: 'test-client',
  );

  MockClient createMockClient({
    int statusCode = 200,
    Object? body,
    void Function(http.Request)? onRequest,
  }) {
    return MockClient((request) async {
      onRequest?.call(request);
      return http.Response(
        body != null ? jsonEncode(body) : '',
        statusCode,
      );
    });
  }

  group('AuthApi', () {
    group('getAuthProviders', () {
      test('returns list of providers on success', () async {
        final client = createMockClient(body: [testProviderJson]);
        final api = AuthApi(client: client);

        final providers = await api.getAuthProviders('https://api.example.com');

        expect(providers, hasLength(1));
        expect(providers.first, equals(testProvider));
      });

      test('requests correct URL', () async {
        Uri? capturedUri;
        final client = createMockClient(
          body: [testProviderJson],
          onRequest: (request) {
            capturedUri = request.url;
          },
        );
        final api = AuthApi(client: client);

        await api.getAuthProviders('https://api.example.com');

        expect(
          capturedUri?.toString(),
          equals('https://api.example.com/api/login'),
        );
      });

      test('normalizes trailing slash in server URL', () async {
        Uri? capturedUri;
        final client = createMockClient(
          body: [testProviderJson],
          onRequest: (request) {
            capturedUri = request.url;
          },
        );
        final api = AuthApi(client: client);

        await api.getAuthProviders('https://api.example.com/');

        expect(
          capturedUri?.toString(),
          equals('https://api.example.com/api/login'),
        );
      });

      test('returns empty list when server returns empty array', () async {
        final client = createMockClient(body: <dynamic>[]);
        final api = AuthApi(client: client);

        final providers = await api.getAuthProviders('https://api.example.com');

        expect(providers, isEmpty);
      });

      test('returns multiple providers', () async {
        final client = createMockClient(
          body: [
            testProviderJson,
            {
              'id': 'azure',
              'title': 'Azure AD',
              'server_url': 'https://login.microsoft.com',
              'client_id': 'azure-client',
            },
          ],
        );
        final api = AuthApi(client: client);

        final providers = await api.getAuthProviders('https://api.example.com');

        expect(providers, hasLength(2));
        expect(providers[0].id, equals('keycloak'));
        expect(providers[1].id, equals('azure'));
      });

      test('throws ApiException on non-200 status', () async {
        final client = createMockClient(statusCode: 500);
        final api = AuthApi(client: client);

        expect(
          () => api.getAuthProviders('https://api.example.com'),
          throwsA(
            isA<ApiException>()
                .having((e) => e.statusCode, 'statusCode', 500)
                .having(
                  (e) => e.message,
                  'message',
                  'https://api.example.com returned 500',
                ),
          ),
        );
      });

      test('throws ApiException on 404', () async {
        final client = createMockClient(statusCode: 404);
        final api = AuthApi(client: client);

        expect(
          () => api.getAuthProviders('https://api.example.com'),
          throwsA(
            isA<ApiException>()
                .having((e) => e.statusCode, 'statusCode', 404)
                .having(
                  (e) => e.message,
                  'message',
                  'https://api.example.com returned 404',
                ),
          ),
        );
      });

      test('throws FormatException on non-list response', () async {
        final client = createMockClient(body: {'error': 'not a list'});
        final api = AuthApi(client: client);

        expect(
          () => api.getAuthProviders('https://api.example.com'),
          throwsA(
            isA<FormatException>().having(
              (e) => e.message,
              'message',
              'Invalid response format',
            ),
          ),
        );
      });

      test('throws FormatException on invalid JSON', () async {
        final client = MockClient(
          (request) async => http.Response('not json', 200),
        );
        final api = AuthApi(client: client);

        expect(
          () => api.getAuthProviders('https://api.example.com'),
          throwsA(isA<FormatException>()),
        );
      });
    });
  });
}
