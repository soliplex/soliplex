import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';
import 'package:soliplex_frontend/core/storage/secure_pending_storage.dart';

class MockFlutterSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  group('SecurePendingStorage', () {
    late MockFlutterSecureStorage mockStorage;
    late SecurePendingStorage pendingStorage;

    setUp(() {
      mockStorage = MockFlutterSecureStorage();
      pendingStorage = SecurePendingStorage(storage: mockStorage);
    });

    group('getPendingServerId', () {
      test('returns PendingServerFound when server ID exists', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => 'https://api.example.com');

        final result = await pendingStorage.getPendingServerId();

        expect(result, isA<PendingServerFound>());
        expect(
          (result as PendingServerFound).serverId,
          'https://api.example.com',
        );
      });

      test('returns NoPendingServer when server ID is null', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => null);

        final result = await pendingStorage.getPendingServerId();

        expect(result, isA<NoPendingServer>());
      });

      test('throws when storage throws', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenThrow(Exception('Keychain locked'));

        expect(
          () => pendingStorage.getPendingServerId(),
          throwsException,
        );
      });
    });

    group('behavior', () {
      test('save then get returns saved value', () async {
        String? storedValue;

        when(
          () => mockStorage.write(
            key: any(named: 'key'),
            value: any(named: 'value'),
          ),
        ).thenAnswer((invocation) async {
          storedValue = invocation.namedArguments[#value] as String;
        });

        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => storedValue);

        await pendingStorage.savePendingServerId('server-123');
        final result = await pendingStorage.getPendingServerId();

        expect(result, isA<PendingServerFound>());
        expect((result as PendingServerFound).serverId, 'server-123');
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

        await pendingStorage.savePendingServerId('server-123');
        await pendingStorage.clearPendingServerId();
        final result = await pendingStorage.getPendingServerId();

        expect(result, isA<NoPendingServer>());
      });

      test('get without save returns nothing', () async {
        when(() => mockStorage.read(key: any(named: 'key')))
            .thenAnswer((_) async => null);

        final result = await pendingStorage.getPendingServerId();

        expect(result, isA<NoPendingServer>());
      });
    });
  });
}
