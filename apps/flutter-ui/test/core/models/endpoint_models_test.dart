import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/models/endpoint_models.dart';

void main() {
  group('AgUiEndpoint', () {
    test('props include required fields', () {
      const endpoint = AgUiEndpoint(
        url: 'http://example.com',
        label: 'Test Server',
      );

      expect(endpoint.props, [
        EndpointType.agUi,
        'http://example.com',
        'Test Server',
        true,
      ]);
    });

    test('toJson/fromJson works', () {
      const endpoint = AgUiEndpoint(
        url: 'http://example.com',
        label: 'Test Server',
        requiresAuth: false,
      );

      final json = endpoint.toJson();
      final fromJson = EndpointConfiguration.fromJson(json);

      expect(fromJson, equals(endpoint));
      expect(fromJson, isA<AgUiEndpoint>());
    });
  });

  group('CompletionsEndpoint', () {
    test('props include required fields', () {
      const endpoint = CompletionsEndpoint(
        url: 'https://api.openai.com',
        label: 'OpenAI',
        model: 'gpt-4',
        availableModels: ['gpt-4', 'gpt-3.5'],
      );

      expect(endpoint.props, [
        EndpointType.completions,
        'https://api.openai.com',
        'OpenAI',
        'gpt-4',
        ['gpt-4', 'gpt-3.5'],
        true,
      ]);
    });

    test('toJson/fromJson works', () {
      const endpoint = CompletionsEndpoint(
        url: 'https://api.openai.com',
        label: 'OpenAI',
        model: 'gpt-4',
      );

      final json = endpoint.toJson();
      final fromJson = EndpointConfiguration.fromJson(json);

      expect(fromJson, equals(endpoint));
      expect(fromJson, isA<CompletionsEndpoint>());
    });
  });
}
