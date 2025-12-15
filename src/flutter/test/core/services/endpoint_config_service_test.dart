import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/saved_endpoint.dart';
import 'package:soliplex/core/services/endpoint_config_service.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';

/// In-memory storage for testing.
class MockSecureStorage implements SecureStorageService {
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
  group('SavedEndpoint', () {
    test('creates new endpoint with factory', () {
      final config = SavedEndpoint.create(
        config: const CompletionsEndpoint(
          url: 'https://api.openai.com',
          label: 'My OpenAI',
          model: 'gpt-4',
        ),
      );

      expect(config.id, isNotEmpty);
      expect(config.name, 'My OpenAI');
      expect(config.url, 'https://api.openai.com');
      expect(config.isEnabled, isTrue);
      expect(config.isCompletions, isTrue);
      expect(config.isAgUi, isFalse);
    });

    test('serializes to JSON', () {
      final config = SavedEndpoint.create(
        config: const AgUiEndpoint(url: 'http://localhost:8080', label: 'Test'),
      );

      final json = config.toJson();

      expect(json['id'], config.id);
      expect(json['config']['label'], 'Test');
      expect(json['config']['url'], 'http://localhost:8080');
      expect(json['config']['type'], 'agUi');
      expect(json['is_enabled'], isTrue);
    });

    test('deserializes from JSON', () {
      final json = {
        'id': 'test-id',
        'is_enabled': true,
        'created_at': '2024-01-01T00:00:00.000Z',
        'updated_at': '2024-01-02T00:00:00.000Z',
        'notes': 'Some notes',
        'config': {
          'type': 'completions',
          'url': 'https://api.test.com',
          'label': 'Test Endpoint',
          'model': 'gpt-4',
        },
      };

      final config = SavedEndpoint.fromJson(json);

      expect(config.id, 'test-id');
      expect(config.name, 'Test Endpoint');
      expect(config.url, 'https://api.test.com');
      expect(config.isCompletions, isTrue);
      expect(config.notes, 'Some notes');
    });

    test('copyWith updates fields', () {
      final config = SavedEndpoint.create(
        config: const CompletionsEndpoint(
          url: 'http://localhost',
          label: 'Original',
          model: 'gpt-4',
        ),
      );

      final updated = config.copyWith(isEnabled: false, notes: 'Updated notes');

      expect(updated.id, config.id); // ID preserved
      expect(updated.name, 'Original'); // Config preserved
      expect(updated.isEnabled, isFalse);
      expect(updated.notes, 'Updated notes');
    });
  });

  group('EndpointConfigService', () {
    late MockSecureStorage storage;
    late EndpointConfigService service;

    setUp(() {
      storage = MockSecureStorage();
      service = EndpointConfigService(storage);
    });

    test('listEndpoints returns empty list initially', () async {
      final endpoints = await service.listEndpoints();
      expect(endpoints, isEmpty);
    });

    test('saveEndpoint adds new endpoint', () async {
      final config = SavedEndpoint.create(
        config: const CompletionsEndpoint(
          url: 'http://localhost',
          label: 'Test',
          model: 'gpt-4',
        ),
      );

      await service.saveEndpoint(config);
      final endpoints = await service.listEndpoints();

      expect(endpoints.length, 1);
      expect(endpoints[0].id, config.id);
    });

    test('saveEndpoint updates existing endpoint', () async {
      final config = SavedEndpoint.create(
        config: const CompletionsEndpoint(
          url: 'http://localhost',
          label: 'Original',
          model: 'gpt-4',
        ),
      );

      await service.saveEndpoint(config);

      final updatedConfig = config.copyWith(
        config: const CompletionsEndpoint(
          url: 'http://localhost',
          label: 'Updated',
          model: 'gpt-4',
        ),
      );

      await service.saveEndpoint(updatedConfig);

      final endpoints = await service.listEndpoints();

      expect(endpoints.length, 1);
      expect(endpoints[0].name, 'Updated');
    });

    test('getEndpoint returns specific endpoint', () async {
      final config = SavedEndpoint.create(
        config: const CompletionsEndpoint(
          url: 'http://localhost',
          label: 'Test',
          model: 'gpt-4',
        ),
      );

      await service.saveEndpoint(config);
      final retrieved = await service.getEndpoint(config.id);

      expect(retrieved?.id, config.id);
    });

    test('deleteEndpoint removes endpoint', () async {
      final config = SavedEndpoint.create(
        config: const CompletionsEndpoint(
          url: 'http://localhost',
          label: 'Test',
          model: 'gpt-4',
        ),
      );

      await service.saveEndpoint(config);
      await service.deleteEndpoint(config.id);
      final endpoints = await service.listEndpoints();

      expect(endpoints, isEmpty);
    });

    test('listCompletionsEndpoints filters by type', () async {
      await service.saveEndpoint(
        SavedEndpoint.create(
          config: const AgUiEndpoint(
            url: 'http://localhost:8080',
            label: 'AG-UI',
          ),
        ),
      );
      await service.saveEndpoint(
        SavedEndpoint.create(
          config: const CompletionsEndpoint(
            url: 'https://api.openai.com',
            label: 'OpenAI',
            model: 'gpt-4',
          ),
        ),
      );

      final completions = await service.listCompletionsEndpoints();
      expect(completions.length, 1);
      expect(completions.first.isCompletions, isTrue);
    });
  });
}
