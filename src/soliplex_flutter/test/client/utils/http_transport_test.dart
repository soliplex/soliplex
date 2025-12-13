import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:soliplex_flutter/client/utils/http_transport.dart';
import 'package:test/test.dart';

void main() {
  group('HttpTransport', () {
    test('creates with defaults', () {
      final transport = HttpTransport(baseUrl: 'https://example.com');

      expect(transport.baseUrl, equals('https://example.com'));
      expect(transport.timeout, equals(const Duration(seconds: 30)));
      expect(transport.defaultHeaders, isNull);
    });

    test('creates with custom parameters', () {
      final transport = HttpTransport(
        baseUrl: 'https://example.com',
        defaultHeaders: {'Authorization': 'Bearer token'},
        timeout: const Duration(seconds: 60),
      );

      expect(transport.baseUrl, equals('https://example.com'));
      expect(transport.timeout, equals(const Duration(seconds: 60)));
      expect(transport.defaultHeaders, equals({'Authorization': 'Bearer token'}));
    });

    group('GET', () {
      test('makes GET request', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('GET'));
          expect(request.url.toString(), equals('https://example.com/api/test'));
          return http.Response('{"success": true}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );

        final response = await transport.get(
          Uri.parse('https://example.com/api/test'),
        );

        expect(response.statusCode, equals(200));
        expect(response.body, equals('{"success": true}'));
      });

      test('GET includes default headers', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['Authorization'], equals('Bearer token'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          defaultHeaders: {'Authorization': 'Bearer token'},
          client: mockClient,
        );

        await transport.get(Uri.parse('https://example.com/api/test'));
      });

      test('GET merges custom headers', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['Authorization'], equals('Bearer token'));
          expect(request.headers['X-Custom'], equals('value'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          defaultHeaders: {'Authorization': 'Bearer token'},
          client: mockClient,
        );

        await transport.get(
          Uri.parse('https://example.com/api/test'),
          headers: {'X-Custom': 'value'},
        );
      });
    });

    group('POST', () {
      test('makes POST request with JSON body', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('POST'));
          expect(request.headers['Content-Type'], equals('application/json'));
          expect(request.body, equals('{"name":"test"}'));
          return http.Response('{"id": 1}', 201);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );

        final response = await transport.post(
          Uri.parse('https://example.com/api/test'),
          body: {'name': 'test'},
        );

        expect(response.statusCode, equals(201));
      });

      test('POST with null body', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('POST'));
          expect(request.body, equals(''));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );

        await transport.post(Uri.parse('https://example.com/api/test'));
      });

      test('POST includes default headers', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['Authorization'], equals('Bearer token'));
          expect(request.headers['Content-Type'], equals('application/json'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          defaultHeaders: {'Authorization': 'Bearer token'},
          client: mockClient,
        );

        await transport.post(
          Uri.parse('https://example.com/api/test'),
          body: {},
        );
      });
    });

    group('DELETE', () {
      test('makes DELETE request', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('DELETE'));
          return http.Response('', 204);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );

        final response = await transport.delete(
          Uri.parse('https://example.com/api/test/1'),
        );

        expect(response.statusCode, equals(204));
      });

      test('DELETE includes default headers', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['Authorization'], equals('Bearer token'));
          return http.Response('', 204);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          defaultHeaders: {'Authorization': 'Bearer token'},
          client: mockClient,
        );

        await transport.delete(Uri.parse('https://example.com/api/test/1'));
      });
    });

    test('close closes the client', () {
      // Just verify it doesn't throw
      final transport = HttpTransport(baseUrl: 'https://example.com');
      transport.close();
    });
  });

  group('HttpResponse', () {
    test('creates with required fields', () {
      const response = HttpResponse(
        statusCode: 200,
        body: '{"data": "value"}',
        headers: {'content-type': 'application/json'},
      );

      expect(response.statusCode, equals(200));
      expect(response.body, equals('{"data": "value"}'));
      expect(response.headers, equals({'content-type': 'application/json'}));
    });

    test('isSuccess returns true for 2xx', () {
      const response200 = HttpResponse(
        statusCode: 200,
        body: '',
        headers: {},
      );
      const response201 = HttpResponse(
        statusCode: 201,
        body: '',
        headers: {},
      );
      const response299 = HttpResponse(
        statusCode: 299,
        body: '',
        headers: {},
      );

      expect(response200.isSuccess, isTrue);
      expect(response201.isSuccess, isTrue);
      expect(response299.isSuccess, isTrue);
    });

    test('isSuccess returns false for non-2xx', () {
      const response400 = HttpResponse(
        statusCode: 400,
        body: '',
        headers: {},
      );
      const response500 = HttpResponse(
        statusCode: 500,
        body: '',
        headers: {},
      );
      const response199 = HttpResponse(
        statusCode: 199,
        body: '',
        headers: {},
      );

      expect(response400.isSuccess, isFalse);
      expect(response500.isSuccess, isFalse);
      expect(response199.isSuccess, isFalse);
    });

    test('json parses body as JSON', () {
      const response = HttpResponse(
        statusCode: 200,
        body: '{"key": "value"}',
        headers: {},
      );

      expect(response.json, equals({'key': 'value'}));
    });

    test('jsonMap returns Map', () {
      const response = HttpResponse(
        statusCode: 200,
        body: '{"key": "value"}',
        headers: {},
      );

      final map = response.jsonMap;
      expect(map, isA<Map<String, dynamic>>());
      expect(map['key'], equals('value'));
    });

    test('jsonList returns List', () {
      const response = HttpResponse(
        statusCode: 200,
        body: '[1, 2, 3]',
        headers: {},
      );

      final list = response.jsonList;
      expect(list, isA<List<dynamic>>());
      expect(list, equals([1, 2, 3]));
    });

    test('toString includes status code', () {
      const response = HttpResponse(
        statusCode: 404,
        body: '',
        headers: {},
      );

      expect(response.toString(), contains('404'));
    });
  });

  group('HttpException', () {
    test('creates with required fields', () {
      const exception = HttpException(
        statusCode: 400,
        body: 'Bad Request',
      );

      expect(exception.statusCode, equals(400));
      expect(exception.body, equals('Bad Request'));
      expect(exception.message, isNull);
    });

    test('creates with message', () {
      const exception = HttpException(
        statusCode: 401,
        body: 'Unauthorized',
        message: 'Authentication required',
      );

      expect(exception.statusCode, equals(401));
      expect(exception.body, equals('Unauthorized'));
      expect(exception.message, equals('Authentication required'));
    });

    test('toString with message shows message', () {
      const exception = HttpException(
        statusCode: 401,
        body: 'Unauthorized body',
        message: 'Custom message',
      );

      expect(exception.toString(), contains('401'));
      expect(exception.toString(), contains('Custom message'));
    });

    test('toString without message shows body', () {
      const exception = HttpException(
        statusCode: 400,
        body: 'Bad Request body',
      );

      expect(exception.toString(), contains('400'));
      expect(exception.toString(), contains('Bad Request body'));
    });
  });
}
