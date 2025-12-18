import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('threadsProvider', () {
    late MockSoliplexApi mockApi;

    setUp(() {
      mockApi = MockSoliplexApi();
    });

    test('returns list of threads from API', () async {
      // Arrange
      const roomId = 'general';
      final mockThreads = [
        const ThreadInfo(id: 'thread1', roomId: roomId),
        const ThreadInfo(id: 'thread2', roomId: roomId),
        const ThreadInfo(id: 'thread3', roomId: roomId),
      ];
      when(() => mockApi.getThreads(roomId))
          .thenAnswer((_) async => mockThreads);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final threads = await container.read(threadsProvider(roomId).future);

      // Assert
      expect(threads, hasLength(3));
      expect(threads[0].id, 'thread1');
      expect(threads[1].id, 'thread2');
      expect(threads[2].id, 'thread3');
      expect(threads.every((t) => t.roomId == roomId), isTrue);
      verify(() => mockApi.getThreads(roomId)).called(1);
    });

    test('propagates NotFoundException when room does not exist', () async {
      // Arrange
      const roomId = 'nonexistent';
      when(() => mockApi.getThreads(roomId)).thenThrow(
        const NotFoundException(
          message: 'Room not found',
          resource: '/rooms/nonexistent/agui',
        ),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Wait for state with error using a completer
      final completer = Completer<AsyncValue<List<ThreadInfo>>>();
      container
        ..listen(threadsProvider(roomId), (_, next) {
          if (next.hasError) {
            completer.complete(next);
          }
        })
        ..read(threadsProvider(roomId));
      final state = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => container.read(threadsProvider(roomId)),
      );

      // Assert
      expect(state.hasError, isTrue);
      expect(state.error, isA<NotFoundException>());
    });

    test('propagates NetworkException from API', () async {
      // Arrange
      const roomId = 'general';
      when(() => mockApi.getThreads(roomId)).thenThrow(
        const NetworkException(message: 'Connection failed'),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Wait for state with error using a completer
      final completer = Completer<AsyncValue<List<ThreadInfo>>>();
      container
        ..listen(threadsProvider(roomId), (_, next) {
          if (next.hasError) {
            completer.complete(next);
          }
        })
        ..read(threadsProvider(roomId));
      final state = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => container.read(threadsProvider(roomId)),
      );

      // Assert
      expect(state.hasError, isTrue);
      expect(state.error, isA<NetworkException>());
    });

    test('propagates ApiException from API', () async {
      // Arrange
      const roomId = 'general';
      when(() => mockApi.getThreads(roomId)).thenThrow(
        const ApiException(
          message: 'Internal server error',
          statusCode: 500,
        ),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Wait for state with error using a completer
      final completer = Completer<AsyncValue<List<ThreadInfo>>>();
      container
        ..listen(threadsProvider(roomId), (_, next) {
          if (next.hasError) {
            completer.complete(next);
          }
        })
        ..read(threadsProvider(roomId));
      final state = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => container.read(threadsProvider(roomId)),
      );

      // Assert
      expect(state.hasError, isTrue);
      expect(state.error, isA<ApiException>());
    });

    test('caches threads separately per room', () async {
      // Arrange
      const room1 = 'general';
      const room2 = 'technical';

      when(() => mockApi.getThreads(room1)).thenAnswer(
        (_) async => [TestData.createThread(id: 'thread1', roomId: room1)],
      );
      when(() => mockApi.getThreads(room2)).thenAnswer(
        (_) async => [TestData.createThread(id: 'thread2', roomId: room2)],
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final threads1 = await container.read(threadsProvider(room1).future);
      final threads2 = await container.read(threadsProvider(room2).future);

      // Assert - Both cached independently
      expect(threads1[0].id, 'thread1');
      expect(threads1[0].roomId, room1);
      expect(threads2[0].id, 'thread2');
      expect(threads2[0].roomId, room2);
      verify(() => mockApi.getThreads(room1)).called(1);
      verify(() => mockApi.getThreads(room2)).called(1);
    });

    test('can be refreshed per room', () async {
      // Arrange
      const roomId = 'general';
      final mockThreads1 = [
        TestData.createThread(id: 'thread1', roomId: roomId),
      ];
      final mockThreads2 = [
        TestData.createThread(id: 'thread1', roomId: roomId),
        TestData.createThread(id: 'thread2', roomId: roomId),
      ];

      when(() => mockApi.getThreads(roomId))
          .thenAnswer((_) async => mockThreads1);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - First fetch
      final threads1 = await container.read(threadsProvider(roomId).future);
      expect(threads1, hasLength(1));

      // Update mock for second fetch
      when(() => mockApi.getThreads(roomId))
          .thenAnswer((_) async => mockThreads2);

      // Refresh and fetch again
      container.refresh(threadsProvider(roomId));
      final threads2 = await container.read(threadsProvider(roomId).future);

      // Assert
      expect(threads2, hasLength(2));
      verify(() => mockApi.getThreads(roomId)).called(2);
    });

    test('returns empty list when room has no threads', () async {
      // Arrange
      const roomId = 'empty-room';
      when(() => mockApi.getThreads(roomId)).thenAnswer((_) async => []);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final threads = await container.read(threadsProvider(roomId).future);

      // Assert
      expect(threads, isEmpty);
      verify(() => mockApi.getThreads(roomId)).called(1);
    });
  });

  group('threadSelectionProvider', () {
    test('starts with NoThreadSelected', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final selection = container.read(threadSelectionProvider);

      expect(selection, isA<NoThreadSelected>());
    });

    test('can be updated to ThreadSelected', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container
          .read(threadSelectionProvider.notifier)
          .set(const ThreadSelected('thread-123'));

      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<ThreadSelected>());
      expect((selection as ThreadSelected).threadId, 'thread-123');
    });

    test('can be updated to NewThreadIntent', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container
          .read(threadSelectionProvider.notifier)
          .set(const NewThreadIntent());

      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<NewThreadIntent>());
    });
  });

  group('currentThreadIdProvider', () {
    test('returns null when NoThreadSelected', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threadId = container.read(currentThreadIdProvider);

      expect(threadId, isNull);
    });

    test('returns threadId when ThreadSelected', () {
      final container = ProviderContainer(
        overrides: [
          threadSelectionProviderOverride(const ThreadSelected('thread-123')),
        ],
      );
      addTearDown(container.dispose);

      final threadId = container.read(currentThreadIdProvider);

      expect(threadId, 'thread-123');
    });

    test('returns null when NewThreadIntent', () {
      final container = ProviderContainer(
        overrides: [
          threadSelectionProviderOverride(const NewThreadIntent()),
        ],
      );
      addTearDown(container.dispose);

      final threadId = container.read(currentThreadIdProvider);

      expect(threadId, isNull);
    });
  });
}
