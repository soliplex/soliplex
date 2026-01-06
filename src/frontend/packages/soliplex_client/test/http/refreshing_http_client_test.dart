import 'dart:async';
import 'dart:typed_data';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockSoliplexHttpClient extends Mock implements SoliplexHttpClient {}

class MockTokenRefresher extends Mock implements TokenRefresher {}

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
}
