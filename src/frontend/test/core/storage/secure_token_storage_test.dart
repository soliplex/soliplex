import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/storage/secure_token_storage.dart';

class MockFlutterSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  late MockFlutterSecureStorage mockStorage;
  late SecureTokenStorage tokenStorage;

  setUp(() {
    mockStorage = MockFlutterSecureStorage();
    tokenStorage = SecureTokenStorage(storage: mockStorage);
  });

  AuthToken createToken({
    String accessToken = 'access-123',
    String? refreshToken = 'refresh-456',
    DateTime? expiresAt,
  }) {
    return AuthToken(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: expiresAt ?? DateTime.utc(2025, 12, 31),
    );
  }

  group('SecureTokenStorage', () {
    group('read', () {
      test('returns TokenFound when token exists', () async {
        final token = createToken();
        final json = jsonEncode(token.toJson());

        when(() => mockStorage.read(key: 'auth_token_server1'))
            .thenAnswer((_) async => json);

        final result = await tokenStorage.read('server1');

        expect(result, isA<TokenFound>());
        final found = result as TokenFound;
        expect(found.token.accessToken, equals('access-123'));
        expect(found.token.refreshToken, equals('refresh-456'));
      });

      test('returns TokenNotFound when no token exists', () async {
        when(() => mockStorage.read(key: 'auth_token_server1'))
            .thenAnswer((_) async => null);

        final result = await tokenStorage.read('server1');

        expect(result, isA<TokenNotFound>());
      });

      test('uses serverId in key', () async {
        when(() => mockStorage.read(key: 'auth_token_https://api.example.com'))
            .thenAnswer((_) async => null);

        await tokenStorage.read('https://api.example.com');

        verify(
          () => mockStorage.read(key: 'auth_token_https://api.example.com'),
        ).called(1);
      });
    });

    group('write', () {
      test('stores token as JSON', () async {
        final token = createToken();

        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenAnswer((_) async {});

        await tokenStorage.write('server1', token);

        final captured = verify(
          () => mockStorage.write(
            key: captureAny(named: 'key'),
            value: captureAny(named: 'value'),
          ),
        ).captured;

        expect(captured[0], equals('auth_token_server1'));

        final storedJson = captured[1] as String;
        final decoded = jsonDecode(storedJson) as Map<String, dynamic>;
        expect(decoded['access_token'], equals('access-123'));
        expect(decoded['refresh_token'], equals('refresh-456'));
      });

      test('overwrites existing token', () async {
        final token1 = createToken(accessToken: 'old-token');
        final token2 = createToken(accessToken: 'new-token');

        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenAnswer((_) async {});

        await tokenStorage.write('server1', token1);
        await tokenStorage.write('server1', token2);

        verify(
          () => mockStorage.write(
            key: 'auth_token_server1',
            value: any(named: 'value'),
          ),
        ).called(2);
      });
    });

    group('delete', () {
      test('removes token from storage', () async {
        when(() => mockStorage.delete(key: 'auth_token_server1'))
            .thenAnswer((_) async {});

        await tokenStorage.delete('server1');

        verify(() => mockStorage.delete(key: 'auth_token_server1')).called(1);
      });

      test('uses serverId in key', () async {
        when(
          () => mockStorage.delete(key: 'auth_token_https://api.example.com'),
        ).thenAnswer((_) async {});

        await tokenStorage.delete('https://api.example.com');

        verify(
          () => mockStorage.delete(key: 'auth_token_https://api.example.com'),
        ).called(1);
      });
    });

    group('keyPrefix', () {
      test('uses custom prefix', () async {
        final customStorage = SecureTokenStorage(
          storage: mockStorage,
          keyPrefix: 'custom_',
        );

        when(() => mockStorage.read(key: 'custom_server1'))
            .thenAnswer((_) async => null);

        await customStorage.read('server1');

        verify(() => mockStorage.read(key: 'custom_server1')).called(1);
      });
    });

    group('round trip', () {
      test('read returns same token that was written', () async {
        final originalToken = AuthToken(
          accessToken: 'access-abc',
          refreshToken: 'refresh-xyz',
          expiresAt: DateTime.utc(2025, 6, 15, 10, 30),
          idToken: 'id-token-123',
        );

        String? storedValue;
        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenAnswer((invocation) async {
          storedValue = invocation.namedArguments[#value] as String;
        });
        when(() => mockStorage.read(key: 'auth_token_server1'))
            .thenAnswer((_) async => storedValue);

        await tokenStorage.write('server1', originalToken);
        final result = await tokenStorage.read('server1');

        expect(result, isA<TokenFound>());
        final found = result as TokenFound;
        expect(found.token, equals(originalToken));
      });

      test('round trips token without optional fields', () async {
        final minimalToken = AuthToken(
          accessToken: 'access-only',
          expiresAt: DateTime.utc(2025, 6, 15),
        );

        String? storedValue;
        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenAnswer((invocation) async {
          storedValue = invocation.namedArguments[#value] as String;
        });
        when(() => mockStorage.read(key: 'auth_token_server1'))
            .thenAnswer((_) async => storedValue);

        await tokenStorage.write('server1', minimalToken);
        final result = await tokenStorage.read('server1');

        expect(result, isA<TokenFound>());
        final found = result as TokenFound;
        expect(found.token, equals(minimalToken));
        expect(found.token.refreshToken, isNull);
        expect(found.token.idToken, isNull);
      });
    });

    group('error handling', () {
      test('throws FormatException when stored data is invalid JSON', () async {
        when(() => mockStorage.read(key: 'auth_token_server1'))
            .thenAnswer((_) async => 'not valid json');

        expect(
          () => tokenStorage.read('server1'),
          throwsA(isA<FormatException>()),
        );
      });
    });
  });
}
