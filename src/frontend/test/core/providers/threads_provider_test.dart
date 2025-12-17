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

      // Act & Assert
      await expectLater(
        container.read(threadsProvider(roomId).future),
        throwsA(isA<NotFoundException>()),
      );
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

      // Act & Assert
      await expectLater(
        container.read(threadsProvider(roomId).future),
        throwsA(isA<NetworkException>()),
      );
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

      // Act & Assert
      await expectLater(
        container.read(threadsProvider(roomId).future),
        throwsA(isA<ApiException>()),
      );
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

  group('currentThreadIdProvider', () {
    test('starts with null', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final threadId = container.read(currentThreadIdProvider);

      expect(threadId, isNull);
    });

    test('can be updated', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(currentThreadIdProvider.notifier).state = 'thread-123';

      expect(container.read(currentThreadIdProvider), 'thread-123');
    });
  });
}
