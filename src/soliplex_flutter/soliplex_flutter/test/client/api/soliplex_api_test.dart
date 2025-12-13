import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:soliplex_flutter/client/api/soliplex_api.dart';
import 'package:soliplex_flutter/client/utils/http_transport.dart';
import 'package:test/test.dart';

void main() {
  group('SoliplexApi', () {
    test('creates with base URL', () {
      final api = SoliplexApi(baseUrl: 'https://api.example.com');

      expect(api.urlBuilder, isNotNull);
    });

    test('creates with headers', () {
      final api = SoliplexApi(
        baseUrl: 'https://api.example.com',
        headers: {'Authorization': 'Bearer token'},
      );

      expect(api, isNotNull);
    });

    group('getRooms', () {
      test('fetches and parses rooms from map response', () async {
        // API returns rooms as a map with room IDs as keys
        final mockClient = MockClient((request) async {
          expect(request.url.path, contains('/rooms'));
          return http.Response(
            '{"room1": {"id": "room1", "name": "Room 1"}, "room2": {"id": "room2", "name": "Room 2"}}',
            200,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final rooms = await api.getRooms();

        expect(rooms, hasLength(2));
        expect(rooms.map((r) => r.id).toSet(), equals({'room1', 'room2'}));
      });

      test('throws on error response', () async {
        final mockClient = MockClient((request) async {
          return http.Response('{"error": "Unauthorized"}', 401);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        expect(() => api.getRooms(), throwsA(isA<HttpException>()));
      });
    });

    group('getRoom', () {
      test('fetches and parses room', () async {
        final mockClient = MockClient((request) async {
          expect(request.url.path, contains('/rooms/room1'));
          return http.Response(
            '{"id": "room1", "name": "Test Room"}',
            200,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final room = await api.getRoom('room1');

        expect(room.id, equals('room1'));
        expect(room.name, equals('Test Room'));
      });
    });

    group('getThreads', () {
      test('parses threads from wrapped response', () async {
        // Real API returns threads wrapped in {"threads": [...]}
        final mockClient = MockClient((request) async {
          expect(request.url.path, contains('/rooms/room1/agui'));
          return http.Response(
            '{"threads": [{"id": "t1", "room_id": "room1", "name": "Thread 1"}]}',
            200,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final threads = await api.getThreads('room1');

        expect(threads, hasLength(1));
        expect(threads[0].id, equals('t1'));
        expect(threads[0].roomId, equals('room1'));
      });
    });

    group('getThread', () {
      test('fetches and parses thread', () async {
        final mockClient = MockClient((request) async {
          expect(request.url.path, contains('/rooms/room1/agui/t1'));
          return http.Response(
            '{"id": "t1", "room_id": "room1", "name": "Thread 1"}',
            200,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final thread = await api.getThread('room1', 't1');

        expect(thread.id, equals('t1'));
        expect(thread.roomId, equals('room1'));
      });
    });

    group('createThread', () {
      test('creates thread and returns result', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('POST'));
          expect(request.url.path, contains('/rooms/room1/agui'));
          return http.Response(
            '{"thread_id": "t1", "run_id": "r1"}',
            201,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final result = await api.createThread('room1');

        expect(result['thread_id'], equals('t1'));
        expect(result['run_id'], equals('r1'));
      });

      test('sends empty JSON body (required by API)', () async {
        String? requestBody;
        final mockClient = MockClient((request) async {
          requestBody = request.body;
          return http.Response('{"thread_id": "t1", "run_id": "r1"}', 201);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        await api.createThread('room1');

        expect(requestBody, isNotNull);
        expect(requestBody, isNotEmpty);
      });
    });

    group('deleteThread', () {
      test('deletes thread', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('DELETE'));
          expect(request.url.path, contains('/rooms/room1/agui/t1'));
          return http.Response('', 204);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        await api.deleteThread('room1', 't1');
        // No exception means success
      });
    });

    group('setThreadMeta', () {
      test('sets thread metadata with name', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('POST'));
          expect(request.url.path, contains('/rooms/room1/agui/t1/meta'));
          expect(request.body, contains('name'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        await api.setThreadMeta('room1', 't1', name: 'New Name');
      });

      test('sets thread metadata with description', () async {
        final mockClient = MockClient((request) async {
          expect(request.body, contains('description'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        await api.setThreadMeta('room1', 't1', description: 'New Description');
      });
    });

    group('getRun', () {
      test('fetches and parses run', () async {
        final mockClient = MockClient((request) async {
          expect(request.url.path, contains('/rooms/room1/agui/t1/r1'));
          return http.Response(
            '{"id": "r1", "thread_id": "t1", "status": "completed"}',
            200,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final run = await api.getRun('room1', 't1', 'r1');

        expect(run.id, equals('r1'));
        expect(run.threadId, equals('t1'));
      });
    });

    group('createRun', () {
      test('creates run and returns result', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('POST'));
          return http.Response(
            '{"run_id": "r1"}',
            201,
          );
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        final result = await api.createRun('room1', 't1');

        expect(result['run_id'], equals('r1'));
      });

      test('sends empty JSON body (required by API)', () async {
        String? requestBody;
        final mockClient = MockClient((request) async {
          requestBody = request.body;
          return http.Response('{"run_id": "r1"}', 201);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        await api.createRun('room1', 't1');

        expect(requestBody, isNotNull);
        expect(requestBody, isNotEmpty);
      });
    });

    group('setRunMeta', () {
      test('sets run metadata with label', () async {
        final mockClient = MockClient((request) async {
          expect(request.method, equals('POST'));
          expect(request.url.path, contains('/meta'));
          expect(request.body, contains('label'));
          return http.Response('{}', 200);
        });

        final transport = HttpTransport(
          baseUrl: 'https://example.com',
          client: mockClient,
        );
        final api = SoliplexApi(
          baseUrl: 'https://example.com',
          transport: transport,
        );

        await api.setRunMeta('room1', 't1', 'r1', label: 'My Run');
      });
    });

    test('close closes the transport', () {
      final api = SoliplexApi(baseUrl: 'https://example.com');

      // Should not throw
      api.close();
    });
  });
}
