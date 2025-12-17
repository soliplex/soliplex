import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_storage_gateway.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';

class MockSecureStorageGateway extends Mock implements SecureStorageGateway {}

void main() {
  late MockSecureStorageGateway mockStorage;
  late SecureTokenStorage tokenStorage;

  setUp(() {
    mockStorage = MockSecureStorageGateway();
    tokenStorage = SecureTokenStorage(mockStorage);
  });

  group('SecureTokenStorage', () {
    group('setOidcAuthTokenResponse', () {
      test('writes all token fields to storage', () async {
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final expiration = DateTime(2024, 1, 15, 12, 0);
        final tokenResponse = OidcAuthTokenResponse(
          idToken: 'test-id-token',
          accessToken: 'test-access-token',
          accessTokenExpiration: expiration,
          refreshToken: 'test-refresh-token',
        );

        await tokenStorage.setOidcAuthTokenResponse(tokenResponse);

        verify(() => mockStorage.write('oidc.id', 'test-id-token')).called(1);
        verify(
          () => mockStorage.write('oidc.access', 'test-access-token'),
        ).called(1);
        verify(
          () => mockStorage.write(
            'oidc.expiration',
            '${expiration.millisecondsSinceEpoch}',
          ),
        ).called(1);
        verify(
          () => mockStorage.write('oidc.refresh', 'test-refresh-token'),
        ).called(1);
      });
    });

    group('getOidcAuthTokenResponse', () {
      test('returns token response when all fields exist', () async {
        final expiration = DateTime(2024, 1, 15, 12, 0);

        when(
          () => mockStorage.read('oidc.id'),
        ).thenAnswer((_) async => 'test-id-token');
        when(
          () => mockStorage.read('oidc.access'),
        ).thenAnswer((_) async => 'test-access-token');
        when(
          () => mockStorage.read('oidc.expiration'),
        ).thenAnswer((_) async => '${expiration.millisecondsSinceEpoch}');
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => 'test-refresh-token');

        final result = await tokenStorage.getOidcAuthTokenResponse();

        expect(result, isNotNull);
        expect(result!.idToken, equals('test-id-token'));
        expect(result.accessToken, equals('test-access-token'));
        expect(result.accessTokenExpiration, equals(expiration));
        expect(result.refreshToken, equals('test-refresh-token'));
      });

      test('returns null when idToken is missing', () async {
        when(() => mockStorage.read('oidc.id')).thenAnswer((_) async => null);
        when(
          () => mockStorage.read('oidc.access'),
        ).thenAnswer((_) async => 'test-access-token');
        when(
          () => mockStorage.read('oidc.expiration'),
        ).thenAnswer((_) async => '1705319200000');
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => 'test-refresh-token');

        final result = await tokenStorage.getOidcAuthTokenResponse();

        expect(result, isNull);
      });

      test('returns null when accessToken is missing', () async {
        when(
          () => mockStorage.read('oidc.id'),
        ).thenAnswer((_) async => 'test-id-token');
        when(
          () => mockStorage.read('oidc.access'),
        ).thenAnswer((_) async => null);
        when(
          () => mockStorage.read('oidc.expiration'),
        ).thenAnswer((_) async => '1705319200000');
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => 'test-refresh-token');

        final result = await tokenStorage.getOidcAuthTokenResponse();

        expect(result, isNull);
      });

      test('returns null when expiration is missing', () async {
        when(
          () => mockStorage.read('oidc.id'),
        ).thenAnswer((_) async => 'test-id-token');
        when(
          () => mockStorage.read('oidc.access'),
        ).thenAnswer((_) async => 'test-access-token');
        when(
          () => mockStorage.read('oidc.expiration'),
        ).thenAnswer((_) async => null);
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => 'test-refresh-token');

        final result = await tokenStorage.getOidcAuthTokenResponse();

        expect(result, isNull);
      });

      test('returns null when refreshToken is missing', () async {
        when(
          () => mockStorage.read('oidc.id'),
        ).thenAnswer((_) async => 'test-id-token');
        when(
          () => mockStorage.read('oidc.access'),
        ).thenAnswer((_) async => 'test-access-token');
        when(
          () => mockStorage.read('oidc.expiration'),
        ).thenAnswer((_) async => '1705319200000');
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => null);

        final result = await tokenStorage.getOidcAuthTokenResponse();

        expect(result, isNull);
      });

      test('returns null when all fields are missing', () async {
        when(() => mockStorage.read(any())).thenAnswer((_) async => null);

        final result = await tokenStorage.getOidcAuthTokenResponse();

        expect(result, isNull);
      });
    });

    group('getOidcRefreshToken', () {
      test('returns refresh token when it exists', () async {
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => 'test-refresh-token');

        final result = await tokenStorage.getOidcRefreshToken();

        expect(result, equals('test-refresh-token'));
      });

      test('returns null when refresh token does not exist', () async {
        when(
          () => mockStorage.read('oidc.refresh'),
        ).thenAnswer((_) async => null);

        final result = await tokenStorage.getOidcRefreshToken();

        expect(result, isNull);
      });
    });

    group('deleteOidcAuthTokenResponse', () {
      test('deletes all token fields from storage', () async {
        when(() => mockStorage.delete(any())).thenAnswer((_) async {});

        await tokenStorage.deleteOidcAuthTokenResponse();

        verify(() => mockStorage.delete('oidc.id')).called(1);
        verify(() => mockStorage.delete('oidc.access')).called(1);
        verify(() => mockStorage.delete('oidc.expiration')).called(1);
        verify(() => mockStorage.delete('oidc.refresh')).called(1);
      });
    });
  });
}
