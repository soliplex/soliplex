import 'dart:async';

import 'package:agui_dash_2/core/network/network_inspector.dart';
import 'package:agui_dash_2/core/network/network_transport_layer.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  group('NetworkTransportLayer', () {
    late NetworkInspector inspector;

    setUp(() {
      inspector = NetworkInspector(maxEntries: 100);
    });

    tearDown(() {
      inspector.dispose();
    });

    group('HTTP POST', () {
      test('records request and response in inspector', () async {
        final mockClient = MockClient((request) async {
          return http.Response('{"result": "ok"}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
          inspector: inspector,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');
        final response = await layer.post(uri, '{"input": "data"}');

        expect(response.statusCode, equals(200));
        expect(response.body, equals('{"result": "ok"}'));

        // Check inspector recorded the request
        expect(inspector.entryCount, equals(1));
        final entry = inspector.entries.first;
        expect(entry.method, equals('POST'));
        expect(entry.statusCode, equals(200));
        expect(entry.isComplete, isTrue);

        layer.close();
      });

      test('records error in inspector on failure', () async {
        final mockClient = MockClient((request) async {
          throw Exception('Network error');
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
          inspector: inspector,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');

        await expectLater(
          () => layer.post(uri, '{}'),
          throwsException,
        );

        // Check inspector recorded the error
        expect(inspector.entryCount, equals(1));
        final entry = inspector.entries.first;
        expect(entry.isError, isTrue);
        expect(entry.error, contains('Network error'));

        layer.close();
      });

      test('retries on 401 with header refresh', () async {
        var callCount = 0;
        final mockClient = MockClient((request) async {
          callCount++;
          if (callCount == 1) {
            return http.Response('Unauthorized', 401);
          }
          return http.Response('{"result": "ok"}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
          defaultHeaders: {'Authorization': 'Bearer old-token'},
          headerRefresher: () async => {'Authorization': 'Bearer new-token'},
          inspector: inspector,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');
        final response = await layer.post(uri, '{}');

        expect(response.statusCode, equals(200));
        expect(callCount, equals(2)); // Initial + retry

        layer.close();
      });
    });

    group('dispose', () {
      test('prevents further requests after close', () async {
        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
        );

        layer.close();

        final uri = Uri.parse('http://localhost:8080/api/test');
        await expectLater(
          () => layer.post(uri, '{}'),
          throwsStateError,
        );
      });

      test('isDisposed returns true after close', () {
        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
        );

        expect(layer.isDisposed, isFalse);
        layer.close();
        expect(layer.isDisposed, isTrue);
      });

      test('close is idempotent', () {
        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
        );

        layer.close();
        layer.close(); // Should not throw
        expect(layer.isDisposed, isTrue);
      });
    });

    group('headers', () {
      test('uses default headers in requests', () async {
        String? authHeader;
        final mockClient = MockClient((request) async {
          authHeader = request.headers['Authorization'];
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
          defaultHeaders: {'Authorization': 'Bearer test-token'},
        );

        final uri = Uri.parse('http://localhost:8080/api/test');
        await layer.post(uri, '{}');

        expect(authHeader, equals('Bearer test-token'));

        layer.close();
      });

      test('updateHeaders changes headers for future requests', () async {
        String? authHeader;
        final mockClient = MockClient((request) async {
          authHeader = request.headers['Authorization'];
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
          defaultHeaders: {'Authorization': 'Bearer old-token'},
        );

        layer.updateHeaders({'Authorization': 'Bearer new-token'});

        final uri = Uri.parse('http://localhost:8080/api/test');
        await layer.post(uri, '{}');

        expect(authHeader, equals('Bearer new-token'));

        layer.close();
      });
    });

    group('agUiClient', () {
      test('exposes AgUiClient for SSE streaming', () {
        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
        );

        expect(layer.agUiClient, isNotNull);

        layer.close();
      });
    });
  });
}
