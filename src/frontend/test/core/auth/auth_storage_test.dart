import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';

class MockFlutterSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  late MockFlutterSecureStorage mockStorage;
  late AuthStorage authStorage;

  setUp(() {
    mockStorage = MockFlutterSecureStorage();
    authStorage = AuthStorage(storage: mockStorage);
  });

  group('saveTokens', () {
    test('writes all token fields to storage', () async {
      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});

      final expiresAt = DateTime(2025, 12, 31, 12);

      await authStorage.saveTokens(
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
        expiresAt: expiresAt,
        issuerId: 'issuer-1',
        issuerDiscoveryUrl: 'https://idp.example.com/.well-known',
        idToken: 'id-token',
      );

      verify(
        () => mockStorage.write(
          key: AuthStorageKeys.accessToken,
          value: 'access-token',
        ),
      ).called(1);
      verify(
        () => mockStorage.write(
          key: AuthStorageKeys.refreshToken,
          value: 'refresh-token',
        ),
      ).called(1);
      verify(
        () => mockStorage.write(
          key: AuthStorageKeys.expiresAt,
          value: expiresAt.toIso8601String(),
        ),
      ).called(1);
      verify(
        () => mockStorage.write(
          key: AuthStorageKeys.issuerId,
          value: 'issuer-1',
        ),
      ).called(1);
      verify(
        () => mockStorage.write(
          key: AuthStorageKeys.issuerDiscoveryUrl,
          value: 'https://idp.example.com/.well-known',
        ),
      ).called(1);
      verify(
        () => mockStorage.write(
          key: AuthStorageKeys.idToken,
          value: 'id-token',
        ),
      ).called(1);
    });

    test('does not write idToken when null', () async {
      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});

      await authStorage.saveTokens(
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
        expiresAt: DateTime(2025, 12, 31),
        issuerId: 'issuer-1',
        issuerDiscoveryUrl: 'https://idp.example.com/.well-known',
      );

      verifyNever(
        () => mockStorage.write(
          key: AuthStorageKeys.idToken,
          value: any(named: 'value'),
        ),
      );
    });
  });

  group('loadTokens', () {
    test('returns StoredTokens when all required fields exist', () async {
      final expiresAt = DateTime(2025, 12, 31, 12);

      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => expiresAt.toIso8601String());
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => 'id-token');

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNotNull);
      expect(tokens!.accessToken, 'access-token');
      expect(tokens.refreshToken, 'refresh-token');
      expect(tokens.expiresAt, expiresAt);
      expect(tokens.issuerId, 'issuer-1');
      expect(tokens.issuerDiscoveryUrl, 'https://idp.example.com/.well-known');
      expect(tokens.idToken, 'id-token');
    });

    test('returns null when accessToken is missing', () async {
      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => null);
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => '2025-12-31T12:00:00.000');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNull);
    });

    test('returns null when refreshToken is missing', () async {
      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => null);
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => '2025-12-31T12:00:00.000');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNull);
    });

    test('returns null when expiresAt is missing', () async {
      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => null);
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNull);
    });

    test('returns null when expiresAt is malformed', () async {
      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => 'not-a-date');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNull);
    });

    test('returns tokens with null idToken when idToken is not stored',
        () async {
      final expiresAt = DateTime(2025, 12, 31, 12);

      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => expiresAt.toIso8601String());
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNotNull);
      expect(tokens!.idToken, isNull);
    });

    test('returns null when issuerId is missing', () async {
      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => '2025-12-31T12:00:00.000');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => null);
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => 'https://idp.example.com/.well-known');
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNull);
    });

    test('returns null when issuerDiscoveryUrl is missing', () async {
      when(() => mockStorage.read(key: AuthStorageKeys.accessToken))
          .thenAnswer((_) async => 'access-token');
      when(() => mockStorage.read(key: AuthStorageKeys.refreshToken))
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockStorage.read(key: AuthStorageKeys.expiresAt))
          .thenAnswer((_) async => '2025-12-31T12:00:00.000');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerId))
          .thenAnswer((_) async => 'issuer-1');
      when(() => mockStorage.read(key: AuthStorageKeys.issuerDiscoveryUrl))
          .thenAnswer((_) async => null);
      when(() => mockStorage.read(key: AuthStorageKeys.idToken))
          .thenAnswer((_) async => null);

      final tokens = await authStorage.loadTokens();

      expect(tokens, isNull);
    });
  });

  group('clearTokens', () {
    test('deletes all token keys from storage', () async {
      when(() => mockStorage.delete(key: any(named: 'key')))
          .thenAnswer((_) async {});

      await authStorage.clearTokens();

      verify(() => mockStorage.delete(key: AuthStorageKeys.accessToken))
          .called(1);
      verify(() => mockStorage.delete(key: AuthStorageKeys.refreshToken))
          .called(1);
      verify(() => mockStorage.delete(key: AuthStorageKeys.idToken)).called(1);
      verify(() => mockStorage.delete(key: AuthStorageKeys.expiresAt))
          .called(1);
      verify(() => mockStorage.delete(key: AuthStorageKeys.issuerId)).called(1);
      verify(() => mockStorage.delete(key: AuthStorageKeys.issuerDiscoveryUrl))
          .called(1);
    });
  });

  group('StoredTokens', () {
    test('stores all provided values', () {
      final expiresAt = DateTime(2025, 12, 31, 12);
      final tokens = StoredTokens(
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: expiresAt,
        issuerId: 'issuer-1',
        issuerDiscoveryUrl: 'https://idp.example.com/.well-known',
        idToken: 'id-token',
      );

      expect(tokens.accessToken, 'access');
      expect(tokens.refreshToken, 'refresh');
      expect(tokens.expiresAt, expiresAt);
      expect(tokens.issuerId, 'issuer-1');
      expect(tokens.issuerDiscoveryUrl, 'https://idp.example.com/.well-known');
      expect(tokens.idToken, 'id-token');
    });

    test('allows null idToken', () {
      final tokens = StoredTokens(
        accessToken: 'access',
        refreshToken: 'refresh',
        expiresAt: DateTime(2025, 12, 31),
        issuerId: 'issuer-1',
        issuerDiscoveryUrl: 'https://idp.example.com/.well-known',
      );

      expect(tokens.idToken, isNull);
    });
  });
}
