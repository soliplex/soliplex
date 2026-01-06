import 'dart:convert';
import 'dart:typed_data';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockSoliplexHttpClient extends Mock implements SoliplexHttpClient {}

void main() {
  late MockSoliplexHttpClient mockClient;
  late TokenRefreshService service;

  const discoveryUrl = 'https://idp.example.com/.well-known/openid-configuration';
  const refreshToken = 'test-refresh-token';
  const clientId = 'test-client-id';

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockClient = MockSoliplexHttpClient();
    service = TokenRefreshService(httpClient: mockClient);
  });

  tearDown(() {
    reset(mockClient);
  });

  HttpResponse jsonResponse(
    Map<String, dynamic> body, {
    int statusCode = 200,
  }) {
    return HttpResponse(
      statusCode: statusCode,
      bodyBytes: Uint8List.fromList(utf8.encode(jsonEncode(body))),
    );
  }

  void setupDiscoverySuccess({String? tokenEndpoint}) {
    final endpoint = tokenEndpoint ?? 'https://idp.example.com/oauth2/token';
    when(
      () => mockClient.request(
        'GET',
        Uri.parse(discoveryUrl),
        timeout: any(named: 'timeout'),
      ),
    ).thenAnswer(
      (_) async => jsonResponse({'token_endpoint': endpoint}),
    );
  }

  void setupTokenSuccess({
    String accessToken = 'new-access-token',
    String? newRefreshToken,
    int? expiresIn,
    String? idToken,
  }) {
    when(
      () => mockClient.request(
        'POST',
        Uri.parse('https://idp.example.com/oauth2/token'),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
        timeout: any(named: 'timeout'),
      ),
    ).thenAnswer(
      (_) async => jsonResponse({
        'access_token': accessToken,
        if (newRefreshToken != null) 'refresh_token': newRefreshToken,
        if (expiresIn != null) 'expires_in': expiresIn,
        if (idToken != null) 'id_token': idToken,
      }),
    );
  }

  group('TokenRefreshService', () {
    group('successful refresh', () {
      test('returns TokenRefreshSuccess with new tokens', () async {
        setupDiscoverySuccess();
        setupTokenSuccess(
          accessToken: 'fresh-access',
          newRefreshToken: 'fresh-refresh',
          expiresIn: 3600,
          idToken: 'fresh-id-token',
        );

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshSuccess>());
        final success = result as TokenRefreshSuccess;
        expect(success.accessToken, 'fresh-access');
        expect(success.refreshToken, 'fresh-refresh');
        expect(success.idToken, 'fresh-id-token');
      });

      test('preserves original refresh token when not rotated', () async {
        setupDiscoverySuccess();
        setupTokenSuccess(accessToken: 'fresh-access');

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshSuccess>());
        final success = result as TokenRefreshSuccess;
        expect(success.refreshToken, refreshToken);
      });

      test('uses fallback expiry when expires_in not provided', () async {
        setupDiscoverySuccess();
        setupTokenSuccess(accessToken: 'fresh-access');

        final before = DateTime.now();
        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );
        final after = DateTime.now();

        expect(result, isA<TokenRefreshSuccess>());
        final success = result as TokenRefreshSuccess;

        // Should be approximately 30 minutes from now (fallback)
        final expectedMin = before.add(const Duration(minutes: 29));
        final expectedMax = after.add(const Duration(minutes: 31));
        expect(success.expiresAt.isAfter(expectedMin), isTrue);
        expect(success.expiresAt.isBefore(expectedMax), isTrue);
      });

      test('idToken is null when IdP does not return it', () async {
        setupDiscoverySuccess();
        setupTokenSuccess(accessToken: 'fresh-access');

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshSuccess>());
        final success = result as TokenRefreshSuccess;
        expect(success.idToken, isNull);
      });
    });

    group('input validation', () {
      test('returns noRefreshToken when refresh token is empty', () async {
        // No HTTP calls should be made - validation happens before network
        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: '',
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.noRefreshToken);

        // Verify no network calls were made
        verifyNever(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        );
      });
    });

    group('invalid_grant error', () {
      test('returns invalidGrant failure', () async {
        setupDiscoverySuccess();
        when(
          () => mockClient.request(
            'POST',
            Uri.parse('https://idp.example.com/oauth2/token'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(
            {'error': 'invalid_grant', 'error_description': 'Token expired'},
            statusCode: 400,
          ),
        );

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.invalidGrant);
      });
    });

    group('network errors', () {
      test('returns networkError on discovery failure', () async {
        when(
          () => mockClient.request(
            'GET',
            Uri.parse(discoveryUrl),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(Exception('Connection refused'));

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.networkError);
      });

      test('returns networkError on token request failure', () async {
        setupDiscoverySuccess();
        when(
          () => mockClient.request(
            'POST',
            Uri.parse('https://idp.example.com/oauth2/token'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(Exception('Connection reset'));

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.networkError);
      });
    });

    group('discovery validation', () {
      test('returns unknownError when discovery returns non-200', () async {
        when(
          () => mockClient.request(
            'GET',
            Uri.parse(discoveryUrl),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse({}, statusCode: 500),
        );

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });

      test('returns unknownError when token_endpoint missing', () async {
        when(
          () => mockClient.request(
            'GET',
            Uri.parse(discoveryUrl),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse({'issuer': 'https://idp.example.com'}),
        );

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });

      test('returns unknownError on SSRF attempt (different host)', () async {
        setupDiscoverySuccess(tokenEndpoint: 'https://evil.com/steal');

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });

      test('returns unknownError on SSRF attempt (http downgrade)', () async {
        // Same host but HTTP instead of HTTPS - potential MITM attack
        setupDiscoverySuccess(tokenEndpoint: 'http://idp.example.com/oauth2/token');

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });

      test('returns unknownError on SSRF attempt (different port)', () async {
        // Same host and scheme but different port
        const maliciousEndpoint = 'https://idp.example.com:8443/oauth2/token';
        setupDiscoverySuccess(tokenEndpoint: maliciousEndpoint);

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });
    });

    group('token response validation', () {
      test('returns unknownError when access_token missing', () async {
        setupDiscoverySuccess();
        when(
          () => mockClient.request(
            'POST',
            Uri.parse('https://idp.example.com/oauth2/token'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse({'token_type': 'Bearer'}),
        );

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });

      test('returns unknownError on non-invalid_grant error', () async {
        setupDiscoverySuccess();
        when(
          () => mockClient.request(
            'POST',
            Uri.parse('https://idp.example.com/oauth2/token'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(
            {'error': 'server_error'},
            statusCode: 500,
          ),
        );

        final result = await service.refresh(
          discoveryUrl: discoveryUrl,
          refreshToken: refreshToken,
          clientId: clientId,
        );

        expect(result, isA<TokenRefreshFailure>());
        final failure = result as TokenRefreshFailure;
        expect(failure.reason, TokenRefreshFailureReason.unknownError);
      });
    });
  });
}
