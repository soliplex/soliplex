import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/client/client.dart';
import 'package:soliplex_flutter/providers/client_provider.dart';
import 'package:soliplex_flutter/providers/room_provider.dart';
import 'package:soliplex_flutter/providers/thread_provider.dart';

import '../mocks/mock_soliplex_client.dart';

void main() {
  group('currentThreadProvider', () {
    test('initial state is null', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      expect(container.read(currentThreadProvider), isNull);
    });

    test('can set thread id', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(currentThreadProvider.notifier).state = 'thread1';

      expect(container.read(currentThreadProvider), equals('thread1'));
    });

    test('can update thread id', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(currentThreadProvider.notifier).state = 'thread1';
      container.read(currentThreadProvider.notifier).state = 'thread2';

      expect(container.read(currentThreadProvider), equals('thread2'));
    });

    test('can clear thread id', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(currentThreadProvider.notifier).state = 'thread1';
      container.read(currentThreadProvider.notifier).state = null;

      expect(container.read(currentThreadProvider), isNull);
    });
  });

  group('threadsProvider', () {
    test('returns empty list when no room selected', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // No room selected
      expect(container.read(currentRoomProvider), isNull);

      // Wait for provider to complete
      final threadsAsync = await container.read(threadsProvider.future);

      expect(threadsAsync, isEmpty);
    });

    test('fetches threads for current room', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      // Wait for provider to complete
      final threadsAsync = await container.read(threadsProvider.future);

      expect(threadsAsync, isA<List<ThreadInfo>>());
      expect(mockClient.getThreadsCalled, isTrue);
    });
  });

  group('roomThreadsProvider', () {
    test('fetches threads for specific room', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Fetch threads for specific room
      final threadsAsync = await container.read(roomThreadsProvider('room1').future);

      expect(threadsAsync, isA<List<ThreadInfo>>());
      expect(mockClient.getThreadsCalled, isTrue);
    });
  });

  group('threadProvider', () {
    test('fetches specific thread', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Fetch specific thread
      final threadAsync = await container.read(
        threadProvider((roomId: 'room1', threadId: 'thread1')).future,
      );

      expect(threadAsync, isA<ThreadInfo>());
      expect(mockClient.getThreadCalled, isTrue);
    });
  });

  group('createThreadProvider', () {
    test('provides create thread function', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      final createThread = container.read(createThreadProvider);

      expect(createThread, isA<Function>());

      // Call the function
      final result = await createThread('room1');

      expect(result.threadId, isNotEmpty);
      expect(result.runId, isNotEmpty);
      expect(mockClient.createThreadCalled, isTrue);
    });
  });

  group('deleteThreadProvider', () {
    test('provides delete thread function', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      final deleteThread = container.read(deleteThreadProvider);

      expect(deleteThread, isA<Function>());

      // Call the function
      await deleteThread('room1', 'thread1');

      expect(mockClient.deleteThreadCalled, isTrue);
    });
  });
}
