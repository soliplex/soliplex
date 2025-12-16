import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockHttpClientAdapter extends Mock implements HttpClientAdapter {}

void main() {
  late MockHttpClientAdapter mockAdapter;
  late HttpTransport transport;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockAdapter = MockHttpClientAdapter();
    transport = HttpTransport(adapter: mockAdapter);

    // Setup default close behavior
    when(() => mockAdapter.close()).thenReturn(null);
  });

  tearDown(() {
    transport.close();
    reset(mockAdapter);
  });

  AdapterResponse jsonResponse(
    int statusCode, {
    Object? body,
    Map<String, String>? headers,
  }) {
    final json = body != null ? jsonEncode(body) : '';
    return AdapterResponse(
      statusCode: statusCode,
      bodyBytes: Uint8List.fromList(utf8.encode(json)),
      headers: {
        'content-type': 'application/json',
        ...?headers,
      },
    );
  }

  AdapterResponse textResponse(int statusCode, String body) {
    return AdapterResponse(
      statusCode: statusCode,
      bodyBytes: Uint8List.fromList(utf8.encode(body)),
      headers: const {'content-type': 'text/plain'},
    );
  }

  AdapterResponse emptyResponse(int statusCode) {
    return AdapterResponse(
      statusCode: statusCode,
      bodyBytes: Uint8List(0),
    );
  }

  group('HttpTransport', () {
    group('constructor', () {
      test('uses default timeout of 30 seconds', () {
        expect(transport.defaultTimeout, equals(const Duration(seconds: 30)));
      });

      test('accepts custom default timeout', () {
        final customTransport = HttpTransport(
          adapter: mockAdapter,
          defaultTimeout: const Duration(seconds: 60),
        );
        expect(
          customTransport.defaultTimeout,
          equals(const Duration(seconds: 60)),
        );
      });
    });

    group('request - successful responses', () {
      test('returns parsed JSON for 200 response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(200, body: {'id': 1, 'name': 'test'}),
        );

        final result = await transport.request<Map<String, dynamic>>(
          'GET',
          Uri.parse('https://api.example.com/data'),
        );

        expect(result['id'], equals(1));
        expect(result['name'], equals('test'));
      });

      test('uses fromJson converter when provided', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async =>
              jsonResponse(200, body: {'id': '1', 'name': 'Test Room'}),
        );

        final result = await transport.request<Room>(
          'GET',
          Uri.parse('https://api.example.com/rooms/1'),
          fromJson: Room.fromJson,
        );

        expect(result.name, equals('Test Room'));
        expect(result.id, equals('1'));
      });

      test('handles 201 Created response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(201, body: {'id': 'new-id'}));

        final result = await transport.request<Map<String, dynamic>>(
          'POST',
          Uri.parse('https://api.example.com/items'),
          body: {'name': 'New Item'},
        );

        expect(result['id'], equals('new-id'));
      });

      test('handles 204 No Content response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => emptyResponse(204));

        final result = await transport.request<Map<String, dynamic>?>(
          'DELETE',
          Uri.parse('https://api.example.com/items/1'),
        );

        expect(result, isNull);
      });

      test('returns raw string for non-JSON response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => textResponse(200, 'Hello, World!'));

        final result = await transport.request<String>(
          'GET',
          Uri.parse('https://api.example.com/text'),
        );

        expect(result, equals('Hello, World!'));
      });

      test('detects JSON by content starting with {', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List.fromList(utf8.encode('{"key": "value"}')),
          ),
        );

        final result = await transport.request<Map<String, dynamic>>(
          'GET',
          Uri.parse('https://api.example.com/data'),
        );

        expect(result['key'], equals('value'));
      });

      test('detects JSON by content starting with [', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List.fromList(utf8.encode('[1, 2, 3]')),
          ),
        );

        final result = await transport.request<List<dynamic>>(
          'GET',
          Uri.parse('https://api.example.com/items'),
        );

        expect(result, equals([1, 2, 3]));
      });
    });

    group('request - HTTP methods', () {
      test('forwards GET request', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'GET',
          Uri.parse('https://api.example.com'),
        );

        verify(
          () => mockAdapter.request(
            'GET',
            Uri.parse('https://api.example.com'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('forwards POST request with JSON body', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(201, body: {}));

        await transport.request<void>(
          'POST',
          Uri.parse('https://api.example.com/items'),
          body: {'name': 'Test'},
        );

        verify(
          () => mockAdapter.request(
            'POST',
            Uri.parse('https://api.example.com/items'),
            headers: {'content-type': 'application/json'},
            body: '{"name":"Test"}',
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('forwards PUT request', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'PUT',
          Uri.parse('https://api.example.com/items/1'),
          body: {'name': 'Updated'},
        );

        verify(
          () => mockAdapter.request(
            'PUT',
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('forwards DELETE request', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => emptyResponse(204));

        await transport.request<void>(
          'DELETE',
          Uri.parse('https://api.example.com/items/1'),
        );

        verify(
          () => mockAdapter.request(
            'DELETE',
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('forwards PATCH request', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'PATCH',
          Uri.parse('https://api.example.com/items/1'),
          body: {'name': 'Patched'},
        );

        verify(
          () => mockAdapter.request(
            'PATCH',
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });
    });

    group('request - headers', () {
      test('passes custom headers to adapter', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'GET',
          Uri.parse('https://api.example.com'),
          headers: {'Authorization': 'Bearer token', 'X-Custom': 'value'},
        );

        verify(
          () => mockAdapter.request(
            any(),
            any(),
            headers: {'Authorization': 'Bearer token', 'X-Custom': 'value'},
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('adds content-type header for JSON body', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'POST',
          Uri.parse('https://api.example.com'),
          body: {'key': 'value'},
        );

        verify(
          () => mockAdapter.request(
            any(),
            any(),
            headers: {'content-type': 'application/json'},
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('does not override existing content-type header', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'POST',
          Uri.parse('https://api.example.com'),
          headers: {'content-type': 'application/x-custom'},
          body: {'key': 'value'},
        );

        verify(
          () => mockAdapter.request(
            any(),
            any(),
            headers: {'content-type': 'application/x-custom'},
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });
    });

    group('request - timeout', () {
      test('uses default timeout when not specified', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'GET',
          Uri.parse('https://api.example.com'),
        );

        verify(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: const Duration(seconds: 30),
          ),
        ).called(1);
      });

      test('uses per-request timeout when specified', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {}));

        await transport.request<void>(
          'GET',
          Uri.parse('https://api.example.com'),
          timeout: const Duration(seconds: 5),
        );

        verify(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: const Duration(seconds: 5),
          ),
        ).called(1);
      });
    });

    group('request - exception mapping', () {
      test('throws AuthException for 401 response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(401, body: {'message': 'Unauthorized'}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<AuthException>()
                .having((e) => e.statusCode, 'statusCode', 401)
                .having((e) => e.message, 'message', 'Unauthorized'),
          ),
        );
      });

      test('throws AuthException for 403 response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(403, body: {'error': 'Forbidden'}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<AuthException>()
                .having((e) => e.statusCode, 'statusCode', 403)
                .having((e) => e.message, 'message', 'Forbidden'),
          ),
        );
      });

      test('throws NotFoundException for 404 response', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async =>
              jsonResponse(404, body: {'detail': 'Resource not found'}),
        );

        await expectLater(
          transport.request<void>(
            'GET',
            Uri.parse('https://api.example.com/items/999'),
          ),
          throwsA(
            isA<NotFoundException>()
                .having((e) => e.resource, 'resource', '/items/999')
                .having((e) => e.message, 'message', 'Resource not found'),
          ),
        );
      });

      test('throws ApiException for 400 Bad Request', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(400, body: {'message': 'Invalid input'}),
        );

        await expectLater(
          transport.request<void>('POST', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>()
                .having((e) => e.statusCode, 'statusCode', 400)
                .having((e) => e.message, 'message', 'Invalid input'),
          ),
        );
      });

      test('throws ApiException for 500 Internal Server Error', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(500, body: {'message': 'Server error'}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>()
                .having((e) => e.statusCode, 'statusCode', 500)
                .having((e) => e.message, 'message', 'Server error'),
          ),
        );
      });

      test('throws ApiException for 502 Bad Gateway', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => textResponse(502, 'Bad Gateway'));

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>().having((e) => e.statusCode, 'statusCode', 502),
          ),
        );
      });

      test('uses HTTP status as message when no JSON error message', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => emptyResponse(500));

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>().having((e) => e.message, 'message', 'HTTP 500'),
          ),
        );
      });

      test('passes through NetworkException from adapter', () async {
        const networkError = NetworkException(
          message: 'Connection refused',
        );

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(networkError);

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(equals(networkError)),
        );
      });

      test('passes through timeout NetworkException from adapter', () async {
        const timeoutError = NetworkException(
          message: 'Request timed out',
          isTimeout: true,
        );

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(timeoutError);

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<NetworkException>()
                .having((e) => e.isTimeout, 'isTimeout', true),
          ),
        );
      });
    });

    group('request - CancelToken', () {
      test('throws CancelledException when token is already cancelled',
          () async {
        final token = CancelToken()..cancel('Pre-cancelled');

        await expectLater(
          transport.request<void>(
            'GET',
            Uri.parse('https://api.example.com'),
            cancelToken: token,
          ),
          throwsA(
            isA<CancelledException>()
                .having((e) => e.reason, 'reason', 'Pre-cancelled'),
          ),
        );

        // Adapter should not be called
        verifyNever(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        );
      });

      test('throws CancelledException when token cancelled during request',
          () async {
        final token = CancelToken();
        final completer = Completer<AdapterResponse>();

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async {
          // Cancel after request starts
          token.cancel('Cancelled mid-flight');
          return completer.future;
        });

        // Complete the request (but token is already cancelled)
        completer.complete(jsonResponse(200, body: {}));

        await expectLater(
          transport.request<void>(
            'GET',
            Uri.parse('https://api.example.com'),
            cancelToken: token,
          ),
          throwsA(
            isA<CancelledException>()
                .having((e) => e.reason, 'reason', 'Cancelled mid-flight'),
          ),
        );
      });

      test('succeeds when token is not cancelled', () async {
        final token = CancelToken();

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => jsonResponse(200, body: {'result': 'ok'}));

        final result = await transport.request<Map<String, dynamic>>(
          'GET',
          Uri.parse('https://api.example.com'),
          cancelToken: token,
        );

        expect(result['result'], equals('ok'));
      });
    });

    group('requestStream', () {
      test('returns byte stream from adapter', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = transport.requestStream(
          'GET',
          Uri.parse('https://api.example.com/stream'),
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
        );

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

      test('forwards headers and JSON body to adapter', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = transport.requestStream(
          'POST',
          Uri.parse('https://api.example.com/stream'),
          headers: {'Authorization': 'Bearer token'},
          body: {'prompt': 'Hello'},
        );

        // Start listening to trigger the request
        final subscription = stream.listen((_) {});

        await Future<void>.delayed(Duration.zero);

        verify(
          () => mockAdapter.requestStream(
            'POST',
            Uri.parse('https://api.example.com/stream'),
            headers: {
              'Authorization': 'Bearer token',
              'content-type': 'application/json',
            },
            body: '{"prompt":"Hello"}',
          ),
        ).called(1);

        await subscription.cancel();
        await controller.close();
      });

      test('throws CancelledException when token already cancelled', () {
        final token = CancelToken()..cancel('Pre-cancelled');

        expect(
          () => transport.requestStream(
            'GET',
            Uri.parse('https://api.example.com/stream'),
            cancelToken: token,
          ),
          throwsA(isA<CancelledException>()),
        );
      });

      test('cancels stream when token is cancelled', () async {
        final token = CancelToken();
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = transport.requestStream(
          'GET',
          Uri.parse('https://api.example.com/stream'),
          cancelToken: token,
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

        // Send some data
        controller.add([1, 2, 3]);
        await Future<void>.delayed(Duration.zero);

        // Cancel the token
        token.cancel('User cancelled');

        await completer.future;

        expect(errors, hasLength(1));
        expect(errors.first, isA<CancelledException>());
        expect(
          (errors.first as CancelledException).reason,
          equals('User cancelled'),
        );

        await controller.close();
      });

      test('stream completes normally when not cancelled', () async {
        final token = CancelToken();
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = transport.requestStream(
          'GET',
          Uri.parse('https://api.example.com/stream'),
          cancelToken: token,
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
        );

        controller
          ..add([1, 2, 3])
          ..add([4, 5]);
        await controller.close();

        await completer.future;

        expect(
          chunks,
          equals([
            [1, 2, 3],
            [4, 5],
          ]),
        );
      });

      test('works without cancel token', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = transport.requestStream(
          'GET',
          Uri.parse('https://api.example.com/stream'),
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
        );

        controller.add([1, 2, 3]);
        await controller.close();

        await completer.future;

        expect(chunks, hasLength(1));
      });

      test('supports pause and resume with cancel token', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final token = CancelToken();
        final stream = transport.requestStream(
          'GET',
          Uri.parse('https://api.example.com/stream'),
          cancelToken: token,
        );

        final chunks = <List<int>>[];
        final subscription = stream.listen(chunks.add);

        // Add first chunk
        controller.add([1, 2, 3]);
        await Future<void>.delayed(Duration.zero);
        expect(chunks, hasLength(1));

        // Pause the subscription
        subscription.pause();
        await Future<void>.delayed(Duration.zero);

        // Add chunk while paused (will be buffered)
        controller.add([4, 5, 6]);
        await Future<void>.delayed(Duration.zero);

        // Resume the subscription
        subscription.resume();
        await Future<void>.delayed(Duration.zero);

        // Buffered chunk should now be received
        expect(chunks, hasLength(2));

        await subscription.cancel();
        await controller.close();
      });
    });

    group('close', () {
      test('delegates to adapter', () {
        transport.close();

        verify(() => mockAdapter.close()).called(1);
      });
    });

    group('error message extraction', () {
      test('extracts message field from JSON error', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async =>
              jsonResponse(400, body: {'message': 'Custom error message'}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>()
                .having((e) => e.message, 'message', 'Custom error message'),
          ),
        );
      });

      test('extracts error field from JSON error', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(400, body: {'error': 'Error field value'}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>()
                .having((e) => e.message, 'message', 'Error field value'),
          ),
        );
      });

      test('extracts detail field from JSON error', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async =>
              jsonResponse(400, body: {'detail': 'Detail field value'}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>()
                .having((e) => e.message, 'message', 'Detail field value'),
          ),
        );
      });

      test('prefers message over error over detail', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => jsonResponse(
            400,
            body: {
              'message': 'Message field',
              'error': 'Error field',
              'detail': 'Detail field',
            },
          ),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>()
                .having((e) => e.message, 'message', 'Message field'),
          ),
        );
      });

      test('includes body in ApiException', () async {
        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async =>
              jsonResponse(400, body: {'message': 'Error', 'code': 123}),
        );

        await expectLater(
          transport.request<void>('GET', Uri.parse('https://api.example.com')),
          throwsA(
            isA<ApiException>().having(
              (e) => e.body,
              'body',
              contains('"code":123'),
            ),
          ),
        );
      });
    });
  });
}
