import 'dart:async';
import 'dart:typed_data';

import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockSoliplexHttpClient extends Mock implements SoliplexHttpClient {}

void main() {
  late MockSoliplexHttpClient mockClient;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockClient = MockSoliplexHttpClient();
    when(() => mockClient.close()).thenReturn(null);
  });

  tearDown(() {
    reset(mockClient);
  });

  group('AuthenticatedHttpClient', () {
    group('token injection', () {
      test('injects Authorization header when token is available', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'test-token-123',
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

        await client.request('GET', Uri.parse('https://example.com/api'));

        final captured = verify(
          () => mockClient.request(
            'GET',
            Uri.parse('https://example.com/api'),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers['Authorization'], equals('Bearer test-token-123'));

        client.close();
      });

      test('skips auth header when token is null', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => null,
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

        await client.request('GET', Uri.parse('https://example.com/api'));

        final captured = verify(
          () => mockClient.request(
            'GET',
            Uri.parse('https://example.com/api'),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers.containsKey('Authorization'), isFalse);

        client.close();
      });

      test('calls getToken for each request', () async {
        var callCount = 0;
        final client = AuthenticatedHttpClient(
          mockClient,
          () {
            callCount++;
            return 'token-$callCount';
          },
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

        await client.request('GET', Uri.parse('https://example.com/1'));
        await client.request('GET', Uri.parse('https://example.com/2'));

        expect(callCount, equals(2));

        client.close();
      });
    });

    group('header merging', () {
      test('preserves existing headers when adding auth', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
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

        await client.request(
          'GET',
          Uri.parse('https://example.com/api'),
          headers: {
            'Content-Type': 'application/json',
            'X-Custom': 'value',
          },
        );

        final captured = verify(
          () => mockClient.request(
            any(),
            any(),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers['Content-Type'], equals('application/json'));
        expect(headers['X-Custom'], equals('value'));
        expect(headers['Authorization'], equals('Bearer token'));

        client.close();
      });

      test('handles null headers parameter', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
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

        await client.request('GET', Uri.parse('https://example.com/api'));

        final captured = verify(
          () => mockClient.request(
            any(),
            any(),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers, equals({'Authorization': 'Bearer token'}));

        client.close();
      });

      test('skips auth header when token is null (stream)', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => null,
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

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/api'),
        );

        final subscription = stream.listen((_) {});

        final captured = verify(
          () => mockClient.requestStream(
            'GET',
            Uri.parse('https://example.com/api'),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers.containsKey('Authorization'), isFalse);

        await subscription.cancel();
        await controller.close();
        client.close();
      });
    });

    group('requestStream', () {
      test('injects token into stream requests', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'stream-token',
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

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
        );

        // Start listening to trigger the call
        final subscription = stream.listen((_) {});

        final captured = verify(
          () => mockClient.requestStream(
            'GET',
            Uri.parse('https://example.com/stream'),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers['Authorization'], equals('Bearer stream-token'));

        await subscription.cancel();
        await controller.close();
        client.close();
      });

      test('preserves existing headers in stream requests', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
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

        final stream = client.requestStream(
          'GET',
          Uri.parse('https://example.com/stream'),
          headers: {'Accept': 'text/event-stream'},
        );

        final subscription = stream.listen((_) {});

        final captured = verify(
          () => mockClient.requestStream(
            any(),
            any(),
            headers: captureAny(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).captured;

        final headers = captured.first as Map<String, String>;
        expect(headers['Accept'], equals('text/event-stream'));
        expect(headers['Authorization'], equals('Bearer token'));

        await subscription.cancel();
        await controller.close();
        client.close();
      });
    });

    group('parameter forwarding', () {
      test('forwards all request parameters', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
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
            bodyBytes: Uint8List.fromList([1, 2, 3]),
          ),
        );

        final result = await client.request(
          'POST',
          Uri.parse('https://example.com/api'),
          body: {'key': 'value'},
          timeout: const Duration(seconds: 30),
        );

        expect(result.statusCode, equals(201));
        expect(result.bodyBytes, hasLength(3));

        verify(
          () => mockClient.request(
            'POST',
            Uri.parse('https://example.com/api'),
            headers: any(named: 'headers'),
            body: {'key': 'value'},
            timeout: const Duration(seconds: 30),
          ),
        ).called(1);

        client.close();
      });

      test('forwards all stream parameters', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
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

        final stream = client.requestStream(
          'POST',
          Uri.parse('https://example.com/stream'),
          body: 'request body',
        );

        final subscription = stream.listen((_) {});

        verify(
          () => mockClient.requestStream(
            'POST',
            Uri.parse('https://example.com/stream'),
            headers: any(named: 'headers'),
            body: 'request body',
          ),
        ).called(1);

        await subscription.cancel();
        await controller.close();
        client.close();
      });
    });

    group('close delegation', () {
      test('delegates close to wrapped client', () {
        AuthenticatedHttpClient(
          mockClient,
          () => 'token',
        ).close();

        verify(() => mockClient.close()).called(1);
      });
    });

    group('response passthrough', () {
      test('returns response unchanged', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
        );

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

      test('propagates exceptions unchanged', () async {
        final client = AuthenticatedHttpClient(
          mockClient,
          () => 'token',
        );

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

        Object? caughtError;
        try {
          await client.request('GET', Uri.parse('https://example.com'));
        } catch (e) {
          caughtError = e;
        }
        expect(caughtError, isA<AuthException>());

        client.close();
      });
    });
  });
}
