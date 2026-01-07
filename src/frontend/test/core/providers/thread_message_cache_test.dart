import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/thread_message_cache.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('ThreadMessageCache', () {
    late MockSoliplexApi mockApi;

    setUp(() {
      mockApi = MockSoliplexApi();
    });

    group('getMessages', () {
      test('returns cached messages on cache hit (no API call)', () async {
        // Arrange: Pre-populate cache
        final cachedMessages = [
          TestData.createMessage(id: 'msg-1', text: 'Hello'),
          TestData.createMessage(id: 'msg-2', text: 'World'),
        ];

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        // Pre-populate cache
        container
            .read(threadMessageCacheProvider.notifier)
            .updateMessages('thread-123', cachedMessages);

        // Act
        final messages = await container
            .read(threadMessageCacheProvider.notifier)
            .getMessages('room-abc', 'thread-123');

        // Assert
        expect(messages, hasLength(2));
        expect(messages[0].id, 'msg-1');
        expect(messages[1].id, 'msg-2');
        verifyNever(() => mockApi.getThreadMessages(any(), any()));
      });

      test('fetches from API and caches on cache miss', () async {
        // Arrange
        final apiMessages = [
          TestData.createMessage(id: 'msg-1', text: 'From API'),
        ];

        when(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .thenAnswer((_) async => apiMessages);

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        // Act
        final messages = await container
            .read(threadMessageCacheProvider.notifier)
            .getMessages('room-abc', 'thread-123');

        // Assert
        expect(messages, hasLength(1));
        expect(messages[0].id, 'msg-1');
        verify(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .called(1);

        // Verify cached
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState.containsKey('thread-123'), isTrue);
        expect(cacheState['thread-123'], hasLength(1));
      });

      test('subsequent calls use cache after initial fetch', () async {
        // Arrange
        final apiMessages = [
          TestData.createMessage(id: 'msg-1', text: 'From API'),
        ];

        when(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .thenAnswer((_) async => apiMessages);

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        final cache = container.read(threadMessageCacheProvider.notifier);

        // Act: First call - fetches from API
        await cache.getMessages('room-abc', 'thread-123');

        // Act: Second call - should use cache
        await cache.getMessages('room-abc', 'thread-123');

        // Assert: API only called once
        verify(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .called(1);
      });

      test('concurrent fetches share single API request', () async {
        // Arrange: Slow API response
        final apiMessages = [
          TestData.createMessage(id: 'msg-1', text: 'From API'),
        ];

        when(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .thenAnswer((_) async {
          // Simulate slow API
          await Future<void>.delayed(const Duration(milliseconds: 50));
          return apiMessages;
        });

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        final cache = container.read(threadMessageCacheProvider.notifier);

        // Act: Start two concurrent fetches
        final future1 = cache.getMessages('room-abc', 'thread-123');
        final future2 = cache.getMessages('room-abc', 'thread-123');

        // Both should complete with same result
        final results = await Future.wait([future1, future2]);

        // Assert: API called only once despite two concurrent requests
        verify(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .called(1);

        // Both callers get the same messages
        expect(results[0], hasLength(1));
        expect(results[1], hasLength(1));
        expect(results[0][0].id, 'msg-1');
        expect(results[1][0].id, 'msg-1');
      });

      test('different threads have separate cache entries', () async {
        // Arrange
        when(() => mockApi.getThreadMessages('room-abc', 'thread-1'))
            .thenAnswer(
          (_) async => [
            TestData.createMessage(id: 'msg-t1', text: 'Thread 1'),
          ],
        );
        when(() => mockApi.getThreadMessages('room-abc', 'thread-2'))
            .thenAnswer(
          (_) async => [
            TestData.createMessage(id: 'msg-t2', text: 'Thread 2'),
          ],
        );

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        final cache = container.read(threadMessageCacheProvider.notifier);

        // Act
        final messages1 = await cache.getMessages('room-abc', 'thread-1');
        final messages2 = await cache.getMessages('room-abc', 'thread-2');

        // Assert
        expect(messages1[0].id, 'msg-t1');
        expect(messages2[0].id, 'msg-t2');

        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState.keys, containsAll(['thread-1', 'thread-2']));
      });
    });

    group('updateMessages', () {
      test('updates cache for thread', () {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        final newMessages = [
          TestData.createMessage(id: 'msg-new', text: 'New message'),
        ];

        // Act
        container
            .read(threadMessageCacheProvider.notifier)
            .updateMessages('thread-123', newMessages);

        // Assert
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState['thread-123'], hasLength(1));
        expect(cacheState['thread-123']![0].id, 'msg-new');
      });

      test('overwrites existing cache entry', () {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        container.read(threadMessageCacheProvider.notifier)
          // Pre-populate
          ..updateMessages('thread-123', [
            TestData.createMessage(id: 'old-msg', text: 'Old'),
          ])
          // Act: Overwrite
          ..updateMessages('thread-123', [
            TestData.createMessage(id: 'new-msg', text: 'New'),
          ]);

        // Assert
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState['thread-123'], hasLength(1));
        expect(cacheState['thread-123']![0].id, 'new-msg');
      });

      test('does not affect other thread entries', () {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        container.read(threadMessageCacheProvider.notifier)
          // Pre-populate thread-1
          ..updateMessages('thread-1', [
            TestData.createMessage(id: 'msg-t1', text: 'Thread 1'),
          ])
          // Act: Update thread-2
          ..updateMessages('thread-2', [
            TestData.createMessage(id: 'msg-t2', text: 'Thread 2'),
          ]);

        // Assert: thread-1 unchanged
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState['thread-1']![0].id, 'msg-t1');
        expect(cacheState['thread-2']![0].id, 'msg-t2');
      });
    });

    group('clearThread', () {
      test('removes cache entry for thread', () {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        container.read(threadMessageCacheProvider.notifier)
          ..updateMessages('thread-123', [
            TestData.createMessage(id: 'msg-1', text: 'Test'),
          ])
          // Act
          ..clearThread('thread-123');

        // Assert
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState.containsKey('thread-123'), isFalse);
      });

      test('does not affect other thread entries', () {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        container.read(threadMessageCacheProvider.notifier)
          ..updateMessages('thread-1', [
            TestData.createMessage(id: 'msg-t1', text: 'Thread 1'),
          ])
          ..updateMessages('thread-2', [
            TestData.createMessage(id: 'msg-t2', text: 'Thread 2'),
          ])
          // Act
          ..clearThread('thread-1');

        // Assert
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState.containsKey('thread-1'), isFalse);
        expect(cacheState.containsKey('thread-2'), isTrue);
      });
    });

    group('clearAll', () {
      test('removes all cache entries', () {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        container.read(threadMessageCacheProvider.notifier)
          ..updateMessages('thread-1', [
            TestData.createMessage(id: 'msg-t1', text: 'Thread 1'),
          ])
          ..updateMessages('thread-2', [
            TestData.createMessage(id: 'msg-t2', text: 'Thread 2'),
          ])
          // Act
          ..clearAll();

        // Assert
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState, isEmpty);
      });
    });
  });

  group('threadMessagesProvider integration', () {
    late MockSoliplexApi mockApi;

    setUp(() {
      mockApi = MockSoliplexApi();
    });

    test('uses cache on hit (no API call)', () async {
      // Arrange: Pre-populate cache with messages
      final cachedMessages = [
        TestData.createMessage(id: 'cached-msg', text: 'From cache'),
      ];

      final mockRoom = TestData.createRoom(id: 'room-1');
      final mockThread = TestData.createThread(id: 'thread-1');

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
          currentRoomProvider.overrideWith((ref) => mockRoom),
          currentThreadProvider.overrideWith((ref) => mockThread),
        ],
      );
      addTearDown(container.dispose);

      // Pre-populate cache
      container
          .read(threadMessageCacheProvider.notifier)
          .updateMessages('thread-1', cachedMessages);

      // Act: Read threadMessagesProvider
      final messages =
          await container.read(threadMessagesProvider('thread-1').future);

      // Assert: Returns cached messages, no API call
      expect(messages, hasLength(1));
      expect(messages[0].id, 'cached-msg');
      verifyNever(() => mockApi.getThreadMessages(any(), any()));
    });

    test('fetches from API on cache miss', () async {
      // Arrange
      final apiMessages = [
        TestData.createMessage(id: 'api-msg', text: 'From API'),
      ];

      when(() => mockApi.getThreadMessages('room-1', 'thread-1'))
          .thenAnswer((_) async => apiMessages);

      final mockRoom = TestData.createRoom(id: 'room-1');
      final mockThread = TestData.createThread(id: 'thread-1');

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
          currentRoomProvider.overrideWith((ref) => mockRoom),
          currentThreadProvider.overrideWith((ref) => mockThread),
        ],
      );
      addTearDown(container.dispose);

      // Act: Read threadMessagesProvider (cache miss)
      final messages =
          await container.read(threadMessagesProvider('thread-1').future);

      // Assert: Fetched from API
      expect(messages, hasLength(1));
      expect(messages[0].id, 'api-msg');
      verify(() => mockApi.getThreadMessages('room-1', 'thread-1')).called(1);
    });

    test('returns empty list when no room selected', () async {
      // Arrange
      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
          currentRoomProvider.overrideWith((ref) => null),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final messages =
          await container.read(threadMessagesProvider('thread-1').future);

      // Assert: Empty list, no API call
      expect(messages, isEmpty);
      verifyNever(() => mockApi.getThreadMessages(any(), any()));
    });
  });
}
