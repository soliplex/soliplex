import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

/// Cache state: threadId -> messages.
typedef ThreadMessageCacheState = Map<String, List<ChatMessage>>;

/// Provides cached thread messages with backend fetch on cache miss.
///
/// This is the single source of truth for historical messages. It:
/// - Returns cached messages instantly on cache hit (no API call)
/// - Fetches from backend and caches on cache miss
/// - Updates cache when runs complete (via [updateMessages])
///
/// Example:
/// ```dart
/// // Get messages (fetches if not cached)
/// final messages = await ref.read(threadMessageCacheProvider.notifier)
///     .getMessages(roomId, threadId);
///
/// // Update cache after run completes
/// ref.read(threadMessageCacheProvider.notifier)
///     .updateMessages(threadId, allMessages);
/// ```
class ThreadMessageCache extends Notifier<ThreadMessageCacheState> {
  @override
  ThreadMessageCacheState build() => {};

  /// Get messages for a thread (from cache or backend).
  ///
  /// Returns cached messages immediately if available. Otherwise, fetches
  /// from backend via [SoliplexApi.getThreadMessages], caches the result,
  /// and returns it.
  ///
  /// Throws on network/API errors from the backend fetch.
  Future<List<ChatMessage>> getMessages(
    String roomId,
    String threadId,
  ) async {
    // Cache hit
    if (state.containsKey(threadId)) {
      return state[threadId]!;
    }

    // Cache miss - fetch from backend
    final api = ref.read(apiProvider);
    final messages = await api.getThreadMessages(roomId, threadId);

    // Store in cache
    state = {...state, threadId: messages};
    return messages;
  }

  /// Update cached messages for a thread.
  ///
  /// Call this on run completion to persist the latest messages. Overwrites
  /// any existing cache entry for the thread.
  void updateMessages(String threadId, List<ChatMessage> messages) {
    state = {...state, threadId: messages};
  }

  /// Clear cache entry for a thread.
  ///
  /// Call this when a thread is deleted to free memory.
  void clearThread(String threadId) {
    state = Map<String, List<ChatMessage>>.from(state)..remove(threadId);
  }

  /// Clear all cached messages.
  ///
  /// Call this on logout to ensure no stale data remains.
  void clearAll() {
    state = {};
  }
}

/// Provider for the thread message cache.
///
/// Manages cached messages per thread with backend fetch on miss.
final threadMessageCacheProvider =
    NotifierProvider<ThreadMessageCache, ThreadMessageCacheState>(
  ThreadMessageCache.new,
);
