import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:soliplex/core/network/http_transport.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';

/// Tests for HttpTransport as a pure adapter over NetworkTransportLayer.
void main() {
  group('HttpTransport', () {
    group('constructor', () {
      test('requires NetworkTransportLayer', () {
        final mockClient = MockClient((request) async {
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        expect(transport.baseUrl, equals('http://localhost:8080'));
        expect(transport.transportLayer, same(layer));

        layer.close();
      });

      test('fromTransportLayer factory creates same instance', () {
        final mockClient = MockClient((request) async {
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport.fromTransportLayer(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        expect(transport.baseUrl, equals('http://localhost:8080'));
        expect(transport.transportLayer, same(layer));

        layer.close();
      });

      test('exposes defaultHeaders from transport layer', () {
        final mockClient = MockClient((request) async {
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
          defaultHeaders: {'Authorization': 'Bearer token'},
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        expect(
          transport.defaultHeaders,
          containsPair('Authorization', 'Bearer token'),
        );

        layer.close();
      });
    });

    group('post', () {
      test('encodes body as JSON and decodes response', () async {
        final mockClient = MockClient((request) async {
          expect(request.body, equals('{"input":"data"}'));
          expect(request.headers['content-type'], contains('application/json'));
          return http.Response('{"result":"ok"}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');
        final result = await transport.post(uri, {'input': 'data'});

        expect(result, equals({'result': 'ok'}));

        layer.close();
      });

      test('returns empty map for empty response', () async {
        final mockClient = MockClient((request) async {
          return http.Response('', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');
        final result = await transport.post(uri, {});

        expect(result, equals({}));

        layer.close();
      });

      test('throws HttpTransportException on 4xx error', () async {
        final mockClient = MockClient((request) async {
          return http.Response('{"error":"not found"}', 404);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');

        expect(
          () => transport.post(uri, {}),
          throwsA(
            isA<HttpTransportException>().having(
              (e) => e.statusCode,
              'statusCode',
              404,
            ),
          ),
        );

        layer.close();
      });

      test('throws HttpTransportException on 5xx error', () async {
        final mockClient = MockClient((request) async {
          return http.Response('{"error":"server error"}', 500);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        final uri = Uri.parse('http://localhost:8080/api/test');

        expect(
          () => transport.post(uri, {}),
          throwsA(
            isA<HttpTransportException>().having(
              (e) => e.statusCode,
              'statusCode',
              500,
            ),
          ),
        );

        layer.close();
      });
    });

    group('cancelRun', () {
      test('sends cancel request to server', () async {
        var cancelCalled = false;

        final mockClient = MockClient((request) async {
          if (request.url.path.contains('cancel')) {
            cancelCalled = true;
            return http.Response('{}', 200);
          }
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        await transport.cancelRun(
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        expect(cancelCalled, isTrue);

        layer.close();
      });

      test('handles cancel failure gracefully (non-critical)', () async {
        final mockClient = MockClient((request) async {
          if (request.url.path.contains('cancel')) {
            return http.Response('{"error":"failed"}', 500);
          }
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        // Should not throw - cancel is non-critical
        await transport.cancelRun(
          roomId: 'room-1',
          threadId: 'thread-1',
          runId: 'run-1',
        );

        layer.close();
      });
    });

    group('close', () {
      test('is a no-op (transport layer managed externally)', () async {
        final mockClient = MockClient((request) async {
          return http.Response('{}', 200);
        });

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          httpClient: mockClient,
        );

        final transport = HttpTransport(
          baseUrl: 'http://localhost:8080',
          transportLayer: layer,
        );

        // Should not throw
        await transport.close();

        // Transport layer should still work after HttpTransport.close()
        final uri = Uri.parse('http://localhost:8080/api/test');
        final response = await layer.post(uri, '{}');
        expect(response.statusCode, equals(200));

        layer.close();
      });
    });

    group('HttpTransportException', () {
      test('contains message and status code', () {
        final exception = HttpTransportException('test error', 404);

        expect(exception.message, equals('test error'));
        expect(exception.statusCode, equals(404));
        expect(exception.toString(), contains('test error'));
        expect(exception.toString(), contains('404'));
      });
    });
  });
}
