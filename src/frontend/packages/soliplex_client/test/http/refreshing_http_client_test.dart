import 'dart:async';
import 'dart:typed_data';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockSoliplexHttpClient extends Mock implements SoliplexHttpClient {}

class MockTokenRefresher extends Mock implements TokenRefresher {}

/// Fake TokenRefresher for integration tests.
///
/// Uses real async behavior to test concurrent refresh deduplication.
class FakeTokenRefresher implements TokenRefresher {
  int refreshCallCount = 0;
  Duration refreshDelay = Duration.zero;
  bool refreshResult = true;

  @override
  bool needsRefresh = false;

  @override
  Future<void> refreshIfExpiringSoon() async {
    // No-op for these tests
  }

  @override
  Future<bool> tryRefresh() async {
    refreshCallCount++;
    if (refreshDelay > Duration.zero) {
      await Future<void>.delayed(refreshDelay);
    }
    return refreshResult;
  }
}

/// Fake HTTP client that returns configurable responses.
class FakeHttpClient implements SoliplexHttpClient {
  final List<HttpResponse> _responses = [];
  int _callIndex = 0;
  int get callCount => _callIndex;

  void queueResponse(int statusCode) {
    _responses.add(
      HttpResponse(statusCode: statusCode, bodyBytes: Uint8List(0)),
    );
  }

  @override
  Future<HttpResponse> request(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
  }) async {
    if (_callIndex >= _responses.length) {
      throw StateError(
        'FakeHttpClient: no more queued responses '
        '(called ${_callIndex + 1} times, only ${_responses.length} queued)',
      );
    }
    return _responses[_callIndex++];
  }

  @override
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
  }) {
    return const Stream.empty();
  }

  @override
  void close() {}
}

void main() {
  late MockSoliplexHttpClient mockClient;
  late MockTokenRefresher mockRefresher;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockClient = MockSoliplexHttpClient();
    mockRefresher = MockTokenRefresher();
    when(() => mockClient.close()).thenReturn(null);
    when(() => mockRefresher.needsRefresh).thenReturn(false);
    when(() => mockRefresher.refreshIfExpiringSoon())
        .thenAnswer((_) async => {});
    when(() => mockRefresher.tryRefresh()).thenAnswer((_) async => true);
  });

  tearDown(() {
    reset(mockClient);
    reset(mockRefresher);
  });

  HttpResponse successResponse([int statusCode = 200]) => HttpResponse(
        statusCode: statusCode,
        bodyBytes: Uint8List(0),
      );

  void setupRequestSuccess([int statusCode = 200]) {
    when(
      () => mockClient.request(
        any(),
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
        timeout: any(named: 'timeout'),
      ),
    ).thenAnswer((_) async => successResponse(statusCode));
  }

  group('RefreshingHttpClient', () {
    group('proactive refresh', () {
      test('calls refreshIfExpiringSoon before each request', () async {
        setupRequestSuccess();
        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        await client.request('GET', Uri.parse('https://example.com/api'));

        verify(() => mockRefresher.refreshIfExpiringSoon()).called(1);
        client.close();
      });

      test('makes request after proactive refresh completes', () async {
        var refreshCompleted = false;
        when(() => mockRefresher.refreshIfExpiringSoon()).thenAnswer((_) async {
          refreshCompleted = true;
        });

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async {
          expect(refreshCompleted, isTrue);
          return successResponse();
        });

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        await client.request('GET', Uri.parse('https://example.com/api'));
        client.close();
      });
    });

    group('401 retry', () {
      test('retries once on 401 after successful refresh', () async {
        var callCount = 0;
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async {
          callCount++;
          if (callCount == 1) return successResponse(401);
          return successResponse();
        });

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final response = await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(response.statusCode, equals(200));
        verify(() => mockRefresher.tryRefresh()).called(1);
        expect(callCount, equals(2));
        client.close();
      });

      test('does not retry second 401 (prevents infinite loop)', () async {
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => successResponse(401));

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final response = await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(response.statusCode, equals(401));
        verify(() => mockRefresher.tryRefresh()).called(1);
        verify(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(2);
        client.close();
      });

      test('returns 401 if refresh fails', () async {
        when(() => mockRefresher.tryRefresh()).thenAnswer((_) async => false);
        setupRequestSuccess(401);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final response = await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(response.statusCode, equals(401));
        verify(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
        client.close();
      });

      test('does not retry non-401 error codes', () async {
        setupRequestSuccess(403);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final response = await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        expect(response.statusCode, equals(403));
        verifyNever(() => mockRefresher.tryRefresh());
        client.close();
      });
    });

    group('concurrent refresh deduplication', () {
      test('multiple 401s share single refresh call', () async {
        final refreshCompleter = Completer<bool>();
        when(() => mockRefresher.tryRefresh())
            .thenAnswer((_) => refreshCompleter.future);

        var call401Count = 0;
        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async {
          call401Count++;
          if (call401Count <= 2) return successResponse(401);
          return successResponse();
        });

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final request1 = client.request(
          'GET',
          Uri.parse('https://example.com/1'),
        );
        final request2 = client.request(
          'GET',
          Uri.parse('https://example.com/2'),
        );

        // Wait for both to hit 401 and start waiting for refresh
        await Future<void>.delayed(Duration.zero);
        await Future<void>.delayed(Duration.zero);

        // Complete refresh
        refreshCompleter.complete(true);

        await Future.wait([request1, request2]);

        // Only one refresh call despite two concurrent 401s
        verify(() => mockRefresher.tryRefresh()).called(1);
        client.close();
      });

      test('refresh error propagates to all waiting requests', () async {
        final refreshCompleter = Completer<bool>();
        when(() => mockRefresher.tryRefresh())
            .thenAnswer((_) => refreshCompleter.future);

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => successResponse(401));

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final request1 = client.request(
          'GET',
          Uri.parse('https://example.com/1'),
        );
        final request2 = client.request(
          'GET',
          Uri.parse('https://example.com/2'),
        );

        await Future<void>.delayed(Duration.zero);
        await Future<void>.delayed(Duration.zero);

        refreshCompleter.completeError(Exception('refresh failed'));

        await expectLater(request1, throwsException);
        await expectLater(request2, throwsException);

        client.close();
      });
    });

    group('stream requests', () {
      test('calls refreshIfExpiringSoon before stream request', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        final subscription = stream.listen((_) {});
        await Future<void>.delayed(Duration.zero);

        verify(() => mockRefresher.refreshIfExpiringSoon()).called(1);

        await subscription.cancel();
        await controller.close();
        client.close();
      });

      test('does not attempt retry on stream (cannot intercept 401)', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        final subscription = stream.listen((_) {});
        await Future<void>.delayed(Duration.zero);

        verifyNever(() => mockRefresher.tryRefresh());

        await subscription.cancel();
        await controller.close();
        client.close();
      });
    });

    group('parameter forwarding', () {
      test('forwards all request parameters', () async {
        setupRequestSuccess();

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
          headers: {'Content-Type': 'application/json'},
          body: {'key': 'value'},
          timeout: const Duration(seconds: 30),
        );

        verify(
          () => mockClient.request(
            'POST',
            Uri.parse('https://example.com/api'),
            headers: {'Content-Type': 'application/json'},
            body: {'key': 'value'},
            timeout: const Duration(seconds: 30),
          ),
        ).called(1);

        client.close();
      });

      test('forwards all stream parameters', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final stream = client.requestStream(
          'POST',
          Uri.parse('https://example.com/stream'),
          headers: {'Accept': 'text/event-stream'},
          body: 'request body',
        );

        final subscription = stream.listen((_) {});
        await Future<void>.delayed(Duration.zero);

        verify(
          () => mockClient.requestStream(
            'POST',
            Uri.parse('https://example.com/stream'),
            headers: {'Accept': 'text/event-stream'},
            body: 'request body',
          ),
        ).called(1);

        await subscription.cancel();
        await controller.close();
        client.close();
      });
    });

    group('close delegation', () {
      test('delegates close to inner client', () {
        RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        ).close();

        verify(() => mockClient.close()).called(1);
      });
    });

    group('response passthrough', () {
      test('returns successful response unchanged', () async {
        final expectedResponse = HttpResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList([65, 66, 67]),
          headers: const {'x-custom': 'header'},
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
        ).thenAnswer((_) async => expectedResponse);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        final result = await client.request(
          'GET',
          Uri.parse('https://example.com'),
        );

        expect(result.statusCode, equals(200));
        expect(result.body, equals('ABC'));
        expect(result.headers['x-custom'], equals('header'));
        expect(result.reasonPhrase, equals('OK'));

        client.close();
      });

      test('propagates exceptions from inner client', () async {
        const exception = NetworkException(message: 'Connection failed');

        when(
          () => mockClient.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(exception);

        final client = RefreshingHttpClient(
          inner: mockClient,
          refresher: mockRefresher,
        );

        await expectLater(
          client.request('GET', Uri.parse('https://example.com')),
          throwsA(isA<NetworkException>()),
        );

        client.close();
      });
    });
  });

  // Integration tests using fakes instead of mocks to verify real async
  // behavior. Mocks complete synchronously, hiding race conditions. These
  // tests use fakes with configurable delays to verify that concurrent 401s
  // share a single refresh call rather than triggering redundant refreshes.
  group('RefreshingHttpClient integration', () {
    late FakeHttpClient fakeClient;
    late FakeTokenRefresher fakeRefresher;

    setUp(() {
      fakeClient = FakeHttpClient();
      fakeRefresher = FakeTokenRefresher();
    });

    group('concurrent refresh with real async', () {
      test('deduplicates concurrent 401 refresh calls', () async {
        // Queue: 401, 401, 200, 200 (two initial failures, then success after
        // refresh)
        fakeClient
          ..queueResponse(401)
          ..queueResponse(401)
          ..queueResponse(200)
          ..queueResponse(200);

        // Simulate real network delay in refresh
        fakeRefresher.refreshDelay = const Duration(milliseconds: 10);

        final client = RefreshingHttpClient(
          inner: fakeClient,
          refresher: fakeRefresher,
        );

        // Fire two concurrent requests
        final results = await Future.wait([
          client.request('GET', Uri.parse('https://example.com/1')),
          client.request('GET', Uri.parse('https://example.com/2')),
        ]);

        // Both should succeed after shared refresh
        expect(results[0].statusCode, equals(200));
        expect(results[1].statusCode, equals(200));

        // Only ONE refresh call despite two concurrent 401s
        expect(fakeRefresher.refreshCallCount, equals(1));

        // 4 HTTP calls: 2 initial 401s + 2 retries
        expect(fakeClient.callCount, equals(4));

        client.close();
      });

      test('sequential 401s each trigger separate refresh', () async {
        // First request: 401 -> refresh -> 200
        // Second request: 401 -> refresh -> 200
        fakeClient
          ..queueResponse(401)
          ..queueResponse(200)
          ..queueResponse(401)
          ..queueResponse(200);

        final client = RefreshingHttpClient(
          inner: fakeClient,
          refresher: fakeRefresher,
        );

        // Sequential requests (not concurrent)
        final result1 = await client.request(
          'GET',
          Uri.parse('https://example.com/1'),
        );
        final result2 = await client.request(
          'GET',
          Uri.parse('https://example.com/2'),
        );

        expect(result1.statusCode, equals(200));
        expect(result2.statusCode, equals(200));

        // Two separate refresh calls (not deduplicated)
        expect(fakeRefresher.refreshCallCount, equals(2));

        client.close();
      });

      test('refresh failure affects all waiting requests', () async {
        fakeClient
          ..queueResponse(401)
          ..queueResponse(401);

        fakeRefresher
          ..refreshDelay = const Duration(milliseconds: 10)
          ..refreshResult = false;

        final client = RefreshingHttpClient(
          inner: fakeClient,
          refresher: fakeRefresher,
        );

        final results = await Future.wait([
          client.request('GET', Uri.parse('https://example.com/1')),
          client.request('GET', Uri.parse('https://example.com/2')),
        ]);

        // Both return 401 since refresh failed
        expect(results[0].statusCode, equals(401));
        expect(results[1].statusCode, equals(401));

        // Still only one refresh attempt
        expect(fakeRefresher.refreshCallCount, equals(1));

        // Only 2 HTTP calls - no retry after failed refresh
        expect(fakeClient.callCount, equals(2));

        client.close();
      });

      test('new request after refresh completes gets fresh refresh', () async {
        fakeClient
          ..queueResponse(401)
          ..queueResponse(200)
          ..queueResponse(401)
          ..queueResponse(200);

        fakeRefresher.refreshDelay = const Duration(milliseconds: 5);

        final client = RefreshingHttpClient(
          inner: fakeClient,
          refresher: fakeRefresher,
        );

        // First request triggers refresh
        final result1 = await client.request(
          'GET',
          Uri.parse('https://example.com/1'),
        );
        expect(result1.statusCode, equals(200));
        expect(fakeRefresher.refreshCallCount, equals(1));

        // Second request after first completes - if it 401s, gets fresh refresh
        final result2 = await client.request(
          'GET',
          Uri.parse('https://example.com/2'),
        );
        expect(result2.statusCode, equals(200));
        expect(fakeRefresher.refreshCallCount, equals(2));

        client.close();
      });
    });
  });
}
