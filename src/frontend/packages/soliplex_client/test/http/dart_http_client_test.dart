import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockHttpClient extends Mock implements http.Client {}

class FakeBaseRequest extends Fake implements http.BaseRequest {}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeBaseRequest());
  });

  group('DartHttpClient', () {
    late MockHttpClient mockClient;
    late DartHttpClient client;

    setUp(() {
      mockClient = MockHttpClient();
      client = DartHttpClient(client: mockClient);
    });

    tearDown(() {
      client.close();
    });

    group('request', () {
      test('performs GET request and returns response', () async {
        final responseBody = utf8.encode('{"data": "test"}');
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: responseBody,
          headers: {'content-type': 'application/json'},
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final response = await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(response.statusCode, equals(200));
        expect(response.body, equals('{"data": "test"}'));
        expect(response.contentType, equals('application/json'));
      });

      test('performs POST request with JSON body', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 201,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
          body: {'key': 'value'},
        );

        expect(capturedRequest?.method, equals('POST'));
        expect(capturedRequest?.body, equals('{"key":"value"}'));
        expect(
          capturedRequest?.headers['content-type'],
          contains('application/json'),
        );
      });

      test('performs POST request with string body', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
          body: 'plain text',
        );

        expect(capturedRequest?.body, equals('plain text'));
        expect(
          capturedRequest?.headers['content-type'],
          contains('text/plain'),
        );
      });

      test('performs POST request with bytes body', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
          body: [1, 2, 3, 4],
        );

        expect(capturedRequest?.bodyBytes, equals([1, 2, 3, 4]));
        expect(
          capturedRequest?.headers['content-type'],
          contains('application/octet-stream'),
        );
      });

      test('includes custom headers in request', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
          headers: {'Authorization': 'Bearer token123'},
        );

        expect(
          capturedRequest?.headers['Authorization'],
          equals('Bearer token123'),
        );
      });

      test('does not override user-provided content-type', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
          headers: {'content-type': 'application/xml'},
          body: '<xml>data</xml>',
        );

        // User's content-type is preserved (http package may append charset)
        expect(
          capturedRequest?.headers['content-type'],
          startsWith('application/xml'),
        );
      });

      test('throws NetworkException with isTimeout on request timeout',
          () async {
        when(() => mockClient.send(any())).thenAnswer(
          (_) => Future.delayed(
            const Duration(seconds: 5),
            () => _createStreamedResponse(statusCode: 200, body: []),
          ),
        );

        client = DartHttpClient(
          client: mockClient,
          defaultTimeout: const Duration(milliseconds: 50),
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com/api')),
          throwsA(
            isA<NetworkException>()
                .having((e) => e.isTimeout, 'isTimeout', isTrue),
          ),
        );
      });

      test('throws NetworkException on SocketException', () async {
        when(() => mockClient.send(any())).thenThrow(
          const SocketException('Connection refused'),
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com/api')),
          throwsA(
            isA<NetworkException>().having(
              (e) => e.message,
              'message',
              contains('Connection refused'),
            ),
          ),
        );
      });

      test('throws NetworkException on ClientException', () async {
        when(() => mockClient.send(any())).thenThrow(
          http.ClientException('Network error'),
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com/api')),
          throwsA(isA<NetworkException>()),
        );
      });

      test('throws NetworkException on HttpException', () async {
        when(() => mockClient.send(any())).thenThrow(
          const HttpException('Invalid response'),
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com/api')),
          throwsA(
            isA<NetworkException>().having(
              (e) => e.message,
              'message',
              contains('HTTP error'),
            ),
          ),
        );
      });

      test('throws ArgumentError for unsupported body type', () async {
        expect(
          () => client.request(
            'POST',
            Uri.parse('https://example.com/api'),
            body: DateTime.now(),
          ),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('uses custom timeout when provided', () async {
        when(() => mockClient.send(any())).thenAnswer(
          (_) => Future.delayed(
            const Duration(milliseconds: 200),
            () => _createStreamedResponse(statusCode: 200, body: []),
          ),
        );

        await expectLater(
          client.request(
            'GET',
            Uri.parse('https://example.com/api'),
            timeout: const Duration(milliseconds: 50),
          ),
          throwsA(isA<NetworkException>()),
        );
      });

      test('normalizes response headers to lowercase', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
          headers: {'Content-Type': 'application/json', 'X-Custom': 'value'},
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final response = await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(response.headers['content-type'], equals('application/json'));
        expect(response.headers['x-custom'], equals('value'));
      });

      test('uppercases HTTP method', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'get',
          Uri.parse('https://example.com/api'),
        );

        expect(capturedRequest?.method, equals('GET'));
      });

      test('includes reasonPhrase in response', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 201,
          body: [],
          reasonPhrase: 'Created',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final response = await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
        );

        expect(response.reasonPhrase, equals('Created'));
      });

      test('preserves original error in NetworkException', () async {
        const originalError = SocketException('Connection refused');
        when(() => mockClient.send(any())).thenThrow(originalError);

        try {
          await client.request('GET', Uri.parse('https://example.com/api'));
          fail('Expected NetworkException');
        } on NetworkException catch (e) {
          expect(e.originalError, equals(originalError));
          expect(e.stackTrace, isNotNull);
        }
      });

      test('throws NetworkException on response body timeout', () async {
        // Create a stream that delays forever to simulate body timeout
        final bodyController = StreamController<List<int>>();
        final streamedResponse = http.StreamedResponse(
          bodyController.stream,
          200,
          reasonPhrase: 'OK',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        client = DartHttpClient(
          client: mockClient,
          defaultTimeout: const Duration(milliseconds: 50),
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com/api')),
          throwsA(
            isA<NetworkException>()
                .having((e) => e.isTimeout, 'isTimeout', isTrue)
                .having(
                  (e) => e.message,
                  'message',
                  contains('Response body timed out'),
                ),
          ),
        );

        await bodyController.close();
      });

      test('handles TimeoutException with null message', () async {
        when(() => mockClient.send(any())).thenThrow(
          TimeoutException(null),
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com/api')),
          throwsA(
            isA<NetworkException>()
                .having((e) => e.isTimeout, 'isTimeout', isTrue)
                .having(
                  (e) => e.message,
                  'message',
                  equals('Request timed out'),
                ),
          ),
        );
      });

      test('request with no body sends empty request', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(capturedRequest?.bodyBytes, isEmpty);
      });

      test('request with no headers sends request without custom headers',
          () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        // Should not have custom headers (only default ones from http package)
        expect(capturedRequest?.headers.containsKey('Authorization'), isFalse);
      });
    });

    group('requestStream', () {
      test('streams response body chunks', () async {
        final controller = StreamController<List<int>>();
        final streamedResponse = http.StreamedResponse(
          controller.stream,
          200,
          reasonPhrase: 'OK',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
          onError: completer.completeError,
        );

        // Give time for the listener to be set up
        await Future<void>.delayed(const Duration(milliseconds: 10));

        controller
          ..add([1, 2, 3])
          ..add([4, 5, 6]);
        await controller.close();

        await completer.future;

        expect(
          chunks,
          equals([
            [1, 2, 3],
            [4, 5, 6],
          ]),
        );
      });

      test('emits NetworkException on HTTP error status', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 500,
          body: utf8.encode('Internal Server Error'),
          reasonPhrase: 'Internal Server Error',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        await expectLater(
          stream,
          emitsError(isA<NetworkException>()),
        );
      });

      test('emits NetworkException on connection error', () async {
        when(() => mockClient.send(any())).thenThrow(
          const SocketException('Connection refused'),
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        await expectLater(
          stream,
          emitsError(isA<NetworkException>()),
        );
      });

      test('emits NetworkException on client exception', () async {
        when(() => mockClient.send(any())).thenThrow(
          http.ClientException('Client error'),
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        await expectLater(
          stream,
          emitsError(isA<NetworkException>()),
        );
      });

      test('can be cancelled via subscription', () async {
        final controller = StreamController<List<int>>();
        final streamedResponse = http.StreamedResponse(
          controller.stream,
          200,
          reasonPhrase: 'OK',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        final chunks = <List<int>>[];
        final subscription = stream.listen(chunks.add);

        await Future<void>.delayed(const Duration(milliseconds: 10));

        controller.add([1, 2, 3]);
        await Future<void>.delayed(const Duration(milliseconds: 10));

        await subscription.cancel();

        // Should not add more chunks after cancel
        controller.add([4, 5, 6]);
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(
          chunks,
          equals([
            [1, 2, 3],
          ]),
        );

        await controller.close();
      });

      test('converts SocketException during streaming to NetworkException',
          () async {
        final controller = StreamController<List<int>>();
        final streamedResponse = http.StreamedResponse(
          controller.stream,
          200,
          reasonPhrase: 'OK',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        final errors = <Object>[];
        final completer = Completer<void>();

        stream.listen(
          (_) {},
          onError: (Object e) {
            errors.add(e);
            completer.complete();
          },
          onDone: () {
            if (!completer.isCompleted) completer.complete();
          },
        );

        await Future<void>.delayed(const Duration(milliseconds: 10));

        // Simulate a SocketException during streaming
        controller.addError(const SocketException('Connection lost'));

        await completer.future;

        expect(errors, hasLength(1));
        expect(errors.first, isA<NetworkException>());
        expect(
          (errors.first as NetworkException).message,
          contains('Connection lost'),
        );

        await controller.close();
      });

      test('passes through non-SocketException errors during streaming',
          () async {
        final controller = StreamController<List<int>>();
        final streamedResponse = http.StreamedResponse(
          controller.stream,
          200,
          reasonPhrase: 'OK',
        );

        when(() => mockClient.send(any())).thenAnswer(
          (_) async => streamedResponse,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        final errors = <Object>[];
        final completer = Completer<void>();

        stream.listen(
          (_) {},
          onError: (Object e) {
            errors.add(e);
            completer.complete();
          },
          onDone: () {
            if (!completer.isCompleted) completer.complete();
          },
        );

        await Future<void>.delayed(const Duration(milliseconds: 10));

        // Simulate a non-SocketException error during streaming
        controller.addError(Exception('Some other error'));

        await completer.future;

        expect(errors, hasLength(1));
        // Non-SocketException errors should be passed through as-is
        expect(errors.first, isA<Exception>());
        expect(errors.first, isNot(isA<NetworkException>()));

        await controller.close();
      });

      test('handles stream with body parameter', () async {
        final controller = StreamController<List<int>>();
        final streamedResponse = http.StreamedResponse(
          controller.stream,
          200,
          reasonPhrase: 'OK',
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        final stream = client.requestStream(
          'POST',
          Uri.parse('https://example.com/stream'),
          body: {'key': 'value'},
          headers: {'X-Custom': 'header'},
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
        );

        await Future<void>.delayed(const Duration(milliseconds: 10));

        controller.add([1, 2, 3]);
        await controller.close();

        await completer.future;

        expect(capturedRequest?.method, equals('POST'));
        expect(capturedRequest?.body, equals('{"key":"value"}'));
        expect(capturedRequest?.headers['X-Custom'], equals('header'));
        expect(
          chunks,
          equals([
            [1, 2, 3],
          ]),
        );
      });
    });

    group('close', () {
      test('closes underlying client', () {
        client.close();

        verify(() => mockClient.close()).called(1);
      });

      test('multiple close calls only close client once', () {
        client
          ..close()
          ..close()
          ..close();

        verify(() => mockClient.close()).called(1);
      });

      test('throws StateError when request called after close', () {
        client.close();

        expect(
          () => client.request('GET', Uri.parse('https://example.com')),
          throwsStateError,
        );
      });

      test('throws StateError when requestStream called after close', () {
        client.close();

        expect(
          () => client.requestStream('GET', Uri.parse('https://example.com')),
          throwsStateError,
        );
      });
    });

    group('default configuration', () {
      test('creates with default timeout of 30 seconds', () {
        final defaultClient = DartHttpClient();

        expect(
          defaultClient.defaultTimeout,
          equals(const Duration(seconds: 30)),
        );

        defaultClient.close();
      });

      test('creates own http.Client when not provided', () {
        final defaultClient = DartHttpClient();

        expect(defaultClient, isA<SoliplexHttpClient>());

        defaultClient.close();
      });

      test('accepts custom default timeout', () {
        final customClient = DartHttpClient(
          defaultTimeout: const Duration(seconds: 60),
        );

        expect(
          customClient.defaultTimeout,
          equals(const Duration(seconds: 60)),
        );

        customClient.close();
      });
    });

    group('HTTP methods', () {
      test('supports PUT request', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'PUT',
          Uri.parse('https://example.com/api'),
          body: {'update': 'data'},
        );

        expect(capturedRequest?.method, equals('PUT'));
      });

      test('supports DELETE request', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 204,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'DELETE',
          Uri.parse('https://example.com/api/123'),
        );

        expect(capturedRequest?.method, equals('DELETE'));
      });

      test('supports PATCH request', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'PATCH',
          Uri.parse('https://example.com/api/123'),
          body: {'partial': 'update'},
        );

        expect(capturedRequest?.method, equals('PATCH'));
      });

      test('supports HEAD request', () async {
        final streamedResponse = _createStreamedResponse(
          statusCode: 200,
          body: [],
        );

        http.Request? capturedRequest;
        when(() => mockClient.send(any())).thenAnswer((invocation) async {
          capturedRequest = invocation.positionalArguments[0] as http.Request;
          return streamedResponse;
        });

        await client.request(
          'HEAD',
          Uri.parse('https://example.com/api'),
        );

        expect(capturedRequest?.method, equals('HEAD'));
      });
    });
  });
}

/// Helper to create a StreamedResponse for testing.
http.StreamedResponse _createStreamedResponse({
  required int statusCode,
  required List<int> body,
  Map<String, String>? headers,
  String? reasonPhrase,
}) {
  return http.StreamedResponse(
    Stream.value(body),
    statusCode,
    headers: headers ?? {},
    reasonPhrase: reasonPhrase,
  );
}
