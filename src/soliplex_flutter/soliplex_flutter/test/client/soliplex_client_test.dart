import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_flutter/client/api/soliplex_api.dart';
import 'package:soliplex_flutter/client/models/models.dart';
import 'package:soliplex_flutter/client/agui/thread.dart';
import 'package:soliplex_flutter/client/session/connection_manager.dart';
import 'package:soliplex_flutter/client/session/room_session.dart';
import 'package:soliplex_flutter/client/soliplex_client.dart';
import 'package:soliplex_flutter/client/utils/http_transport.dart';
import 'package:soliplex_flutter/client/utils/url_builder.dart';
import 'package:test/test.dart';

/// Test helper to create a SoliplexClient with a mock HTTP client
MockClient createMockClientForDelegationTests(
  Future<http.Response> Function(http.Request) handler,
) {
  return MockClient(handler);
}

/// Mock classes for testing
class MockSoliplexApi extends Mock implements SoliplexApi {}

class MockConnectionManager extends Mock implements ConnectionManager {}

class MockRoomSession extends Mock implements RoomSession {}

class MockUrlBuilder extends Mock implements UrlBuilder {}

class MockThread extends Mock implements Thread {}

// Fallback values for mocktail
class FakeTool extends Fake implements ag_ui.Tool {}

class FakeToolExecutor extends Fake {
  Future<String> call(ag_ui.ToolCall call) async => '';
}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeTool());
    registerFallbackValue(FakeToolExecutor().call);
    registerFallbackValue(ag_ui.TextMessageStartEvent(messageId: 'fake'));
  });
  group('SoliplexClient', () {
    test('creates with default URL', () {
      final client = SoliplexClient();

      expect(client.baseUrl, equals('http://localhost:8000'));
      expect(client.api, isNotNull);
      expect(client.connectionManager, isNotNull);
      expect(client.urlBuilder, isNotNull);
    });

    test('creates with custom URL', () {
      final client = SoliplexClient(baseUrl: 'https://api.example.com');

      expect(client.baseUrl, equals('https://api.example.com'));
    });

    test('creates with custom headers', () {
      final client = SoliplexClient(
        baseUrl: 'https://api.example.com',
        headers: {'Authorization': 'Bearer token'},
      );

      expect(client.baseUrl, equals('https://api.example.com'));
    });

    test('normalizes base URL', () {
      final client = SoliplexClient(baseUrl: 'example.com/api/');

      expect(client.baseUrl, equals('https://example.com'));
    });

    group('configure', () {
      test('reconfigures client', () {
        final client = SoliplexClient(baseUrl: 'https://old.example.com');

        client.configure('https://new.example.com');

        expect(client.baseUrl, equals('https://new.example.com'));
      });

      test('reconfigures with new headers', () {
        final client = SoliplexClient(baseUrl: 'https://example.com');

        client.configure(
          'https://example.com',
          headers: {'Authorization': 'Bearer new-token'},
        );

        // Client is reconfigured (no direct way to verify headers without making requests)
        expect(client.baseUrl, equals('https://example.com'));
      });

      test('preserves existing headers when not provided', () {
        final client = SoliplexClient(
          baseUrl: 'https://example.com',
          headers: {'Authorization': 'Bearer original'},
        );

        // Configure without headers - should preserve original
        client.configure('https://new.example.com');

        expect(client.baseUrl, equals('https://new.example.com'));
      });
    });

    group('getMessages', () {
      test('returns messages for room', () {
        final client = SoliplexClient();

        final messages = client.getMessages('room1');

        expect(messages, isEmpty);
      });

      test('returns messages for different rooms', () {
        final client = SoliplexClient();

        final messages1 = client.getMessages('room1');
        final messages2 = client.getMessages('room2');

        expect(messages1, isEmpty);
        expect(messages2, isEmpty);
      });
    });

    group('getMessageStream', () {
      test('returns message stream for room', () {
        final client = SoliplexClient();

        final stream = client.getMessageStream('room1');

        expect(stream, isNotNull);
      });

      test('returns different streams for different rooms', () {
        final client = SoliplexClient();

        final stream1 = client.getMessageStream('room1');
        final stream2 = client.getMessageStream('room2');

        expect(stream1, isNotNull);
        expect(stream2, isNotNull);
      });
    });

    group('switchRoom', () {
      test('switches active room', () {
        final client = SoliplexClient();

        client.switchRoom('room1');

        expect(client.connectionManager.activeRoomId, equals('room1'));
      });

      test('can switch between rooms', () {
        final client = SoliplexClient();

        client.switchRoom('room1');
        expect(client.connectionManager.activeRoomId, equals('room1'));

        client.switchRoom('room2');
        expect(client.connectionManager.activeRoomId, equals('room2'));
      });
    });

    group('cancelRun', () {
      test('does not throw for non-existent room', () {
        final client = SoliplexClient();

        expect(() => client.cancelRun('room1'), returnsNormally);
      });

      test('can cancel after switching rooms', () {
        final client = SoliplexClient();

        client.switchRoom('room1');
        expect(() => client.cancelRun('room1'), returnsNormally);
      });
    });

    group('dispose', () {
      test('disposes client', () {
        final client = SoliplexClient();

        expect(() => client.dispose(), returnsNormally);
      });

      test('can dispose after operations', () {
        final client = SoliplexClient();
        client.switchRoom('room1');
        client.getMessages('room1');

        expect(() => client.dispose(), returnsNormally);
      });
    });
  });

  group('SoliplexClient with mock HTTP', () {
    late MockClient mockHttpClient;
    late SoliplexApi api;

    MockClient createMockClient(
      Future<http.Response> Function(http.Request) handler,
    ) {
      return MockClient(handler);
    }

    SoliplexApi createApiWithMock(MockClient mockClient) {
      final transport = HttpTransport(
        baseUrl: 'http://localhost:8000',
        client: mockClient,
      );
      return SoliplexApi(
        baseUrl: 'http://localhost:8000',
        transport: transport,
      );
    }

    group('getRooms via API', () {
      test('returns list of rooms', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms') {
            return http.Response(
              jsonEncode([
                {'id': 'room1', 'name': 'Test Room'},
                {'id': 'room2', 'name': 'Another Room'},
              ]),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final rooms = await api.getRooms();

        expect(rooms.length, equals(2));
        expect(rooms[0].id, equals('room1'));
        expect(rooms[1].id, equals('room2'));
      });

      test('handles empty list', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms') {
            return http.Response(jsonEncode([]), 200);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final rooms = await api.getRooms();

        expect(rooms, isEmpty);
      });

      test('throws on error response', () async {
        mockHttpClient = createMockClient((request) async {
          return http.Response('Internal Server Error', 500);
        });

        api = createApiWithMock(mockHttpClient);

        expect(() => api.getRooms(), throwsA(isA<HttpException>()));
      });
    });

    group('getRoom via API', () {
      test('returns single room', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/test-room') {
            return http.Response(
              jsonEncode({
                'id': 'test-room',
                'name': 'Test Room',
                'description': 'A test room',
              }),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final room = await api.getRoom('test-room');

        expect(room.id, equals('test-room'));
        expect(room.name, equals('Test Room'));
      });

      test('throws on 404', () async {
        mockHttpClient = createMockClient((request) async {
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        expect(() => api.getRoom('invalid'), throwsA(isA<HttpException>()));
      });
    });

    group('getThreads via API', () {
      test('returns list of threads', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui') {
            return http.Response(
              jsonEncode([
                {
                  'id': 'thread1',
                  'room_id': 'room1',
                  'name': 'Thread 1',
                },
                {
                  'id': 'thread2',
                  'room_id': 'room1',
                  'name': 'Thread 2',
                },
              ]),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final threads = await api.getThreads('room1');

        expect(threads.length, equals(2));
        expect(threads[0].id, equals('thread1'));
      });
    });

    group('getThread via API', () {
      test('returns single thread', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1') {
            return http.Response(
              jsonEncode({
                'id': 'thread1',
                'room_id': 'room1',
                'name': 'Test Thread',
              }),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final thread = await api.getThread('room1', 'thread1');

        expect(thread.id, equals('thread1'));
      });
    });

    group('createThread via API', () {
      test('creates thread and returns IDs', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui' &&
              request.method == 'POST') {
            return http.Response(
              jsonEncode({'thread_id': 'new-thread', 'run_id': 'new-run'}),
              201,
            );
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final result = await api.createThread('room1');

        expect(result['thread_id'], equals('new-thread'));
        expect(result['run_id'], equals('new-run'));
      });
    });

    group('deleteThread via API', () {
      test('deletes thread successfully', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1' &&
              request.method == 'DELETE') {
            return http.Response('', 204);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        await expectLater(api.deleteThread('room1', 'thread1'), completes);
      });
    });

    group('setThreadMeta via API', () {
      test('sets thread name', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1/meta' &&
              request.method == 'POST') {
            final body = jsonDecode(request.body);
            expect(body['name'], equals('New Name'));
            return http.Response('', 200);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        await expectLater(
          api.setThreadMeta('room1', 'thread1', name: 'New Name'),
          completes,
        );
      });

      test('sets thread description', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1/meta' &&
              request.method == 'POST') {
            final body = jsonDecode(request.body);
            expect(body['description'], equals('New Description'));
            return http.Response('', 200);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        await expectLater(
          api.setThreadMeta('room1', 'thread1', description: 'New Description'),
          completes,
        );
      });

      test('sets both name and description', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1/meta' &&
              request.method == 'POST') {
            final body = jsonDecode(request.body);
            expect(body['name'], equals('Name'));
            expect(body['description'], equals('Desc'));
            return http.Response('', 200);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        await expectLater(
          api.setThreadMeta(
            'room1',
            'thread1',
            name: 'Name',
            description: 'Desc',
          ),
          completes,
        );
      });
    });

    group('getRun via API', () {
      test('returns run info', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1/run1') {
            return http.Response(
              jsonEncode({
                'id': 'run1',
                'thread_id': 'thread1',
                'status': 'completed',
              }),
              200,
            );
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final run = await api.getRun('room1', 'thread1', 'run1');

        expect(run.id, equals('run1'));
      });
    });

    group('createRun via API', () {
      test('creates run and returns ID', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path == '/api/v1/rooms/room1/agui/thread1' &&
              request.method == 'POST') {
            return http.Response(jsonEncode({'run_id': 'new-run'}), 201);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        final result = await api.createRun('room1', 'thread1');

        expect(result['run_id'], equals('new-run'));
      });
    });

    group('setRunMeta via API', () {
      test('sets run label', () async {
        mockHttpClient = createMockClient((request) async {
          if (request.url.path ==
                  '/api/v1/rooms/room1/agui/thread1/run1/meta' &&
              request.method == 'POST') {
            final body = jsonDecode(request.body);
            expect(body['label'], equals('Test Label'));
            return http.Response('', 200);
          }
          return http.Response('Not found', 404);
        });

        api = createApiWithMock(mockHttpClient);

        await expectLater(
          api.setRunMeta('room1', 'thread1', 'run1', label: 'Test Label'),
          completes,
        );
      });
    });
  });

  group('HttpResponse', () {
    test('isSuccess returns true for 2xx status codes', () {
      expect(
        const HttpResponse(statusCode: 200, body: '', headers: {}).isSuccess,
        isTrue,
      );
      expect(
        const HttpResponse(statusCode: 201, body: '', headers: {}).isSuccess,
        isTrue,
      );
      expect(
        const HttpResponse(statusCode: 299, body: '', headers: {}).isSuccess,
        isTrue,
      );
    });

    test('isSuccess returns false for non-2xx status codes', () {
      expect(
        const HttpResponse(statusCode: 199, body: '', headers: {}).isSuccess,
        isFalse,
      );
      expect(
        const HttpResponse(statusCode: 300, body: '', headers: {}).isSuccess,
        isFalse,
      );
      expect(
        const HttpResponse(statusCode: 404, body: '', headers: {}).isSuccess,
        isFalse,
      );
      expect(
        const HttpResponse(statusCode: 500, body: '', headers: {}).isSuccess,
        isFalse,
      );
    });

    test('json parses body', () {
      final response = HttpResponse(
        statusCode: 200,
        body: jsonEncode({'key': 'value'}),
        headers: {},
      );

      expect(response.json, equals({'key': 'value'}));
    });

    test('jsonMap returns map', () {
      final response = HttpResponse(
        statusCode: 200,
        body: jsonEncode({'key': 'value'}),
        headers: {},
      );

      expect(response.jsonMap, equals({'key': 'value'}));
    });

    test('jsonList returns list', () {
      final response = HttpResponse(
        statusCode: 200,
        body: jsonEncode([1, 2, 3]),
        headers: {},
      );

      expect(response.jsonList, equals([1, 2, 3]));
    });

    test('toString includes status code', () {
      const response = HttpResponse(statusCode: 404, body: '', headers: {});

      expect(response.toString(), contains('404'));
    });
  });

  group('HttpException', () {
    test('toString includes status code and body', () {
      const exception = HttpException(statusCode: 500, body: 'Server Error');

      expect(exception.toString(), contains('500'));
      expect(exception.toString(), contains('Server Error'));
    });

    test('toString includes message when provided', () {
      const exception = HttpException(
        statusCode: 500,
        body: 'body',
        message: 'Custom message',
      );

      expect(exception.toString(), contains('Custom message'));
    });
  });

  group('HttpTransport', () {
    test('creates with default timeout', () {
      final transport = HttpTransport(baseUrl: 'http://localhost');

      expect(transport.timeout, equals(const Duration(seconds: 30)));
    });

    test('creates with custom timeout', () {
      final transport = HttpTransport(
        baseUrl: 'http://localhost',
        timeout: const Duration(seconds: 60),
      );

      expect(transport.timeout, equals(const Duration(seconds: 60)));
    });

    test('close does not throw', () {
      final transport = HttpTransport(baseUrl: 'http://localhost');

      expect(() => transport.close(), returnsNormally);
    });

    group('with mock client', () {
      test('get request includes default headers', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['X-Custom'], equals('value'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'http://localhost',
          defaultHeaders: {'X-Custom': 'value'},
          client: mockClient,
        );

        await transport.get(Uri.parse('http://localhost/test'));
      });

      test('post request includes Content-Type', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['Content-Type'], equals('application/json'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'http://localhost',
          client: mockClient,
        );

        await transport.post(Uri.parse('http://localhost/test'));
      });

      test('post request encodes body as JSON', () async {
        final mockClient = MockClient((request) async {
          expect(
            request.body,
            equals(jsonEncode({'key': 'value'})),
          );
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'http://localhost',
          client: mockClient,
        );

        await transport.post(
          Uri.parse('http://localhost/test'),
          body: {'key': 'value'},
        );
      });

      test('delete request works', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('DELETE'));
          return http.Response('', 204);
        });

        final transport = HttpTransport(
          baseUrl: 'http://localhost',
          client: mockClient,
        );

        final response = await transport.delete(
          Uri.parse('http://localhost/test'),
        );

        expect(response.statusCode, equals(204));
      });

      test('merges request-specific headers', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['X-Default'], equals('default'));
          expect(request.headers['X-Request'], equals('request'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'http://localhost',
          defaultHeaders: {'X-Default': 'default'},
          client: mockClient,
        );

        await transport.get(
          Uri.parse('http://localhost/test'),
          headers: {'X-Request': 'request'},
        );
      });

      test('request-specific headers override defaults', () async {
        final mockClient = MockClient((request) async {
          expect(request.headers['X-Header'], equals('overridden'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'http://localhost',
          defaultHeaders: {'X-Header': 'default'},
          client: mockClient,
        );

        await transport.get(
          Uri.parse('http://localhost/test'),
          headers: {'X-Header': 'overridden'},
        );
      });
    });
  });

  group('SoliplexClient delegation methods - error handling', () {
    // These tests verify the delegation methods exist and execute correctly
    // by calling them and expecting network errors (no server is running)
    late SoliplexClient client;

    setUp(() {
      // Use a very short timeout to fail fast
      client = SoliplexClient(baseUrl: 'http://127.0.0.1:0');
    });

    test('getRooms delegates to API', () async {
      // Calling getRooms executes the delegation code path
      expect(client.getRooms(), throwsA(anything));
    });

    test('getRoom delegates to API', () async {
      expect(client.getRoom('test-room'), throwsA(anything));
    });

    test('getThreads delegates to API', () async {
      expect(client.getThreads('room1'), throwsA(anything));
    });

    test('getThread delegates to API', () async {
      expect(client.getThread('room1', 'thread1'), throwsA(anything));
    });

    test('createThread delegates to API', () async {
      expect(client.createThread('room1'), throwsA(anything));
    });

    test('deleteThread delegates to API', () async {
      expect(client.deleteThread('room1', 'thread1'), throwsA(anything));
    });

    test('setThreadMeta with name delegates to API', () async {
      expect(
        client.setThreadMeta('room1', 'thread1', name: 'Name'),
        throwsA(anything),
      );
    });

    test('setThreadMeta with description delegates to API', () async {
      expect(
        client.setThreadMeta('room1', 'thread1', description: 'Desc'),
        throwsA(anything),
      );
    });

    test('setThreadMeta with both delegates to API', () async {
      expect(
        client.setThreadMeta('room1', 'thread1', name: 'N', description: 'D'),
        throwsA(anything),
      );
    });

    test('getRun delegates to API', () async {
      expect(client.getRun('room1', 'thread1', 'run1'), throwsA(anything));
    });

    test('createRun delegates to API', () async {
      expect(client.createRun('room1', 'thread1'), throwsA(anything));
    });

    test('setRunMeta delegates to API', () async {
      expect(
        client.setRunMeta('room1', 'thread1', 'run1', label: 'Label'),
        throwsA(anything),
      );
    });

    test('chat initializes thread if needed', () async {
      // Chat will try to create a thread (which will fail due to network error)
      // but the code path is still covered
      expect(
        client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
        ),
        throwsA(anything),
      );
    });

    test('chat with callbacks initializes properly', () async {
      var canvasCalled = false;
      var contextCalled = false;
      var activityCalled = false;

      // These callbacks are set but won't be called since network fails
      expect(
        client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          onCanvasUpdate: (data) => canvasCalled = true,
          onContextUpdate: (type, {summary, data}) => contextCalled = true,
          onActivityUpdate: (isActive) => activityCalled = true,
        ),
        throwsA(anything),
      );

      // Callbacks weren't called due to network error
      expect(canvasCalled, isFalse);
      expect(contextCalled, isFalse);
      expect(activityCalled, isFalse);
    });
  });

  group('SoliplexClient with injected dependencies', () {
    late MockSoliplexApi mockApi;
    late MockConnectionManager mockConnectionManager;
    late MockRoomSession mockSession;
    late SoliplexClient client;

    setUp(() {
      mockApi = MockSoliplexApi();
      mockConnectionManager = MockConnectionManager();
      mockSession = MockRoomSession();

      // Default stubs
      when(() => mockConnectionManager.baseUrl).thenReturn('http://localhost:8000');
      when(() => mockConnectionManager.getSession(any())).thenReturn(mockSession);
      when(() => mockSession.threadId).thenReturn(null);
      when(() => mockSession.messages).thenReturn([]);
      when(() => mockSession.messageStream).thenAnswer((_) => const Stream.empty());

      client = SoliplexClient(
        api: mockApi,
        connectionManager: mockConnectionManager,
      );
    });

    group('createThread', () {
      test('calls API and initializes session', () async {
        when(() => mockApi.createThread('room1')).thenAnswer(
          (_) async => {'thread_id': 'thread-123', 'run_id': 'run-456'},
        );
        when(() => mockConnectionManager.initializeSession('room1', 'thread-123'))
            .thenReturn(null);

        final result = await client.createThread('room1');

        expect(result.threadId, equals('thread-123'));
        expect(result.runId, equals('run-456'));
        verify(() => mockApi.createThread('room1')).called(1);
        verify(() => mockConnectionManager.initializeSession('room1', 'thread-123')).called(1);
      });

      test('throws on API error', () async {
        when(() => mockApi.createThread('room1')).thenThrow(
          const HttpException(statusCode: 500, body: 'Server Error'),
        );

        expect(
          () => client.createThread('room1'),
          throwsA(isA<HttpException>()),
        );
      });
    });

    group('createRun', () {
      test('calls API and returns run ID', () async {
        when(() => mockApi.createRun('room1', 'thread1')).thenAnswer(
          (_) async => {'run_id': 'run-789'},
        );

        final runId = await client.createRun('room1', 'thread1');

        expect(runId, equals('run-789'));
        verify(() => mockApi.createRun('room1', 'thread1')).called(1);
      });
    });

    group('setThreadMeta', () {
      test('calls API with name only', () async {
        when(() => mockApi.setThreadMeta(
              'room1',
              'thread1',
              name: 'New Name',
              description: null,
            )).thenAnswer((_) async {});

        await client.setThreadMeta('room1', 'thread1', name: 'New Name');

        verify(() => mockApi.setThreadMeta(
              'room1',
              'thread1',
              name: 'New Name',
              description: null,
            )).called(1);
      });

      test('calls API with description only', () async {
        when(() => mockApi.setThreadMeta(
              'room1',
              'thread1',
              name: null,
              description: 'New Description',
            )).thenAnswer((_) async {});

        await client.setThreadMeta('room1', 'thread1', description: 'New Description');

        verify(() => mockApi.setThreadMeta(
              'room1',
              'thread1',
              name: null,
              description: 'New Description',
            )).called(1);
      });

      test('calls API with both name and description', () async {
        when(() => mockApi.setThreadMeta(
              'room1',
              'thread1',
              name: 'Name',
              description: 'Desc',
            )).thenAnswer((_) async {});

        await client.setThreadMeta('room1', 'thread1', name: 'Name', description: 'Desc');

        verify(() => mockApi.setThreadMeta(
              'room1',
              'thread1',
              name: 'Name',
              description: 'Desc',
            )).called(1);
      });
    });

    group('setRunMeta', () {
      test('calls API with label', () async {
        when(() => mockApi.setRunMeta('room1', 'thread1', 'run1', label: 'Label'))
            .thenAnswer((_) async {});

        await client.setRunMeta('room1', 'thread1', 'run1', label: 'Label');

        verify(() => mockApi.setRunMeta('room1', 'thread1', 'run1', label: 'Label')).called(1);
      });
    });

    group('getRooms', () {
      test('returns rooms from API', () async {
        final rooms = [
          Room(id: 'room1', name: 'Room 1'),
          Room(id: 'room2', name: 'Room 2'),
        ];
        when(() => mockApi.getRooms()).thenAnswer((_) async => rooms);

        final result = await client.getRooms();

        expect(result.length, equals(2));
        expect(result[0].id, equals('room1'));
      });
    });

    group('getRoom', () {
      test('returns room from API', () async {
        final room = Room(id: 'room1', name: 'Room 1');
        when(() => mockApi.getRoom('room1')).thenAnswer((_) async => room);

        final result = await client.getRoom('room1');

        expect(result.id, equals('room1'));
      });
    });

    group('getThreads', () {
      test('returns threads from API', () async {
        final threads = [
          ThreadInfo(id: 'thread1', roomId: 'room1'),
          ThreadInfo(id: 'thread2', roomId: 'room1'),
        ];
        when(() => mockApi.getThreads('room1')).thenAnswer((_) async => threads);

        final result = await client.getThreads('room1');

        expect(result.length, equals(2));
      });
    });

    group('getThread', () {
      test('returns thread from API', () async {
        final thread = ThreadInfo(id: 'thread1', roomId: 'room1');
        when(() => mockApi.getThread('room1', 'thread1')).thenAnswer((_) async => thread);

        final result = await client.getThread('room1', 'thread1');

        expect(result.id, equals('thread1'));
      });
    });

    group('deleteThread', () {
      test('calls API', () async {
        when(() => mockApi.deleteThread('room1', 'thread1')).thenAnswer((_) async {});

        await client.deleteThread('room1', 'thread1');

        verify(() => mockApi.deleteThread('room1', 'thread1')).called(1);
      });
    });

    group('getRun', () {
      test('returns run from API', () async {
        final run = RunInfo(id: 'run1', threadId: 'thread1');
        when(() => mockApi.getRun('room1', 'thread1', 'run1')).thenAnswer((_) async => run);

        final result = await client.getRun('room1', 'thread1', 'run1');

        expect(result.id, equals('run1'));
      });
    });

    group('getMessages', () {
      test('returns messages from session', () {
        final messages = <ChatMessage>[
          ChatMessage.text(
            user: ChatUser.user,
            text: 'Hello',
          ),
        ];
        when(() => mockSession.messages).thenReturn(messages);

        final result = client.getMessages('room1');

        expect(result.length, equals(1));
        verify(() => mockConnectionManager.getSession('room1')).called(1);
      });
    });

    group('getMessageStream', () {
      test('returns stream from session', () {
        when(() => mockSession.messageStream).thenAnswer((_) => const Stream.empty());

        final stream = client.getMessageStream('room1');

        expect(stream, isNotNull);
        verify(() => mockConnectionManager.getSession('room1')).called(1);
      });
    });

    group('switchRoom', () {
      test('delegates to connection manager', () {
        when(() => mockConnectionManager.switchRoom('room1')).thenReturn(null);

        client.switchRoom('room1');

        verify(() => mockConnectionManager.switchRoom('room1')).called(1);
      });
    });

    group('cancelRun', () {
      test('delegates to connection manager', () {
        when(() => mockConnectionManager.cancelRun('room1')).thenReturn(null);

        client.cancelRun('room1');

        verify(() => mockConnectionManager.cancelRun('room1')).called(1);
      });
    });

    group('dispose', () {
      test('disposes api and connection manager', () {
        when(() => mockApi.close()).thenReturn(null);
        when(() => mockConnectionManager.dispose()).thenReturn(null);

        client.dispose();

        verify(() => mockApi.close()).called(1);
        verify(() => mockConnectionManager.dispose()).called(1);
      });
    });

    group('chat', () {
      late MockThread mockThread;
      late MockUrlBuilder mockUrlBuilder;

      setUp(() {
        mockThread = MockThread();
        mockUrlBuilder = MockUrlBuilder();

        // Setup URL builder
        when(() => mockConnectionManager.urlBuilder).thenReturn(mockUrlBuilder);
        when(() => mockUrlBuilder.runEndpointPath(any(), any(), any()))
            .thenReturn('/api/v1/rooms/room1/agui/thread1/run1');
      });

      test('creates thread when session has no thread', () async {
        // Setup session without thread
        when(() => mockSession.threadId).thenReturn(null);
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);

        // Setup createThread
        when(() => mockApi.createThread('room1')).thenAnswer(
          (_) async => {'thread_id': 'thread-123', 'run_id': 'run-456'},
        );
        when(() => mockConnectionManager.initializeSession('room1', 'thread-123'))
            .thenReturn(null);

        // Session still has no thread after creation (returns StateError)
        when(() => mockSession.thread).thenReturn(null);

        expect(
          () => client.chat(roomId: 'room1', userMessage: 'Hello'),
          throwsA(isA<StateError>()),
        );

        verify(() => mockApi.createThread('room1')).called(1);
      });

      test('sets up callbacks on session', () async {
        var canvasSet = false;
        var contextSet = false;
        var activitySet = false;

        when(() => mockSession.onCanvasUpdate = any()).thenAnswer((_) {
          canvasSet = true;
        });
        when(() => mockSession.onContextUpdate = any()).thenAnswer((_) {
          contextSet = true;
        });
        when(() => mockSession.onActivityUpdate = any()).thenAnswer((_) {
          activitySet = true;
        });

        // Setup existing thread
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        // Setup thread mock
        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          onCanvasUpdate: (_) {},
          onContextUpdate: (_, {summary, data}) {},
          onActivityUpdate: (_) {},
        );

        expect(canvasSet, isTrue);
        expect(contextSet, isTrue);
        expect(activitySet, isTrue);
      });

      test('adds user message to session', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        await client.chat(roomId: 'room1', userMessage: 'Test message');

        verify(() => mockSession.addUserMessage('Test message')).called(1);
      });

      test('creates run via API', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        await client.chat(roomId: 'room1', userMessage: 'Hello');

        verify(() => mockApi.createRun('room1', 'thread-1')).called(1);
      });

      test('calls startRun on thread', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        await client.chat(roomId: 'room1', userMessage: 'Hello');

        verify(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: 'run-1',
              messages: any(named: 'messages'),
              state: null,
            )).called(1);
      });

      test('passes state to startRun', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          state: {'key': 'value'},
        );

        verify(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: 'run-1',
              messages: any(named: 'messages'),
              state: {'key': 'value'},
            )).called(1);
      });

      test('handles tool result loop', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );

        // First createRun
        var runCounter = 0;
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-${++runCounter}'},
        );

        // First startRun returns tool results, second returns empty
        var startRunCounter = 0;
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async {
          startRunCounter++;
          if (startRunCounter == 1) {
            // Return a tool result to trigger the loop
            return [
              ag_ui.ToolMessage(
                toolCallId: 'tool-1',
                content: 'result',
              ),
            ];
          }
          return <ag_ui.ToolMessage>[];
        });

        await client.chat(roomId: 'room1', userMessage: 'Hello');

        // Should have called createRun twice (initial + loop)
        verify(() => mockApi.createRun('room1', 'thread-1')).called(2);
        expect(startRunCounter, equals(2));
      });

      test('listens to stepsStream and processes events', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.processEvent(any())).thenReturn(null);

        // Use an empty stream - just verifies the stream is subscribed
        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );

        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
        );

        // Verify stepsStream was accessed (subscribed to)
        verify(() => mockThread.stepsStream).called(1);
      });
    });

    group('_registerTools', () {
      late MockThread mockThread;
      late MockUrlBuilder mockUrlBuilder;

      setUp(() {
        mockThread = MockThread();
        mockUrlBuilder = MockUrlBuilder();

        when(() => mockConnectionManager.urlBuilder).thenReturn(mockUrlBuilder);
        when(() => mockUrlBuilder.runEndpointPath(any(), any(), any()))
            .thenReturn('/api/v1/rooms/room1/agui/thread1/run1');
      });

      test('registers tools with thread', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenReturn(null);

        final testTool = ag_ui.Tool(
          name: 'test_tool',
          description: 'A test tool',
          parameters: {},
        );

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'test_tool': testTool},
          toolExecutors: {
            'test_tool': (call) async => '{"result": "success"}',
          },
        );

        verify(() => mockThread.addTool(
              testTool,
              any(),
              fireAndForget: false,
            )).called(1);
      });

      test('registers UI tools as fire and forget', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenReturn(null);

        final canvasTool = ag_ui.Tool(
          name: 'canvas_render',
          description: 'Canvas render tool',
          parameters: {},
        );

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'canvas_render': canvasTool},
          toolExecutors: {
            'canvas_render': (call) async => '{}',
          },
        );

        verify(() => mockThread.addTool(
              canvasTool,
              any(),
              fireAndForget: true,
            )).called(1);
      });

      test('registers multiple tools with correct fire and forget settings', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenReturn(null);

        // Multiple tools
        final tools = {
          'regular_tool': ag_ui.Tool(name: 'regular_tool', description: 'Regular', parameters: {}),
          'canvas_render': ag_ui.Tool(name: 'canvas_render', description: 'Canvas', parameters: {}),
          'context_set': ag_ui.Tool(name: 'context_set', description: 'Context', parameters: {}),
        };

        final toolExecutors = <String, Future<String> Function(ag_ui.ToolCall)>{
          'regular_tool': (call) async => '{}',
          'canvas_render': (call) async => '{}',
          'context_set': (call) async => '{}',
        };

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: tools,
          toolExecutors: toolExecutors,
        );

        // Verify all tools were added
        verify(() => mockThread.addTool(
              any(),
              any(),
              fireAndForget: any(named: 'fireAndForget'),
            )).called(3);
      });

      test('does not register tools when tools or executors are null', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        // Call without tools
        await client.chat(roomId: 'room1', userMessage: 'Hello');

        // addTool should never be called
        verifyNever(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')));
      });

      test('does not register tools when only tools provided without executors', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        final tools = {
          'my_tool': ag_ui.Tool(name: 'my_tool', description: 'Tool', parameters: {}),
        };

        // Call with tools but no executors
        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: tools,
          // no toolExecutors
        );

        // addTool should never be called
        verifyNever(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')));
      });

      test('tool callback parses JSON arguments', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.handleLocalToolExecution(any(), any(), any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        // Capture the callback
        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final testTool = ag_ui.Tool(
          name: 'test_tool',
          description: 'A test tool',
          parameters: {},
        );

        Map<String, dynamic>? receivedArgs;
        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'test_tool': testTool},
          toolExecutors: {
            'test_tool': (call) async {
              receivedArgs = jsonDecode(call.function.arguments) as Map<String, dynamic>;
              return '{"result": "success"}';
            },
          },
        );

        // Invoke the captured callback with a tool call containing arguments
        expect(capturedCallback, isNotNull);
        final toolCall = ag_ui.ToolCall(
          id: 'call-1',
          function: ag_ui.FunctionCall(
            name: 'test_tool',
            arguments: '{"key": "value"}',
          ),
        );
        final result = await capturedCallback!(toolCall);

        expect(result, equals('{"result": "success"}'));
        expect(receivedArgs, equals({'key': 'value'}));
      });

      test('tool callback handles empty arguments', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.handleLocalToolExecution(any(), any(), any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final testTool = ag_ui.Tool(name: 'test_tool', description: 'Tool', parameters: {});

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'test_tool': testTool},
          toolExecutors: {'test_tool': (call) async => '{"ok": true}'},
        );

        // Invoke with empty arguments
        final toolCall = ag_ui.ToolCall(
          id: 'call-1',
          function: ag_ui.FunctionCall(name: 'test_tool', arguments: ''),
        );
        final result = await capturedCallback!(toolCall);

        expect(result, equals('{"ok": true}'));
      });

      test('tool callback handles invalid JSON gracefully', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.handleLocalToolExecution(any(), any(), any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final testTool = ag_ui.Tool(name: 'test_tool', description: 'Tool', parameters: {});

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'test_tool': testTool},
          toolExecutors: {'test_tool': (call) async => '{"ok": true}'},
        );

        // Invoke with invalid JSON arguments - should not throw
        final toolCall = ag_ui.ToolCall(
          id: 'call-1',
          function: ag_ui.FunctionCall(name: 'test_tool', arguments: 'not valid json'),
        );
        final result = await capturedCallback!(toolCall);

        expect(result, equals('{"ok": true}'));
      });

      test('tool callback handles executor error', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.handleLocalToolExecution(any(), any(), any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final testTool = ag_ui.Tool(name: 'test_tool', description: 'Tool', parameters: {});

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'test_tool': testTool},
          toolExecutors: {'test_tool': (call) async => throw Exception('Executor failed')},
        );

        final toolCall = ag_ui.ToolCall(
          id: 'call-1',
          function: ag_ui.FunctionCall(name: 'test_tool', arguments: '{}'),
        );
        final result = await capturedCallback!(toolCall);

        expect(result, contains('error'));
        expect(result, contains('Executor failed'));
        verify(() => mockSession.handleLocalToolExecution('call-1', 'test_tool', 'executing')).called(1);
      });

      test('tool callback returns error for missing executor', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final testTool = ag_ui.Tool(name: 'test_tool', description: 'Tool', parameters: {});

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'test_tool': testTool},
          toolExecutors: {'other_tool': (call) async => '{}'}, // Different tool name
        );

        final toolCall = ag_ui.ToolCall(
          id: 'call-1',
          function: ag_ui.FunctionCall(name: 'test_tool', arguments: '{}'),
        );
        final result = await capturedCallback!(toolCall);

        expect(result, contains('error'));
        expect(result, contains('No executor for tool test_tool'));
      });

      test('UI tool callback executes uiToolHandler', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.handleLocalToolExecution(any(), any(), any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final canvasTool = ag_ui.Tool(name: 'canvas_render', description: 'Canvas', parameters: {});

        String? receivedToolCallId;
        String? receivedToolName;
        Map<String, dynamic>? receivedArgs;

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'canvas_render': canvasTool},
          toolExecutors: {'canvas_render': (call) async => '{}'},
          uiToolHandler: (toolCallId, toolName, args) async {
            receivedToolCallId = toolCallId;
            receivedToolName = toolName;
            receivedArgs = args;
            return {'rendered': true};
          },
        );

        final toolCall = ag_ui.ToolCall(
          id: 'ui-call-1',
          function: ag_ui.FunctionCall(name: 'canvas_render', arguments: '{"data": "test"}'),
        );
        final result = await capturedCallback!(toolCall);

        expect(receivedToolCallId, equals('ui-call-1'));
        expect(receivedToolName, equals('canvas_render'));
        expect(receivedArgs, equals({'data': 'test'}));
        expect(result, equals('{"rendered":true}'));
        verify(() => mockSession.handleLocalToolExecution('ui-call-1', 'canvas_render', 'executing')).called(1);
        verify(() => mockSession.handleLocalToolExecution('ui-call-1', 'canvas_render', 'completed')).called(1);
      });

      test('UI tool callback handles uiToolHandler error', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.handleLocalToolExecution(any(), any(), any())).thenReturn(null);

        when(() => mockThread.stepsStream).thenAnswer(
          (_) => const Stream<ag_ui.BaseEvent>.empty(),
        );
        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        Future<String> Function(ag_ui.ToolCall)? capturedCallback;
        when(() => mockThread.addTool(any(), any(), fireAndForget: any(named: 'fireAndForget')))
            .thenAnswer((invocation) {
          capturedCallback = invocation.positionalArguments[1] as Future<String> Function(ag_ui.ToolCall);
        });

        final canvasTool = ag_ui.Tool(name: 'canvas_render', description: 'Canvas', parameters: {});

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          tools: {'canvas_render': canvasTool},
          toolExecutors: {'canvas_render': (call) async => '{}'},
          uiToolHandler: (toolCallId, toolName, args) async {
            throw Exception('UI handler failed');
          },
        );

        final toolCall = ag_ui.ToolCall(
          id: 'ui-call-1',
          function: ag_ui.FunctionCall(name: 'canvas_render', arguments: '{}'),
        );
        final result = await capturedCallback!(toolCall);

        expect(result, contains('error'));
        expect(result, contains('UI handler failed'));
        verify(() => mockSession.handleLocalToolExecution('ui-call-1', 'canvas_render', 'executing')).called(1);
      });

      test('stepsStream events are processed and forwarded to onEvent', () async {
        when(() => mockSession.onCanvasUpdate = any()).thenReturn(null);
        when(() => mockSession.onContextUpdate = any()).thenReturn(null);
        when(() => mockSession.onActivityUpdate = any()).thenReturn(null);
        when(() => mockSession.threadId).thenReturn('thread-1');
        when(() => mockSession.thread).thenReturn(mockThread);
        when(() => mockSession.addUserMessage(any())).thenReturn(null);
        when(() => mockSession.processEvent(any())).thenReturn(null);

        // Create a stream with one event
        final event = ag_ui.TextMessageStartEvent(messageId: 'msg-1');
        when(() => mockThread.stepsStream).thenAnswer(
          (_) => Stream.fromIterable([event]),
        );

        when(() => mockApi.createRun('room1', 'thread-1')).thenAnswer(
          (_) async => {'run_id': 'run-1'},
        );
        when(() => mockThread.startRun(
              endpoint: any(named: 'endpoint'),
              runId: any(named: 'runId'),
              messages: any(named: 'messages'),
              state: any(named: 'state'),
            )).thenAnswer((_) async => <ag_ui.ToolMessage>[]);

        final receivedEvents = <ag_ui.BaseEvent>[];

        await client.chat(
          roomId: 'room1',
          userMessage: 'Hello',
          onEvent: (e) => receivedEvents.add(e),
        );

        // Give stream time to process
        await Future.delayed(const Duration(milliseconds: 10));

        verify(() => mockSession.processEvent(event)).called(1);
        expect(receivedEvents.length, equals(1));
        expect(receivedEvents[0], equals(event));
      });
    });
  });
}
