import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/thread_message_cache.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('allMessagesProvider', () {
    late MockSoliplexApi mockApi;

    setUp(() {
      mockApi = MockSoliplexApi();
    });

    group('thread switching', () {
      test('messages persist in cache after switching threads', () async {
        // Arrange: Two threads with different messages
        final threadAMessages = [
          TestData.createMessage(id: 'msg-a1', text: 'Thread A message 1'),
          TestData.createMessage(id: 'msg-a2', text: 'Thread A message 2'),
        ];
        final threadBMessages = [
          TestData.createMessage(id: 'msg-b1', text: 'Thread B message'),
        ];

        final threadA = TestData.createThread(id: 'thread-a');
        final threadB = TestData.createThread(id: 'thread-b');
        final mockRoom = TestData.createRoom(id: 'room-abc');

        // Shared map that persists across provider rebuilds
        final sharedData = <String, List<ChatMessage>>{
          'thread-a': threadAMessages,
          'thread-b': threadBMessages,
        };

        // Step 1: View Thread A
        var container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => threadA),
            currentRoomProvider.overrideWith((ref) => mockRoom),
            threadMessageCacheProvider.overrideWith(
              () => _SharedDataCache(sharedData),
            ),
            activeRunNotifierOverride(const IdleState()),
          ],
        );

        var messages = await container.read(allMessagesProvider.future);
        expect(messages, hasLength(2));
        expect(messages[0].id, 'msg-a1');
        expect(messages[1].id, 'msg-a2');
        container.dispose();

        // Step 2: Switch to Thread B
        container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => threadB),
            currentRoomProvider.overrideWith((ref) => mockRoom),
            threadMessageCacheProvider.overrideWith(
              () => _SharedDataCache(sharedData),
            ),
            activeRunNotifierOverride(const IdleState()),
          ],
        );

        messages = await container.read(allMessagesProvider.future);
        expect(messages, hasLength(1));
        expect(messages[0].id, 'msg-b1');
        container.dispose();

        // Step 3: Switch back to Thread A - messages should still be cached
        container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => threadA),
            currentRoomProvider.overrideWith((ref) => mockRoom),
            threadMessageCacheProvider.overrideWith(
              () => _SharedDataCache(sharedData),
            ),
            activeRunNotifierOverride(const IdleState()),
          ],
        );
        addTearDown(container.dispose);

        messages = await container.read(allMessagesProvider.future);

        // Assert: Thread A messages are still available (not lost)
        expect(
          messages,
          hasLength(2),
          reason: 'Thread A messages should persist after switching',
        );
        expect(messages[0].id, 'msg-a1');
        expect(messages[1].id, 'msg-a2');
      });

      test('cache persists messages when run completes on thread', () async {
        // This tests that updateMessages() correctly persists run results
        final mockRoom = TestData.createRoom(id: 'room-abc');
        final threadA = TestData.createThread(id: 'thread-a');

        // Start with empty cache, then populate via updateMessages
        final sharedData = <String, List<ChatMessage>>{};

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => threadA),
            currentRoomProvider.overrideWith((ref) => mockRoom),
            threadMessageCacheProvider.overrideWith(
              () => _SharedDataCache(sharedData),
            ),
            activeRunNotifierOverride(const IdleState()),
          ],
        );
        addTearDown(container.dispose);

        // Simulate run completion by updating cache
        final newMessages = [
          TestData.createMessage(id: 'msg-1', text: 'User message'),
          TestData.createMessage(id: 'msg-2', text: 'AI response'),
        ];
        container
            .read(threadMessageCacheProvider.notifier)
            .updateMessages('thread-a', newMessages);

        // Verify messages are retrievable
        final cacheState = container.read(threadMessageCacheProvider);
        expect(cacheState['thread-a'], hasLength(2));
        expect(cacheState['thread-a']![0].id, 'msg-1');
        expect(cacheState['thread-a']![1].id, 'msg-2');
      });

    });

    group('message deduplication', () {
      test('deduplicates messages by ID (cached messages take precedence)',
          () async {
        // Arrange: Same message ID in both cached and running state
        final cachedMessage = TestData.createMessage(
          id: 'msg-1',
          text: 'Cached version',
        );
        final runningMessage = TestData.createMessage(
          id: 'msg-1',
          text: 'Running version (should be ignored)',
        );

        final mockThread = TestData.createThread(id: 'thread-123');
        final mockRoom = TestData.createRoom(id: 'room-abc');

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => mockThread),
            currentRoomProvider.overrideWith((ref) => mockRoom),
            threadMessageCacheProvider.overrideWith(() {
              return _PrePopulatedCache({'thread-123': [cachedMessage]});
            }),
            activeRunNotifierOverride(
              RunningState(
                conversation: Conversation(
                  threadId: 'thread-123',
                  messages: [runningMessage],
                  status: const Running(runId: 'run-1'),
                ),
              ),
            ),
          ],
        );
        addTearDown(container.dispose);

        // Act
        final messages = await container.read(allMessagesProvider.future);

        // Assert: Only one message, with cached content
        expect(messages, hasLength(1));
        expect(messages[0].id, 'msg-1');
        expect((messages[0] as TextMessage).text, 'Cached version');
      });

      test('preserves order: cached messages first, then new running messages',
          () async {
        // Arrange
        final cachedMessages = [
          TestData.createMessage(id: 'msg-1', text: 'First cached'),
          TestData.createMessage(id: 'msg-2', text: 'Second cached'),
        ];
        final runningMessages = [
          TestData.createMessage(id: 'msg-3', text: 'New from run'),
        ];

        final mockThread = TestData.createThread(id: 'thread-123');
        final mockRoom = TestData.createRoom(id: 'room-abc');

        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => mockThread),
            currentRoomProvider.overrideWith((ref) => mockRoom),
            threadMessageCacheProvider.overrideWith(() {
              return _PrePopulatedCache({'thread-123': cachedMessages});
            }),
            activeRunNotifierOverride(
              RunningState(
                conversation: Conversation(
                  threadId: 'thread-123',
                  messages: runningMessages,
                  status: const Running(runId: 'run-1'),
                ),
              ),
            ),
          ],
        );
        addTearDown(container.dispose);

        // Act
        final messages = await container.read(allMessagesProvider.future);

        // Assert: Order is [cached..., running...]
        expect(messages, hasLength(3));
        expect(messages[0].id, 'msg-1');
        expect(messages[1].id, 'msg-2');
        expect(messages[2].id, 'msg-3');
      });

      test('returns empty list when no thread selected', () async {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider.overrideWith((ref) => null),
            currentRoomProvider
                .overrideWith((ref) => TestData.createRoom(id: 'room-abc')),
            activeRunNotifierOverride(const IdleState()),
          ],
        );
        addTearDown(container.dispose);

        // Act
        final messages = await container.read(allMessagesProvider.future);

        // Assert
        expect(messages, isEmpty);
      });

      test('returns empty list when no room selected', () async {
        // Arrange
        final container = ProviderContainer(
          overrides: [
            apiProvider.overrideWithValue(mockApi),
            currentThreadProvider
                .overrideWith((ref) => TestData.createThread(id: 'thread-123')),
            currentRoomProvider.overrideWith((ref) => null),
            activeRunNotifierOverride(const IdleState()),
          ],
        );
        addTearDown(container.dispose);

        // Act
        final messages = await container.read(allMessagesProvider.future);

        // Assert
        expect(messages, isEmpty);
      });
    });
  });
}

/// Test helper: Pre-populated cache that doesn't fetch from API.
class _PrePopulatedCache extends ThreadMessageCache {
  _PrePopulatedCache(this._initialState);

  final ThreadMessageCacheState _initialState;

  @override
  ThreadMessageCacheState build() => _initialState;
}

/// Test helper: Cache backed by shared map for thread switching tests.
///
/// Each ProviderContainer creates a new instance, but they all
/// read/write to the same shared map to simulate cache persistence.
class _SharedDataCache extends ThreadMessageCache {
  _SharedDataCache(this._sharedData);

  final Map<String, List<ChatMessage>> _sharedData;

  @override
  ThreadMessageCacheState build() => Map.from(_sharedData);

  @override
  Future<List<ChatMessage>> getMessages(String roomId, String threadId) async {
    // Check shared data first (simulates persistent cache)
    final cached = _sharedData[threadId];
    if (cached != null) return cached;

    // Delegate to parent for API fetch
    final messages = await super.getMessages(roomId, threadId);
    // Persist to shared data
    _sharedData[threadId] = messages;
    return messages;
  }

  @override
  void updateMessages(String threadId, List<ChatMessage> messages) {
    _sharedData[threadId] = messages;
    state = Map.from(_sharedData);
  }
}
