import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/core/services/secure_storage_service.dart';

/// In-memory implementation for testing
class TestSecureStorageService implements SecureStorageService {
  final Map<String, String> _storage = {};

  @override
  Future<void> write(String key, String value) async {
    _storage[key] = value;
  }

  @override
  Future<String?> read(String key) async {
    return _storage[key];
  }

  @override
  Future<void> delete(String key) async {
    _storage.remove(key);
  }

  @override
  Future<void> deleteAll() async {
    _storage.clear();
  }

  @override
  Future<bool> containsKey(String key) async {
    return _storage.containsKey(key);
  }

  @override
  Future<Map<String, String>> readAll() async {
    return Map.from(_storage);
  }
}

void main() {
  group('StorageKeys', () {
    test('serverAccessToken generates correct key', () {
      expect(
        StorageKeys.serverAccessToken('test-id'),
        'server_test-id_access_token',
      );
    });

    test('serverRefreshToken generates correct key', () {
      expect(
        StorageKeys.serverRefreshToken('test-id'),
        'server_test-id_refresh_token',
      );
    });

    test('serverTokenExpiry generates correct key', () {
      expect(
        StorageKeys.serverTokenExpiry('test-id'),
        'server_test-id_token_expiry',
      );
    });

    test('endpointApiKey generates correct key', () {
      expect(
        StorageKeys.endpointApiKey('openai-1'),
        'endpoint_openai-1_api_key',
      );
    });
  });

  group('TokenStorageExtension', () {
    late TestSecureStorageService storage;

    setUp(() {
      storage = TestSecureStorageService();
    });

    group('token storage', () {
      test('stores and retrieves access token', () async {
        await storage.storeTokens(
          serverId: 'server-1',
          accessToken: 'test-token',
        );

        expect(await storage.getAccessToken('server-1'), 'test-token');
      });

      test('stores and retrieves refresh token', () async {
        await storage.storeTokens(
          serverId: 'server-1',
          accessToken: 'access',
          refreshToken: 'refresh-token',
        );

        expect(await storage.getRefreshToken('server-1'), 'refresh-token');
      });

      test('stores and retrieves token expiry', () async {
        final expiry = DateTime.utc(2025, 12, 31);
        await storage.storeTokens(
          serverId: 'server-1',
          accessToken: 'access',
          expiresAt: expiry,
        );

        expect(await storage.getTokenExpiry('server-1'), expiry);
      });

      test('clears tokens for a server', () async {
        await storage.storeTokens(
          serverId: 'server-1',
          accessToken: 'access',
          refreshToken: 'refresh',
          expiresAt: DateTime.now(),
        );

        await storage.clearTokens('server-1');

        expect(await storage.getAccessToken('server-1'), isNull);
        expect(await storage.getRefreshToken('server-1'), isNull);
        expect(await storage.getTokenExpiry('server-1'), isNull);
      });
    });

    group('API key storage', () {
      test('stores and retrieves API key', () async {
        await storage.storeApiKey(
          endpointId: 'openai-1',
          apiKey: 'sk-test-key-123',
        );

        expect(await storage.getApiKey('openai-1'), 'sk-test-key-123');
      });

      test('hasApiKey returns true when key exists', () async {
        await storage.storeApiKey(
          endpointId: 'openai-1',
          apiKey: 'sk-test-key',
        );

        expect(await storage.hasApiKey('openai-1'), isTrue);
      });

      test('hasApiKey returns false when key does not exist', () async {
        expect(await storage.hasApiKey('nonexistent'), isFalse);
      });

      test('deleteApiKey removes the key', () async {
        await storage.storeApiKey(
          endpointId: 'openai-1',
          apiKey: 'sk-test-key',
        );

        await storage.deleteApiKey('openai-1');

        expect(await storage.hasApiKey('openai-1'), isFalse);
        expect(await storage.getApiKey('openai-1'), isNull);
      });

      test('stores separate API keys for different endpoints', () async {
        await storage.storeApiKey(endpointId: 'openai-1', apiKey: 'key-1');
        await storage.storeApiKey(endpointId: 'anthropic-1', apiKey: 'key-2');

        expect(await storage.getApiKey('openai-1'), 'key-1');
        expect(await storage.getApiKey('anthropic-1'), 'key-2');
      });

      test('updating API key overwrites previous value', () async {
        await storage.storeApiKey(endpointId: 'openai-1', apiKey: 'old-key');
        await storage.storeApiKey(endpointId: 'openai-1', apiKey: 'new-key');

        expect(await storage.getApiKey('openai-1'), 'new-key');
      });
    });

    group('server history', () {
      test('stores and retrieves server history', () async {
        final history = [
          {'id': 'server-1', 'url': 'http://localhost:8080'},
          {'id': 'server-2', 'url': 'http://example.com'},
        ];

        await storage.storeServerHistory(history);

        final retrieved = await storage.loadServerHistory();
        expect(retrieved, history);
      });

      test('returns empty list when no history', () async {
        final history = await storage.loadServerHistory();
        expect(history, isEmpty);
      });
    });

    group('current server ID', () {
      test('stores and retrieves current server ID', () async {
        await storage.storeCurrentServerId('server-1');
        expect(await storage.getCurrentServerId(), 'server-1');
      });

      test('clears current server ID when null', () async {
        await storage.storeCurrentServerId('server-1');
        await storage.storeCurrentServerId(null);
        expect(await storage.getCurrentServerId(), isNull);
      });
    });
  });
}
