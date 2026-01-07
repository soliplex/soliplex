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
