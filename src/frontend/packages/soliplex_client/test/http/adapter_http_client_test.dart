import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockHttpClientAdapter extends Mock implements HttpClientAdapter {}

void main() {
  late MockHttpClientAdapter mockAdapter;
  late AdapterHttpClient httpClient;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  setUp(() {
    mockAdapter = MockHttpClientAdapter();
    httpClient = AdapterHttpClient(adapter: mockAdapter);
    when(() => mockAdapter.close()).thenReturn(null);
  });

  tearDown(() {
    httpClient.close();
    reset(mockAdapter);
  });

  group('AdapterHttpClient', () {
    group('regular requests (non-SSE)', () {
      test('delegates GET request to adapter.request', () async {
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList('{"data": "test"}'.codeUnits),
          headers: const {'content-type': 'application/json'},
          reasonPhrase: 'OK',
        );

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => response);

        final request = http.Request('GET', Uri.parse('https://api.test/data'));
        final streamedResponse = await httpClient.send(request);

        expect(streamedResponse.statusCode, 200);
        expect(streamedResponse.reasonPhrase, 'OK');

        final body = await streamedResponse.stream.bytesToString();
        expect(body, '{"data": "test"}');

        verify(
          () => mockAdapter.request(
            'GET',
            Uri.parse('https://api.test/data'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('delegates POST request with body to adapter.request', () async {
        final response = AdapterResponse(
          statusCode: 201,
          bodyBytes: Uint8List.fromList('{"id": 1}'.codeUnits),
          headers: const {'content-type': 'application/json'},
          reasonPhrase: 'Created',
        );

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => response);

        final request = http.Request('POST', Uri.parse('https://api.test/data'))
          ..headers['content-type'] = 'application/json'
          ..body = '{"name": "test"}';

        final streamedResponse = await httpClient.send(request);

        expect(streamedResponse.statusCode, 201);
        expect(streamedResponse.reasonPhrase, 'Created');

        verify(
          () => mockAdapter.request(
            'POST',
            Uri.parse('https://api.test/data'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('returns proper headers and content length', () async {
        final bodyBytes = Uint8List.fromList('response body'.codeUnits);
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: bodyBytes,
          headers: const {
            'content-type': 'text/plain',
            'x-custom': 'value',
          },
        );

        when(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => response);

        final request = http.Request('GET', Uri.parse('https://api.test/data'));
        final streamedResponse = await httpClient.send(request);

        expect(streamedResponse.headers['content-type'], 'text/plain');
        expect(streamedResponse.headers['x-custom'], 'value');
        expect(streamedResponse.contentLength, bodyBytes.length);
      });
    });

    group('SSE requests', () {
      test('delegates SSE request to adapter.requestStream', () async {
        final controller = StreamController<List<int>>.broadcast();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final request = http.Request('POST', Uri.parse('https://api.test/sse'))
          ..headers['accept'] = 'text/event-stream'
          ..headers['content-type'] = 'application/json'
          ..body = '{"message": "hello"}';

        final streamedResponse = await httpClient.send(request);

        // SSE streams return 200 (errors throw before returning)
        expect(streamedResponse.statusCode, 200);
        expect(streamedResponse.headers['content-type'], 'text/event-stream');

        verify(
          () => mockAdapter.requestStream(
            'POST',
            Uri.parse('https://api.test/sse'),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).called(1);

        // Verify request() was NOT called
        verifyNever(
          () => mockAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        );

        unawaited(controller.close());
      });

      test('streams SSE data correctly', () async {
        final controller = StreamController<List<int>>();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        final request = http.Request('GET', Uri.parse('https://api.test/sse'))
          ..headers['accept'] = 'text/event-stream';

        final streamedResponse = await httpClient.send(request);

        final receivedData = <String>[];
        unawaited(
          streamedResponse.stream
              .transform(const Utf8Decoder())
              .forEach(receivedData.add),
        );

        // Simulate SSE events
        controller
          ..add('data: event1\n\n'.codeUnits)
          ..add('data: event2\n\n'.codeUnits);
        await controller.close();

        // Give time for stream to process
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(receivedData, ['data: event1\n\n', 'data: event2\n\n']);
      });

      test('detects SSE by Accept header case-insensitively', () async {
        final controller = StreamController<List<int>>.broadcast();

        when(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => controller.stream);

        // Test with 'Accept' (capital A)
        final request = http.Request('GET', Uri.parse('https://api.test/sse'))
          ..headers['Accept'] = 'text/event-stream';

        await httpClient.send(request);

        verify(
          () => mockAdapter.requestStream(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).called(1);

        unawaited(controller.close());
      });
    });

    group('close', () {
      test('delegates to adapter.close', () {
        httpClient.close();

        verify(() => mockAdapter.close()).called(1);
      });
    });

    group('integration with ObservableHttpAdapter', () {
      test('works with ObservableHttpAdapter wrapper', () async {
        final baseAdapter = MockHttpClientAdapter();
        final observer = _RecordingObserver();

        when(baseAdapter.close).thenReturn(null);

        final observableAdapter = ObservableHttpAdapter(
          adapter: baseAdapter,
          observers: [observer],
        );

        final client = AdapterHttpClient(adapter: observableAdapter);

        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList('ok'.codeUnits),
        );

        when(
          () => baseAdapter.request(
            any(),
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => response);

        final request = http.Request('GET', Uri.parse('https://api.test/data'));
        await client.send(request);

        // Observer should have recorded events
        expect(observer.requestEvents, hasLength(1));
        expect(observer.responseEvents, hasLength(1));

        client.close();
      });
    });
  });
}

/// Simple recording observer for testing.
class _RecordingObserver implements HttpObserver {
  final requestEvents = <HttpRequestEvent>[];
  final responseEvents = <HttpResponseEvent>[];
  final errorEvents = <HttpErrorEvent>[];

  @override
  void onRequest(HttpRequestEvent event) => requestEvents.add(event);

  @override
  void onResponse(HttpResponseEvent event) => responseEvents.add(event);

  @override
  void onError(HttpErrorEvent event) => errorEvents.add(event);

  @override
  void onStreamStart(HttpStreamStartEvent event) {}

  @override
  void onStreamEnd(HttpStreamEndEvent event) {}
}
