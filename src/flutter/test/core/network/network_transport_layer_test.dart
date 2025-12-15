import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';

/// Mock AgUiClient for testing SSE streaming.
class MockAgUiClient extends Mock implements ag_ui.AgUiClient {}

/// Fake SimpleRunAgentInput for registerFallbackValue.
class FakeSimpleRunAgentInput extends Fake
    implements ag_ui.SimpleRunAgentInput {}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeSimpleRunAgentInput());
  });

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

        await expectLater(() => layer.post(uri, '{}'), throwsException);

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
        final layer = NetworkTransportLayer(baseUrl: 'http://localhost:8080');

        layer.close();

        final uri = Uri.parse('http://localhost:8080/api/test');
        await expectLater(() => layer.post(uri, '{}'), throwsStateError);
      });

      test('isDisposed returns true after close', () {
        final layer = NetworkTransportLayer(baseUrl: 'http://localhost:8080');

        expect(layer.isDisposed, isFalse);
        layer.close();
        expect(layer.isDisposed, isTrue);
      });

      test('close is idempotent', () {
        final layer = NetworkTransportLayer(baseUrl: 'http://localhost:8080');

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
        final layer = NetworkTransportLayer(baseUrl: 'http://localhost:8080');

        expect(layer.agUiClient, isNotNull);

        layer.close();
      });

      test('uses injected AgUiClient when provided', () {
        final mockAgUiClient = MockAgUiClient();
        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
        );

        expect(layer.agUiClient, same(mockAgUiClient));

        layer.close();
      });
    });

    group('runAgent', () {
      late MockAgUiClient mockAgUiClient;

      setUp(() {
        mockAgUiClient = MockAgUiClient();
      });

      test('streams events from AgUiClient', () async {
        final events = [
          const ag_ui.RunStartedEvent(threadId: 't1', runId: 'r1'),
          const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          ),
          const ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Hello'),
          const ag_ui.TextMessageEndEvent(messageId: 'm1'),
          const ag_ui.RunFinishedEvent(threadId: 't1', runId: 'r1'),
        ];

        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => Stream.fromIterable(events));

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1', runId: 'r1');
        final receivedEvents = await layer
            .runAgent('api/v1/agent', input)
            .toList();

        expect(receivedEvents.length, equals(5));
        expect(receivedEvents[0], isA<ag_ui.RunStartedEvent>());
        expect(receivedEvents[4], isA<ag_ui.RunFinishedEvent>());

        layer.close();
      });

      test('throws StateError when disposed', () async {
        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
        );

        layer.close();

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1');
        // runAgent is an async* generator, so StateError is thrown during
        // iteration
        await expectLater(
          layer.runAgent('api/v1/agent', input).toList(),
          throwsStateError,
        );
      });

      test('normalizes endpoint without leading slash', () async {
        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => const Stream.empty());

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1');
        await layer.runAgent('api/v1/agent', input).toList();

        // Verify inspector recorded correct URI with normalized path
        expect(inspector.entryCount, equals(1));
        final entry = inspector.entries.first;
        expect(entry.uri.path, equals('/api/v1/agent'));

        layer.close();
      });

      test('preserves endpoint with leading slash', () async {
        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => const Stream.empty());

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1');
        await layer.runAgent('/api/v1/agent', input).toList();

        // Verify inspector recorded correct URI
        expect(inspector.entryCount, equals(1));
        final entry = inspector.entries.first;
        expect(entry.uri.path, equals('/api/v1/agent'));

        layer.close();
      });

      test('records SSE request in inspector', () async {
        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => const Stream.empty());

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1', runId: 'r1');
        await layer.runAgent('/api/v1/agent', input).toList();

        expect(inspector.entryCount, equals(1));
        final entry = inspector.entries.first;
        expect(entry.method, equals('SSE'));
        expect(entry.isComplete, isTrue);
        expect(entry.statusCode, equals(200));

        layer.close();
      });

      test('records event count in inspector response', () async {
        final events = List.generate(
          10,
          (i) =>
              ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'chunk $i'),
        );

        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => Stream.fromIterable(events));

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1');
        await layer.runAgent('/agent', input).toList();

        final entry = inspector.entries.first;
        expect(entry.responseHeaders?['x-sse-event-count'], equals('10'));

        layer.close();
      });

      test('records error in inspector on stream failure', () async {
        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => Stream.error(Exception('SSE connection failed')));

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1');

        await expectLater(
          layer.runAgent('/agent', input).toList(),
          throwsException,
        );

        expect(inspector.entryCount, equals(1));
        final entry = inspector.entries.first;
        expect(entry.isError, isTrue);
        expect(entry.error, contains('SSE connection failed'));

        layer.close();
      });

      test('uses headers when recording SSE request', () async {
        when(
          () => mockAgUiClient.runAgent(any(), any()),
        ).thenAnswer((_) => const Stream.empty());

        final layer = NetworkTransportLayer(
          baseUrl: 'http://localhost:8080',
          agUiClient: mockAgUiClient,
          defaultHeaders: {'Authorization': 'Bearer test-token'},
          inspector: inspector,
        );

        const input = ag_ui.SimpleRunAgentInput(threadId: 't1');
        await layer.runAgent('/agent', input).toList();

        final entry = inspector.entries.first;
        expect(
          entry.requestHeaders['Authorization'],
          equals('Bearer test-token'),
        );

        layer.close();
      });
    });
  });
}
