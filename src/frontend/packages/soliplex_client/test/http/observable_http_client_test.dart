import 'dart:async';
import 'dart:typed_data';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockSoliplexHttpClient extends Mock implements SoliplexHttpClient {}

class MockHttpObserver extends Mock implements HttpObserver {}

/// Test observer that records all events for verification.
class RecordingObserver implements HttpObserver {
  final events = <HttpEvent>[];

  @override
  void onRequest(HttpRequestEvent event) => events.add(event);

  @override
  void onResponse(HttpResponseEvent event) => events.add(event);

  @override
  void onError(HttpErrorEvent event) => events.add(event);

  @override
  void onStreamStart(HttpStreamStartEvent event) => events.add(event);

  @override
  void onStreamEnd(HttpStreamEndEvent event) => events.add(event);

  List<T> eventsOfType<T extends HttpEvent>() => events.whereType<T>().toList();
}

/// Observer that throws on every callback.
class ThrowingObserver implements HttpObserver {
  @override
  void onRequest(HttpRequestEvent event) =>
      throw Exception('Observer onRequest error');

  @override
  void onResponse(HttpResponseEvent event) =>
      throw Exception('Observer onResponse error');

  @override
  void onError(HttpErrorEvent event) =>
      throw Exception('Observer onError error');

  @override
  void onStreamStart(HttpStreamStartEvent event) =>
      throw Exception('Observer onStreamStart error');

  @override
  void onStreamEnd(HttpStreamEndEvent event) =>
      throw Exception('Observer onStreamEnd error');
}

void main() {
  late MockSoliplexHttpClient mockClient;
  late RecordingObserver recorder;
  late ObservableHttpClient observableClient;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockClient = MockSoliplexHttpClient();
    recorder = RecordingObserver();
    observableClient = ObservableHttpClient(
      client: mockClient,
      observers: [recorder],
    );

    // Setup default close behavior
    when(() => mockClient.close()).thenReturn(null);
  });

  tearDown(() {
    // Reset mock state after each test
    reset(mockClient);
  });

  group('ObservableHttpClient', () {
    group('request lifecycle - success', () {
      test('notifies observer on request start and response', () async {
        final response = HttpResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList(const [1, 2, 3, 4]),
          headers: const {'content-type': 'application/json'},
          reasonPhrase: 'OK',
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => response);

        final result = await observableClient.request(
          'GET',
          Uri.parse('https://example.com/api'),
          headers: {'Authorization': 'Bearer token'},
        );

        expect(result, equals(response));
        expect(recorder.events, hasLength(2));

        final requestEvent = recorder.eventsOfType<HttpRequestEvent>().first;
        expect(requestEvent.method, equals('GET'));
        expect(requestEvent.uri.toString(), equals('https://example.com/api'));
        expect(requestEvent.headers['Authorization'], equals('Bearer token'));

        final responseEvent = recorder.eventsOfType<HttpResponseEvent>().first;
        expect(responseEvent.requestId, equals(requestEvent.requestId));
        expect(responseEvent.statusCode, equals(200));
        expect(responseEvent.bodySize, equals(4));
        expect(responseEvent.reasonPhrase, equals('OK'));
        expect(responseEvent.duration.inMicroseconds, greaterThanOrEqualTo(0));
      });

      test('passes through response unchanged', () async {
        final response = HttpResponse(
          statusCode: 201,
          bodyBytes: Uint8List.fromList(const [65, 66, 67]),
          headers: const {'x-custom': 'value'},
          reasonPhrase: 'Created',
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => response);

        final result = await observableClient.request(
          'POST',
          Uri.parse('https://example.com/create'),
          body: {'data': 'test'},
        );

        expect(result.statusCode, equals(201));
        expect(result.body, equals('ABC'));
        expect(result.headers['x-custom'], equals('value'));
        expect(result.reasonPhrase, equals('Created'));
      });

      test('records empty headers when none provided', () async {
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        await observableClient.request(
          'GET',
          Uri.parse('https://example.com'),
        );

        final requestEvent = recorder.eventsOfType<HttpRequestEvent>().first;
        expect(requestEvent.headers, isEmpty);
      });
    });

    group('request lifecycle - network error', () {
      test('notifies observer on network error and rethrows', () async {
        const exception = NetworkException(
          message: 'Connection refused',
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(exception);

        await expectLater(
          observableClient.request(
            'GET',
            Uri.parse('https://example.com/api'),
          ),
          throwsA(equals(exception)),
        );

        expect(recorder.events, hasLength(2));

        final requestEvent = recorder.eventsOfType<HttpRequestEvent>().first;
        final errorEvent = recorder.eventsOfType<HttpErrorEvent>().first;

        expect(errorEvent.requestId, equals(requestEvent.requestId));
        expect(errorEvent.method, equals('GET'));
        expect(errorEvent.uri.toString(), equals('https://example.com/api'));
        expect(errorEvent.exception, equals(exception));
        expect(errorEvent.duration.inMicroseconds, greaterThanOrEqualTo(0));
      });

      test('notifies observer on timeout error', () async {
        const exception = NetworkException(
          message: 'Request timed out',
          isTimeout: true,
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(exception);

        await expectLater(
          observableClient.request(
            'POST',
            Uri.parse('https://example.com/slow'),
            timeout: const Duration(seconds: 5),
          ),
          throwsA(isA<NetworkException>()),
        );

        final errorEvent = recorder.eventsOfType<HttpErrorEvent>().first;
        expect(errorEvent.exception, isA<NetworkException>());
        expect(
          (errorEvent.exception as NetworkException).isTimeout,
          isTrue,
        );
      });

      test('notifies observer on auth error', () async {
        const exception = AuthException(
          message: 'Unauthorized',
          statusCode: 401,
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(exception);

        await expectLater(
          observableClient.request('GET', Uri.parse('https://example.com')),
          throwsA(equals(exception)),
        );

        final errorEvent = recorder.eventsOfType<HttpErrorEvent>().first;
        expect(errorEvent.exception, isA<AuthException>());
      });
    });

    group('stream lifecycle - success', () {
      test('notifies observer on stream start and end', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = observableClient.requestStream(
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

        // Give time for listener setup
        await Future<void>.delayed(const Duration(milliseconds: 10));

        // Verify stream start event was sent
        expect(recorder.eventsOfType<HttpStreamStartEvent>(), hasLength(1));
        final startEvent = recorder.eventsOfType<HttpStreamStartEvent>().first;
        expect(startEvent.method, equals('GET'));
        expect(
          startEvent.uri.toString(),
          equals('https://example.com/stream'),
        );

        // Send data and close
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

        // Verify stream end event
        expect(recorder.eventsOfType<HttpStreamEndEvent>(), hasLength(1));
        final endEvent = recorder.eventsOfType<HttpStreamEndEvent>().first;
        expect(endEvent.requestId, equals(startEvent.requestId));
        expect(endEvent.bytesReceived, equals(5));
        expect(endEvent.isSuccess, isTrue);
        expect(endEvent.error, isNull);
      });

      test('tracks bytes received correctly', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = observableClient.requestStream(
          'GET',
          Uri.parse('https://example.com'),
        );

        final completer = Completer<void>();
        stream.listen(
          (_) {},
          onDone: completer.complete,
        );

        await Future<void>.delayed(const Duration(milliseconds: 10));

        // Send varying chunk sizes
        controller
          ..add([1, 2, 3, 4, 5]) // 5 bytes
          ..add([6, 7, 8]) // 3 bytes
          ..add([9, 10, 11, 12, 13, 14, 15]); // 7 bytes
        await controller.close();

        await completer.future;

        final endEvent = recorder.eventsOfType<HttpStreamEndEvent>().first;
        expect(endEvent.bytesReceived, equals(15));
      });
    });

    group('stream lifecycle - error', () {
      test('notifies observer on stream error with SoliplexException',
          () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = observableClient.requestStream(
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

        // Add some data before error
        controller.add([1, 2, 3]);
        await Future<void>.delayed(const Duration(milliseconds: 10));

        // Emit error
        controller.addError(
          const NetworkException(message: 'Connection lost'),
        );

        await completer.future;

        expect(errors, hasLength(1));
        expect(errors.first, isA<NetworkException>());

        final endEvent = recorder.eventsOfType<HttpStreamEndEvent>().first;
        expect(endEvent.bytesReceived, equals(3));
        expect(endEvent.isSuccess, isFalse);
        expect(endEvent.error, isA<NetworkException>());

        await controller.close();
      });

      test('wraps non-SoliplexException errors in NetworkException', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = observableClient.requestStream(
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

        // Emit non-SoliplexException error
        controller.addError(Exception('Generic error'));

        await completer.future;

        // Original error should be passed through
        expect(errors.first, isA<Exception>());

        // Observer should receive wrapped NetworkException
        final endEvent = recorder.eventsOfType<HttpStreamEndEvent>().first;
        expect(endEvent.error, isA<NetworkException>());
        expect(endEvent.error!.message, contains('Generic error'));

        await controller.close();
      });
    });

    group('multiple observers', () {
      test('notifies all observers in order', () async {
        final recorder1 = RecordingObserver();
        final recorder2 = RecordingObserver();
        final recorder3 = RecordingObserver();

        final observableClient = ObservableHttpClient(
          client: mockClient,
          observers: [recorder1, recorder2, recorder3],
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        await observableClient.request('GET', Uri.parse('https://example.com'));

        // All observers should have same events
        expect(recorder1.events, hasLength(2));
        expect(recorder2.events, hasLength(2));
        expect(recorder3.events, hasLength(2));

        // Same request ID across all observers
        final id1 = recorder1.eventsOfType<HttpRequestEvent>().first.requestId;
        final id2 = recorder2.eventsOfType<HttpRequestEvent>().first.requestId;
        final id3 = recorder3.eventsOfType<HttpRequestEvent>().first.requestId;
        expect(id1, equals(id2));
        expect(id2, equals(id3));

        observableClient.close();
      });

      test('one observer exception does not affect others', () async {
        final recorder1 = RecordingObserver();
        final throwingObserver = ThrowingObserver();
        final recorder2 = RecordingObserver();

        final observableClient = ObservableHttpClient(
          client: mockClient,
          observers: [recorder1, throwingObserver, recorder2],
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        // Should not throw despite throwing observer
        await expectLater(
          observableClient.request('GET', Uri.parse('https://example.com')),
          completes,
        );

        // Both recording observers should still receive events
        expect(recorder1.events, hasLength(2));
        expect(recorder2.events, hasLength(2));

        observableClient.close();
      });
    });

    group('observer error isolation', () {
      test('observer throwing on request does not break request', () async {
        final observableClient = ObservableHttpClient(
          client: mockClient,
          observers: [ThrowingObserver()],
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List.fromList([1, 2, 3]),
          ),
        );

        final result = await observableClient.request(
          'GET',
          Uri.parse('https://example.com'),
        );

        expect(result.statusCode, equals(200));
        expect(result.bodyBytes, hasLength(3));

        observableClient.close();
      });

      test('observer throwing on response does not break request', () async {
        final observableClient = ObservableHttpClient(
          client: mockClient,
          observers: [ThrowingObserver()],
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 201,
            bodyBytes: Uint8List(0),
          ),
        );

        final result = await observableClient.request(
          'POST',
          Uri.parse('https://example.com'),
        );

        expect(result.statusCode, equals(201));

        observableClient.close();
      });

      test('observer throwing on error does not suppress exception', () async {
        final observableClient = ObservableHttpClient(
          client: mockClient,
          observers: [ThrowingObserver()],
        );

        const originalException = NetworkException(message: 'Network failed');

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(originalException);

        await expectLater(
          observableClient.request('GET', Uri.parse('https://example.com')),
          throwsA(equals(originalException)),
        );

        observableClient.close();
      });

      test('observer throwing on stream events does not break stream',
          () async {
        final observableClient = ObservableHttpClient(
          client: mockClient,
          observers: [ThrowingObserver()],
        );

        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = observableClient.requestStream(
          'GET',
          Uri.parse('https://example.com'),
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
        );

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

        observableClient.close();
      });
    });

    group('request ID correlation', () {
      test('same requestId across request/response events', () async {
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        await observableClient.request(
          'GET',
          Uri.parse('https://example.com'),
        );

        final requestEvent = recorder.eventsOfType<HttpRequestEvent>().first;
        final responseEvent = recorder.eventsOfType<HttpResponseEvent>().first;

        expect(requestEvent.requestId, isNotEmpty);
        expect(responseEvent.requestId, equals(requestEvent.requestId));
      });

      test('same requestId across request/error events', () async {
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(const NetworkException(message: 'Failed'));

        try {
          await observableClient.request(
            'GET',
            Uri.parse('https://example.com'),
          );
        } on NetworkException {
          // Expected
        }

        final requestEvent = recorder.eventsOfType<HttpRequestEvent>().first;
        final errorEvent = recorder.eventsOfType<HttpErrorEvent>().first;

        expect(errorEvent.requestId, equals(requestEvent.requestId));
      });

      test('same requestId across stream start/end events', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = observableClient.requestStream(
          'GET',
          Uri.parse('https://example.com'),
        );

        final completer = Completer<void>();
        stream.listen((_) {}, onDone: completer.complete);

        await Future<void>.delayed(const Duration(milliseconds: 10));
        await controller.close();
        await completer.future;

        final startEvent = recorder.eventsOfType<HttpStreamStartEvent>().first;
        final endEvent = recorder.eventsOfType<HttpStreamEndEvent>().first;

        expect(startEvent.requestId, isNotEmpty);
        expect(endEvent.requestId, equals(startEvent.requestId));
      });

      test('different requests have different IDs', () async {
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        await observableClient.request(
          'GET',
          Uri.parse('https://example.com/1'),
        );
        await observableClient.request(
          'GET',
          Uri.parse('https://example.com/2'),
        );

        final requestEvents = recorder.eventsOfType<HttpRequestEvent>();
        expect(requestEvents, hasLength(2));
        expect(
          requestEvents[0].requestId,
          isNot(equals(requestEvents[1].requestId)),
        );
      });
    });

    group('custom request ID generator', () {
      test('uses provided generator', () async {
        var callCount = 0;
        final customClient = ObservableHttpClient(
          client: mockClient,
          observers: [recorder],
          generateRequestId: () => 'custom-id-${++callCount}',
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        await customClient.request('GET', Uri.parse('https://example.com'));

        final requestEvent = recorder.eventsOfType<HttpRequestEvent>().first;
        expect(requestEvent.requestId, equals('custom-id-1'));

        customClient.close();
      });
    });

    group('close delegation', () {
      test('delegates close to wrapped client', () {
        observableClient.close();

        verify(() => mockClient.close()).called(1);
      });

      test('does not notify observers on close', () {
        observableClient.close();

        expect(recorder.events, isEmpty);
      });
    });

    group('empty observer list', () {
      test('works correctly with no observers', () async {
        final clientNoObservers = ObservableHttpClient(
          client: mockClient,
        );

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List.fromList([1, 2, 3]),
          ),
        );

        final result = await clientNoObservers.request(
          'GET',
          Uri.parse('https://example.com'),
        );

        expect(result.statusCode, equals(200));
        expect(result.bodyBytes, hasLength(3));

        clientNoObservers.close();
      });

      test('streaming works with no observers', () async {
        final clientNoObservers = ObservableHttpClient(
          client: mockClient,
        );

        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final stream = clientNoObservers.requestStream(
          'GET',
          Uri.parse('https://example.com'),
        );

        final chunks = <List<int>>[];
        final completer = Completer<void>();

        stream.listen(
          chunks.add,
          onDone: completer.complete,
        );

        await Future<void>.delayed(const Duration(milliseconds: 10));

        controller
          ..add([1, 2])
          ..add([3, 4]);
        await controller.close();

        await completer.future;

        expect(
          chunks,
          equals([
            [1, 2],
            [3, 4],
          ]),
        );

        clientNoObservers.close();
      });
    });

    group('parameters forwarding', () {
      test('forwards all request parameters to wrapped client', () async {
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => HttpResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          ),
        );

        await observableClient.request(
          'POST',
          Uri.parse('https://example.com/api'),
          headers: {'X-Custom': 'value'},
          body: {'key': 'data'},
          timeout: const Duration(seconds: 10),
        );

        verify(
          () => mockClient.request(
            'POST',
            Uri.parse('https://example.com/api'),
            headers: {'X-Custom': 'value'},
            body: {'key': 'data'},
            timeout: const Duration(seconds: 10),
          ),
        ).called(1);
      });

      test('forwards all stream parameters to wrapped client', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        // Start listening to trigger the request
        final subscription = observableClient
            .requestStream(
              'POST',
              Uri.parse('https://example.com/stream'),
              headers: const {'Accept': 'text/event-stream'},
              body: 'test body',
            )
            .listen((_) {});

        // Give time for stream to start
        await Future<void>.delayed(const Duration(milliseconds: 10));

        verify(
          () => mockClient.requestStream(
            'POST',
            Uri.parse('https://example.com/stream'),
            headers: const {'Accept': 'text/event-stream'},
            body: 'test body',
          ),
        ).called(1);

        await subscription.cancel();
        await controller.close();
      });
    });
  });
}
