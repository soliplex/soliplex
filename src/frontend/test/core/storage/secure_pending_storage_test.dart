import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';
import 'package:soliplex_frontend/core/storage/secure_pending_storage.dart';

import '../../helpers/auth_test_helpers.dart';

class MockFlutterSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  // Key verification: Tests verifying storage contract use exact key
  // 'pending_auth_state'. Tests focused on return values use any().
  group('SecurePendingStorage', () {
    late MockFlutterSecureStorage mockStorage;
    late SecurePendingStorage pendingStorage;

    setUp(() {
      mockStorage = MockFlutterSecureStorage();
      pendingStorage = SecurePendingStorage(storage: mockStorage);
    });

    group('getPendingAuth', () {
      test('returns PendingAuthFound when auth state exists', () async {
        final json = jsonEncode({
          'serverId': 'https://api.example.com',
          'authSystem': testAuthSystem.toJson(),
        });
        // Use exact key to verify contract
        when(() => mockStorage.read(key: 'pending_auth_state'))
            .thenAnswer((_) async => json);

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<PendingAuthFound>());
        final found = result as PendingAuthFound;
        expect(found.serverId, 'https://api.example.com');
        expect(found.authSystem.id, 'keycloak');
        expect(found.authSystem.title, 'Keycloak');
        expect(found.authSystem.serverUrl, 'https://auth.example.com');
        expect(found.authSystem.clientId, 'test-client');
      });

      test('returns NoPendingAuth when storage is empty', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => null);

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
      });

      test('returns NoPendingAuth and clears corrupted JSON', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => 'invalid json');
        // Use exact key to verify delete contract
        when(() => mockStorage.delete(key: 'pending_auth_state'))
            .thenAnswer((_) async {});

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
        verify(() => mockStorage.delete(key: 'pending_auth_state')).called(1);
      });

      test('returns NoPendingAuth and clears data with wrong types', () async {
        // Valid JSON but wrong types (serverId should be String, not int)
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => '{"serverId": 123, "authSystem": {}}');
        when(() => mockStorage.delete(key: any(named: 'key')))
            .thenAnswer((_) async {});

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
        verify(() => mockStorage.delete(key: any(named: 'key'))).called(1);
      });

      test('returns NoPendingAuth and clears when authSystem missing fields',
          () async {
        // Valid JSON structure but authSystem missing required fields.
        // Treated as corruption - return NoPendingAuth and clear the data.
        final json = jsonEncode({
          'serverId': 'https://api.example.com',
          'authSystem': {'id': 'keycloak'}, // Missing title, server_url, etc.
        });
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => json);
        when(() => mockStorage.delete(key: any(named: 'key')))
            .thenAnswer((_) async {});

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
        verify(() => mockStorage.delete(key: any(named: 'key'))).called(1);
      });

      test('throws when storage throws', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenThrow(Exception('Keychain locked'));

        expect(
          () => pendingStorage.getPendingAuth(),
          throwsException,
        );
      });

      test('returns NoPendingAuth and clears when JSON is array', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => '[1, 2, 3]');
        when(() => mockStorage.delete(key: any(named: 'key')))
            .thenAnswer((_) async {});

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
        verify(() => mockStorage.delete(key: any(named: 'key'))).called(1);
      });
    });

    group('savePendingAuth', () {
      test('throws when storage throws', () async {
        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenThrow(Exception('Keychain locked'));

        expect(
          () => pendingStorage.savePendingAuth('server-123', testAuthSystem),
          throwsException,
        );
      });
    });

    group('clearPendingAuth', () {
      test('throws when storage throws', () async {
        when(() => mockStorage.delete(key: any(named: 'key')))
            .thenThrow(Exception('Keychain locked'));

        expect(
          () => pendingStorage.clearPendingAuth(),
          throwsException,
        );
      });
    });

    group('behavior', () {
      test('save then get returns saved value', () async {
        String? storedValue;

        // Use exact key to verify write contract
        when(
          () => mockStorage.write(
            key: 'pending_auth_state',
            value: any(named: 'value'),
          ),
        ).thenAnswer((invocation) async {
          storedValue = invocation.namedArguments[#value] as String;
        });

        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => storedValue);

        await pendingStorage.savePendingAuth('server-123', testAuthSystem);
        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<PendingAuthFound>());
        final found = result as PendingAuthFound;
        expect(found.serverId, 'server-123');
        expect(found.authSystem.id, 'keycloak');
      });

      test('save then clear then get returns nothing', () async {
        String? storedValue;

        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenAnswer((invocation) async {
          storedValue = invocation.namedArguments[#value] as String;
        });

        when(() => mockStorage.delete(key: any(named: 'key')))
            .thenAnswer((_) async {
          storedValue = null;
        });

        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => storedValue);

        await pendingStorage.savePendingAuth('server-123', testAuthSystem);
        await pendingStorage.clearPendingAuth();
        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
      });

      test('get without save returns nothing', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => null);

        final result = await pendingStorage.getPendingAuth();

        expect(result, isA<NoPendingAuth>());
      });
    });
  });
}
