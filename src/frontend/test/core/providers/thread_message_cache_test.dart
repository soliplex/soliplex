import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart' show NetworkException;
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/thread_message_cache.dart';

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

      test('propagates API errors wrapped with thread context', () async {
        // Arrange
        when(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .thenThrow(const NetworkException(message: 'Connection failed'));

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        // Act & Assert: Error is wrapped with MessageFetchException
        await expectLater(
          container
              .read(threadMessageCacheProvider.notifier)
              .getMessages('room-abc', 'thread-123'),
          throwsA(
            allOf([
              isA<MessageFetchException>(),
              predicate<MessageFetchException>(
                (e) =>
                    e.threadId == 'thread-123' && e.cause is NetworkException,
                'has correct threadId and cause',
              ),
            ]),
          ),
        );

        // Cache should remain empty (no partial caching on error)
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState.containsKey('thread-123'), isFalse);
      });

      test('allows retry after API error', () async {
        // Arrange: First call fails, second succeeds
        var callCount = 0;
        when(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .thenAnswer((_) async {
          callCount++;
          if (callCount == 1) {
            throw const NetworkException(message: 'Connection failed');
          }
          return [TestData.createMessage(id: 'msg-1', text: 'Success')];
        });

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        final cache = container.read(threadMessageCacheProvider.notifier);

        // First call fails (wrapped in MessageFetchException)
        await expectLater(
          cache.getMessages('room-abc', 'thread-123'),
          throwsA(isA<MessageFetchException>()),
        );

        // Second call retries and succeeds
        final messages = await cache.getMessages('room-abc', 'thread-123');
        expect(messages, hasLength(1));
        expect(messages[0].id, 'msg-1');

        // API was called twice (retry after failure)
        verify(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .called(2);
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

    group('MessageFetchException', () {
      test('asserts threadId is not empty', () {
        expect(
          () => MessageFetchException(
            threadId: '',
            cause: const NetworkException(message: 'Failed'),
          ),
          throwsA(isA<AssertionError>()),
        );
      });

      test('allows non-empty threadId', () {
        final exception = MessageFetchException(
          threadId: 'valid-thread-id',
          cause: const NetworkException(message: 'Failed'),
        );
        expect(exception.threadId, 'valid-thread-id');
        expect(exception.cause, isA<NetworkException>());
      });
    });

    group('refreshMessages', () {
      test('clears cache and refetches from API', () async {
        // Arrange: Pre-populate cache with stale data
        final staleMessages = [
          TestData.createMessage(id: 'stale-msg', text: 'Stale'),
        ];
        final freshMessages = [
          TestData.createMessage(id: 'fresh-msg', text: 'Fresh'),
        ];

        when(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .thenAnswer((_) async => freshMessages);

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        // Pre-populate cache
        container
            .read(threadMessageCacheProvider.notifier)
            .updateMessages('thread-123', staleMessages);

        // Verify stale data is cached
        expect(
          container.read(threadMessageCacheProvider)['thread-123']![0].id,
          'stale-msg',
        );

        // Act
        final messages = await container
            .read(threadMessageCacheProvider.notifier)
            .refreshMessages('room-abc', 'thread-123');

        // Assert: Got fresh data
        expect(messages, hasLength(1));
        expect(messages[0].id, 'fresh-msg');

        // Assert: Cache updated with fresh data
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState['thread-123']![0].id, 'fresh-msg');

        // Assert: API was called
        verify(() => mockApi.getThreadMessages('room-abc', 'thread-123'))
            .called(1);
      });

      test('does not affect other thread entries', () async {
        // Arrange
        when(() => mockApi.getThreadMessages('room-abc', 'thread-1'))
            .thenAnswer(
          (_) async => [
            TestData.createMessage(id: 'refreshed-t1', text: 'Refreshed'),
          ],
        );

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
          ],
        );
        addTearDown(container.dispose);

        // Pre-populate both threads
        container.read(threadMessageCacheProvider.notifier)
          ..updateMessages('thread-1', [
            TestData.createMessage(id: 'old-t1', text: 'Old T1'),
          ])
          ..updateMessages('thread-2', [
            TestData.createMessage(id: 'msg-t2', text: 'Thread 2'),
          ]);

        // Act: Refresh thread-1
        await container
            .read(threadMessageCacheProvider.notifier)
            .refreshMessages('room-abc', 'thread-1');

        // Assert: thread-2 unchanged
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState['thread-1']![0].id, 'refreshed-t1');
        expect(cacheState['thread-2']![0].id, 'msg-t2');
      });
    });
  });
}
