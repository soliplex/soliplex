import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/services/completions_probe.dart';

void main() {
  group('CompletionsProbeResult', () {
    test('unreachable factory creates correct result', () {
      final result = CompletionsProbeResult.unreachable(
        'http://example.com',
        'Connection failed',
      );

      expect(result.isReachable, isFalse);
      expect(result.error, 'Connection failed');
      expect(result.url, 'http://example.com');
    });

    test('success factory creates correct result', () {
      final result = CompletionsProbeResult.success(
        url: 'http://example.com',
        requiresApiKey: true,
        models: const ['gpt-4', 'gpt-3.5-turbo'],
      );

      expect(result.isReachable, isTrue);
      expect(result.requiresApiKey, isTrue);
      expect(result.availableModels, ['gpt-4', 'gpt-3.5-turbo']);
      expect(result.defaultModel, 'gpt-4');
      expect(result.isReady, isTrue);
    });

    test('isReady is false when no models and no default', () {
      final result = CompletionsProbeResult.success(
        url: 'http://example.com',
        requiresApiKey: true,
      );

      expect(result.isReady, isFalse);
    });

    test('toEndpointType creates CompletionsEndpoint', () {
      final result = CompletionsProbeResult.success(
        url: 'http://example.com',
        requiresApiKey: true,
        models: const ['gpt-4', 'gpt-3.5-turbo'],
        defaultModel: 'gpt-4',
      );

      final endpoint = result.toEndpointType();

      expect(endpoint, isA<CompletionsEndpoint>());
      expect(endpoint.model, 'gpt-4');
      expect(endpoint.availableModels, ['gpt-4', 'gpt-3.5-turbo']);
      expect(endpoint.supportsModelDiscovery, isTrue);
    });

    test(
      'toEndpointType with no models sets supportsModelDiscovery to false',
      () {
        final result = CompletionsProbeResult.success(
          url: 'http://example.com',
          requiresApiKey: true,
          defaultModel: 'gpt-4',
        );

        final endpoint = result.toEndpointType();

        expect(endpoint.supportsModelDiscovery, isFalse);
      },
    );
  });

  group('CompletionsProbe', () {
    group('probe', () {
      test('discovers models from /v1/models endpoint', () async {
        final client = MockClient((request) async {
          if (request.url.path == '/v1/models') {
            return http.Response(
              jsonEncode({
                'data': [
                  {'id': 'gpt-4'},
                  {'id': 'gpt-3.5-turbo'},
                ],
              }),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('https://api.example.com');

        expect(result.isReachable, isTrue);
        expect(result.availableModels, ['gpt-4', 'gpt-3.5-turbo']);
        expect(result.defaultModel, 'gpt-4');
      });

      test('detects 401 as requiring API key', () async {
        final client = MockClient((request) async {
          return http.Response('Unauthorized', 401);
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('https://api.example.com');

        expect(result.isReachable, isTrue);
        expect(result.requiresApiKey, isTrue);
      });

      test('uses API key in Authorization header', () async {
        String? authHeader;
        final client = MockClient((request) async {
          authHeader = request.headers['Authorization'];
          return http.Response(jsonEncode({'data': []}), 200);
        });

        final probe = CompletionsProbe(httpClient: client);
        await probe.probe('https://api.example.com', apiKey: 'sk-test');

        expect(authHeader, 'Bearer sk-test');
      });

      test('falls back to chat endpoint when models fails', () async {
        final client = MockClient((request) async {
          if (request.url.path == '/v1/models') {
            return http.Response('Not found', 404);
          }
          if (request.url.path == '/v1/chat/completions') {
            // 400 means endpoint exists but request was bad
            return http.Response('Bad request', 400);
          }
          return http.Response('Not found', 404);
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('https://api.example.com');

        expect(result.isReachable, isTrue);
      });

      test('returns unreachable when all probes fail with 404', () async {
        final client = MockClient((request) async {
          return http.Response('Not found', 404);
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('https://api.example.com');

        expect(result.isReachable, isFalse);
        expect(result.error, contains('not found'));
      });

      test('normalizes URL correctly', () async {
        final requests = <Uri>[];
        final client = MockClient((request) async {
          requests.add(request.url);
          return http.Response(jsonEncode({'data': []}), 200);
        });

        final probe = CompletionsProbe(httpClient: client);

        // Test with trailing slash
        await probe.probe('https://api.example.com/');
        expect(requests.last.toString(), 'https://api.example.com/v1/models');

        // Test without protocol (should add https)
        await probe.probe('api.example.com');
        expect(requests.last.toString(), 'https://api.example.com/v1/models');

        // Test localhost (should use http)
        await probe.probe('localhost:11434');
        expect(requests.last.toString(), 'http://localhost:11434/v1/models');
      });

      test('handles timeout gracefully', () async {
        final client = MockClient((request) async {
          await Future<void>.delayed(const Duration(seconds: 15));
          return http.Response('', 200);
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('https://api.example.com');

        expect(result.isReachable, isFalse);
        expect(result.error, contains('timed out'));
      });

      test('handles network error gracefully', () async {
        final client = MockClient((request) async {
          throw Exception('Network error');
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('https://api.example.com');

        expect(result.isReachable, isFalse);
        expect(result.error, contains('Network error'));
      });
    });

    group('common providers', () {
      test('probes Ollama-style endpoint (no auth)', () async {
        final client = MockClient((request) async {
          if (request.url.path == '/v1/models') {
            return http.Response(
              jsonEncode({
                'data': [
                  {'id': 'llama2'},
                  {'id': 'codellama'},
                ],
              }),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        final probe = CompletionsProbe(httpClient: client);
        final result = await probe.probe('http://localhost:11434');

        expect(result.isReachable, isTrue);
        expect(result.requiresApiKey, isFalse);
        expect(result.availableModels, contains('llama2'));
      });

      test('probes OpenAI-style endpoint (with auth)', () async {
        final client = MockClient((request) async {
          if (request.headers['Authorization'] != 'Bearer sk-test') {
            return http.Response('Unauthorized', 401);
          }
          if (request.url.path == '/v1/models') {
            return http.Response(
              jsonEncode({
                'data': [
                  {'id': 'gpt-4-turbo'},
                  {'id': 'gpt-4'},
                  {'id': 'gpt-3.5-turbo'},
                ],
              }),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        final probe = CompletionsProbe(httpClient: client);

        // Without API key - should detect needs auth
        final unauthResult = await probe.probe('https://api.openai.com');
        expect(unauthResult.requiresApiKey, isTrue);
        expect(unauthResult.availableModels, isEmpty);

        // With API key - should get models
        final authResult = await probe.probe(
          'https://api.openai.com',
          apiKey: 'sk-test',
        );
        expect(authResult.availableModels, contains('gpt-4-turbo'));
      });
    });
  });
}
