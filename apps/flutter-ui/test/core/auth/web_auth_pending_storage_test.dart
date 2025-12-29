import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:soliplex/core/auth/web_auth_pending_storage.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';

class MockSecureStorageService extends Mock implements SecureStorageService {}

void main() {
  late MockSecureStorageService mockStorage;
  late WebAuthPendingStorage pendingStorage;

  setUp(() {
    mockStorage = MockSecureStorageService();
    pendingStorage = WebAuthPendingStorage(mockStorage);
  });

  group('PendingWebAuth', () {
    test('creates with required fields', () {
      final pending = PendingWebAuth(
        serverId: 'server-1',
        providerId: 'keycloak',
        codeVerifier: 'verifier123',
        state: 'state456',
        tokenEndpoint: 'https://auth.example.com/token',
        clientId: 'my-client',
        redirectUrl: 'https://app.example.com/callback',
        createdAt: DateTime.now(),
      );

      expect(pending.serverId, equals('server-1'));
      expect(pending.providerId, equals('keycloak'));
      expect(pending.codeVerifier, equals('verifier123'));
      expect(pending.state, equals('state456'));
    });

    test('isExpired returns false for fresh auth', () {
      final pending = PendingWebAuth(
        serverId: 'server-1',
        providerId: 'keycloak',
        codeVerifier: 'verifier123',
        state: 'state456',
        tokenEndpoint: 'https://auth.example.com/token',
        clientId: 'my-client',
        redirectUrl: 'https://app.example.com/callback',
        createdAt: DateTime.now(),
      );

      expect(pending.isExpired, isFalse);
    });

    test('isExpired returns true for old auth', () {
      final pending = PendingWebAuth(
        serverId: 'server-1',
        providerId: 'keycloak',
        codeVerifier: 'verifier123',
        state: 'state456',
        tokenEndpoint: 'https://auth.example.com/token',
        clientId: 'my-client',
        redirectUrl: 'https://app.example.com/callback',
        createdAt: DateTime.now().subtract(const Duration(minutes: 10)),
      );

      expect(pending.isExpired, isTrue);
    });

    test('toJson serializes correctly', () {
      final createdAt = DateTime(2024, 1, 15, 10, 30);
      final pending = PendingWebAuth(
        serverId: 'server-1',
        providerId: 'keycloak',
        codeVerifier: 'verifier123',
        state: 'state456',
        tokenEndpoint: 'https://auth.example.com/token',
        clientId: 'my-client',
        redirectUrl: 'https://app.example.com/callback',
        createdAt: createdAt,
      );

      final json = pending.toJson();

      expect(json['serverId'], equals('server-1'));
      expect(json['providerId'], equals('keycloak'));
      expect(json['codeVerifier'], equals('verifier123'));
      expect(json['state'], equals('state456'));
      expect(json['tokenEndpoint'], equals('https://auth.example.com/token'));
      expect(json['clientId'], equals('my-client'));
      expect(json['redirectUrl'], equals('https://app.example.com/callback'));
      expect(json['createdAt'], equals(createdAt.toIso8601String()));
    });

    test('fromJson deserializes correctly', () {
      final json = {
        'serverId': 'server-1',
        'providerId': 'keycloak',
        'codeVerifier': 'verifier123',
        'state': 'state456',
        'tokenEndpoint': 'https://auth.example.com/token',
        'clientId': 'my-client',
        'redirectUrl': 'https://app.example.com/callback',
        'createdAt': '2024-01-15T10:30:00.000',
      };

      final pending = PendingWebAuth.fromJson(json);

      expect(pending.serverId, equals('server-1'));
      expect(pending.providerId, equals('keycloak'));
      expect(pending.codeVerifier, equals('verifier123'));
      expect(pending.state, equals('state456'));
      expect(pending.tokenEndpoint, equals('https://auth.example.com/token'));
      expect(pending.clientId, equals('my-client'));
      expect(pending.redirectUrl, equals('https://app.example.com/callback'));
    });

    test('toString masks sensitive data', () {
      final pending = PendingWebAuth(
        serverId: 'server-1',
        providerId: 'keycloak',
        codeVerifier: 'verifier123456789',
        state: 'state456789012345',
        tokenEndpoint: 'https://auth.example.com/token',
        clientId: 'my-client',
        redirectUrl: 'https://app.example.com/callback',
        createdAt: DateTime.now(),
      );

      final str = pending.toString();
      expect(str, contains('server-1'));
      expect(str, contains('keycloak'));
      expect(str, contains('state456'));
      expect(str, contains('...'));
      // Should not contain full state
      expect(str.contains('state456789012345'), isFalse);
    });
  });

  group('WebAuthPendingStorage', () {
    group('savePendingAuth', () {
      test('saves pending auth to storage', () async {
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final pending = PendingWebAuth(
          serverId: 'server-1',
          providerId: 'keycloak',
          codeVerifier: 'verifier123',
          state: 'state456',
          tokenEndpoint: 'https://auth.example.com/token',
          clientId: 'my-client',
          redirectUrl: 'https://app.example.com/callback',
          createdAt: DateTime.now(),
        );

        await pendingStorage.savePendingAuth(pending);

        verify(() => mockStorage.write('pending_web_auth', any())).called(1);
      });
    });

    group('getPendingAuth', () {
      test('returns null when no pending auth exists', () async {
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => null);

        final result = await pendingStorage.getPendingAuth();

        expect(result, isNull);
      });

      test('returns pending auth when exists', () async {
        final json =
            '''
        {
          "serverId": "server-1",
          "providerId": "keycloak",
          "codeVerifier": "verifier123",
          "state": "state456",
          "tokenEndpoint": "https://auth.example.com/token",
          "clientId": "my-client",
          "redirectUrl": "https://app.example.com/callback",
          "createdAt": "${DateTime.now().toIso8601String()}"
        }
        ''';
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => json);

        final result = await pendingStorage.getPendingAuth();

        expect(result, isNotNull);
        expect(result!.serverId, equals('server-1'));
        expect(result.providerId, equals('keycloak'));
      });

      test('returns null and clears storage when expired', () async {
        final oldDate = DateTime.now().subtract(const Duration(minutes: 10));
        final json =
            '''
        {
          "serverId": "server-1",
          "providerId": "keycloak",
          "codeVerifier": "verifier123",
          "state": "state456",
          "tokenEndpoint": "https://auth.example.com/token",
          "clientId": "my-client",
          "redirectUrl": "https://app.example.com/callback",
          "createdAt": "${oldDate.toIso8601String()}"
        }
        ''';
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => json);
        when(
          () => mockStorage.delete('pending_web_auth'),
        ).thenAnswer((_) async {});

        final result = await pendingStorage.getPendingAuth();

        expect(result, isNull);
        verify(() => mockStorage.delete('pending_web_auth')).called(1);
      });

      test('returns null and clears storage when JSON is invalid', () async {
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => 'invalid json');
        when(
          () => mockStorage.delete('pending_web_auth'),
        ).thenAnswer((_) async {});

        final result = await pendingStorage.getPendingAuth();

        expect(result, isNull);
        verify(() => mockStorage.delete('pending_web_auth')).called(1);
      });
    });

    group('clearPendingAuth', () {
      test('deletes pending auth from storage', () async {
        when(
          () => mockStorage.delete('pending_web_auth'),
        ).thenAnswer((_) async {});

        await pendingStorage.clearPendingAuth();

        verify(() => mockStorage.delete('pending_web_auth')).called(1);
      });
    });

    group('hasPendingAuth', () {
      test('returns true when valid pending auth exists', () async {
        final json =
            '''
        {
          "serverId": "server-1",
          "providerId": "keycloak",
          "codeVerifier": "verifier123",
          "state": "state456",
          "tokenEndpoint": "https://auth.example.com/token",
          "clientId": "my-client",
          "redirectUrl": "https://app.example.com/callback",
          "createdAt": "${DateTime.now().toIso8601String()}"
        }
        ''';
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => json);

        final result = await pendingStorage.hasPendingAuth();

        expect(result, isTrue);
      });

      test('returns false when no pending auth exists', () async {
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => null);

        final result = await pendingStorage.hasPendingAuth();

        expect(result, isFalse);
      });
    });

    group('validateState', () {
      test('returns true when state matches', () async {
        final json =
            '''
        {
          "serverId": "server-1",
          "providerId": "keycloak",
          "codeVerifier": "verifier123",
          "state": "correct_state",
          "tokenEndpoint": "https://auth.example.com/token",
          "clientId": "my-client",
          "redirectUrl": "https://app.example.com/callback",
          "createdAt": "${DateTime.now().toIso8601String()}"
        }
        ''';
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => json);

        final result = await pendingStorage.validateState('correct_state');

        expect(result, isTrue);
      });

      test('returns false when state does not match', () async {
        final json =
            '''
        {
          "serverId": "server-1",
          "providerId": "keycloak",
          "codeVerifier": "verifier123",
          "state": "correct_state",
          "tokenEndpoint": "https://auth.example.com/token",
          "clientId": "my-client",
          "redirectUrl": "https://app.example.com/callback",
          "createdAt": "${DateTime.now().toIso8601String()}"
        }
        ''';
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => json);

        final result = await pendingStorage.validateState('wrong_state');

        expect(result, isFalse);
      });

      test('returns false when no pending auth exists', () async {
        when(
          () => mockStorage.read('pending_web_auth'),
        ).thenAnswer((_) async => null);

        final result = await pendingStorage.validateState('any_state');

        expect(result, isFalse);
      });
    });
  });
}
