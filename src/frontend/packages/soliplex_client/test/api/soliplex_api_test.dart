import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockHttpTransport extends Mock implements HttpTransport {}

void main() {
  late MockHttpTransport mockTransport;
  late UrlBuilder urlBuilder;
  late SoliplexApi api;

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://example.com'));
    registerFallbackValue(CancelToken());
  });

  setUp(() {
    mockTransport = MockHttpTransport();
    urlBuilder = UrlBuilder('https://api.example.com/api/v1');
    api = SoliplexApi(transport: mockTransport, urlBuilder: urlBuilder);

    when(() => mockTransport.close()).thenReturn(null);
  });

  tearDown(() {
    api.close();
    reset(mockTransport);
  });

  group('SoliplexApi', () {
    group('constructor', () {
      test('creates with required dependencies', () {
        expect(api, isNotNull);
      });
    });

    group('close', () {
      test('delegates to transport', () {
        api.close();

        verify(() => mockTransport.close()).called(1);
      });
    });

    // ============================================================
    // Rooms
    // ============================================================

    group('getRooms', () {
      test('returns list of rooms', () async {
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => [
            {'id': 'room-1', 'name': 'Room 1'},
            {'id': 'room-2', 'name': 'Room 2'},
          ],
        );

        final rooms = await api.getRooms();

        expect(rooms.length, equals(2));
        expect(rooms[0].id, equals('room-1'));
        expect(rooms[0].name, equals('Room 1'));
        expect(rooms[1].id, equals('room-2'));
        expect(rooms[1].name, equals('Room 2'));
      });

      test('returns empty list when no rooms', () async {
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => <dynamic>[]);

        final rooms = await api.getRooms();

        expect(rooms, isEmpty);
      });

      test('propagates exceptions', () async {
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(const AuthException(message: 'Unauthorized'));

        expect(
          () => api.getRooms(),
          throwsA(isA<AuthException>()),
        );
      });

      test('supports cancellation', () async {
        final cancelToken = CancelToken();

        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => <dynamic>[]);

        await api.getRooms(cancelToken: cancelToken);

        verify(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return <dynamic>[];
        });

        await api.getRooms();

        expect(capturedUri?.path, equals('/api/v1/rooms'));
      });
    });

    group('getRoom', () {
      test('returns room by ID', () async {
        when(
          () => mockTransport.request<Room>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => const Room(id: 'room-123', name: 'Test Room'),
        );

        final room = await api.getRoom('room-123');

        expect(room.id, equals('room-123'));
        expect(room.name, equals('Test Room'));
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.getRoom(''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('propagates NotFoundException', () async {
        when(
          () => mockTransport.request<Room>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(const NotFoundException(message: 'Not found'));

        expect(
          () => api.getRoom('nonexistent'),
          throwsA(isA<NotFoundException>()),
        );
      });

      test('supports cancellation', () async {
        final cancelToken = CancelToken();

        when(
          () => mockTransport.request<Room>(
            'GET',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => const Room(id: 'room-123', name: 'Test'),
        );

        await api.getRoom('room-123', cancelToken: cancelToken);

        verify(
          () => mockTransport.request<Room>(
            'GET',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<Room>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return const Room(id: 'room-123', name: 'Test');
        });

        await api.getRoom('room-123');

        expect(capturedUri?.path, equals('/api/v1/rooms/room-123'));
      });
    });

    // ============================================================
    // Threads
    // ============================================================

    group('getThreads', () {
      test('returns list of threads', () async {
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => [
            {'id': 'thread-1', 'room_id': 'room-123'},
            {'id': 'thread-2', 'room_id': 'room-123'},
          ],
        );

        final threads = await api.getThreads('room-123');

        expect(threads.length, equals(2));
        expect(threads[0].id, equals('thread-1'));
        expect(threads[1].id, equals('thread-2'));
      });

      test('returns empty list when no threads', () async {
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => <dynamic>[]);

        final threads = await api.getThreads('room-123');

        expect(threads, isEmpty);
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.getThreads(''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('supports cancellation', () async {
        final cancelToken = CancelToken();

        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async => <dynamic>[]);

        await api.getThreads('room-123', cancelToken: cancelToken);

        verify(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<List<dynamic>>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return <dynamic>[];
        });

        await api.getThreads('room-123');

        expect(capturedUri?.path, equals('/api/v1/rooms/room-123/agui'));
      });
    });

    group('getThread', () {
      test('returns thread by ID', () async {
        when(
          () => mockTransport.request<ThreadInfo>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => const ThreadInfo(id: 'thread-123', roomId: 'room-123'),
        );

        final thread = await api.getThread('room-123', 'thread-123');

        expect(thread.id, equals('thread-123'));
        expect(thread.roomId, equals('room-123'));
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.getThread('', 'thread-123'),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('validates non-empty threadId', () {
        expect(
          () => api.getThread('room-123', ''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('propagates NotFoundException', () async {
        when(
          () => mockTransport.request<ThreadInfo>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(const NotFoundException(message: 'Not found'));

        expect(
          () => api.getThread('room-123', 'nonexistent'),
          throwsA(isA<NotFoundException>()),
        );
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<ThreadInfo>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return const ThreadInfo(id: 'thread-123', roomId: 'room-123');
        });

        await api.getThread('room-123', 'thread-456');

        expect(
          capturedUri?.path,
          equals('/api/v1/rooms/room-123/agui/thread-456'),
        );
      });
    });

    group('createThread', () {
      test('returns ThreadInfo', () async {
        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => {
            'thread_id': 'new-thread',
            'runs': <String, dynamic>{},
          },
        );

        final thread = await api.createThread('room-123');

        expect(thread.id, equals('new-thread'));
        expect(thread.roomId, equals('room-123'));
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.createThread(''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('propagates exceptions', () async {
        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(
          const ApiException(message: 'Server error', statusCode: 500),
        );

        expect(
          () => api.createThread('room-123'),
          throwsA(isA<ApiException>()),
        );
      });

      test('supports cancellation', () async {
        final cancelToken = CancelToken();

        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => {
            'thread_id': 'new-thread',
            'runs': <String, dynamic>{},
          },
        );

        await api.createThread('room-123', cancelToken: cancelToken);

        verify(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: cancelToken,
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return {'thread_id': 'new', 'runs': <String, dynamic>{}};
        });

        await api.createThread('room-123');

        expect(capturedUri?.path, equals('/api/v1/rooms/room-123/agui'));
      });
    });

    group('deleteThread', () {
      test('completes successfully', () async {
        when(
          () => mockTransport.request<void>(
            'DELETE',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((_) async {});

        await api.deleteThread('room-123', 'thread-456');

        verify(
          () => mockTransport.request<void>(
            'DELETE',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).called(1);
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.deleteThread('', 'thread-123'),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('validates non-empty threadId', () {
        expect(
          () => api.deleteThread('room-123', ''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('propagates NotFoundException', () async {
        when(
          () => mockTransport.request<void>(
            'DELETE',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(const NotFoundException(message: 'Not found'));

        expect(
          () => api.deleteThread('room-123', 'nonexistent'),
          throwsA(isA<NotFoundException>()),
        );
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<void>(
            'DELETE',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
        });

        await api.deleteThread('room-123', 'thread-456');

        expect(
          capturedUri?.path,
          equals('/api/v1/rooms/room-123/agui/thread-456'),
        );
      });
    });

    // ============================================================
    // Runs
    // ============================================================

    group('createRun', () {
      test('returns RunInfo', () async {
        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => {'run_id': 'new-run'},
        );

        final run = await api.createRun('room-123', 'thread-456');

        expect(run.id, equals('new-run'));
        expect(run.threadId, equals('thread-456'));
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.createRun('', 'thread-123'),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('validates non-empty threadId', () {
        expect(
          () => api.createRun('room-123', ''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('propagates exceptions', () async {
        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(
          const ApiException(message: 'Server error', statusCode: 500),
        );

        expect(
          () => api.createRun('room-123', 'thread-456'),
          throwsA(isA<ApiException>()),
        );
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<Map<String, dynamic>>(
            'POST',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return {'run_id': 'new'};
        });

        await api.createRun('room-123', 'thread-456');

        expect(
          capturedUri?.path,
          equals('/api/v1/rooms/room-123/agui/thread-456'),
        );
      });
    });

    group('getRun', () {
      test('returns run by ID', () async {
        when(
          () => mockTransport.request<RunInfo>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer(
          (_) async => const RunInfo(id: 'run-789', threadId: 'thread-456'),
        );

        final run = await api.getRun('room-123', 'thread-456', 'run-789');

        expect(run.id, equals('run-789'));
        expect(run.threadId, equals('thread-456'));
      });

      test('validates non-empty roomId', () {
        expect(
          () => api.getRun('', 'thread-123', 'run-456'),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('validates non-empty threadId', () {
        expect(
          () => api.getRun('room-123', '', 'run-456'),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('validates non-empty runId', () {
        expect(
          () => api.getRun('room-123', 'thread-456', ''),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('propagates NotFoundException', () async {
        when(
          () => mockTransport.request<RunInfo>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenThrow(const NotFoundException(message: 'Not found'));

        expect(
          () => api.getRun('room-123', 'thread-456', 'nonexistent'),
          throwsA(isA<NotFoundException>()),
        );
      });

      test('uses correct URL', () async {
        Uri? capturedUri;
        when(
          () => mockTransport.request<RunInfo>(
            'GET',
            any(),
            cancelToken: any(named: 'cancelToken'),
            fromJson: any(named: 'fromJson'),
            body: any(named: 'body'),
            headers: any(named: 'headers'),
            timeout: any(named: 'timeout'),
          ),
        ).thenAnswer((invocation) async {
          capturedUri = invocation.positionalArguments[1] as Uri;
          return const RunInfo(id: 'run-789', threadId: 'thread-456');
        });

        await api.getRun('room-123', 'thread-456', 'run-789');

        expect(
          capturedUri?.path,
          equals('/api/v1/rooms/room-123/agui/thread-456/run-789'),
        );
      });
    });
  });
}
