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
  /// Tracks in-flight fetches to prevent duplicate concurrent requests.
  final _inFlightFetches = <String, Future<List<ChatMessage>>>{};

  @override
  ThreadMessageCacheState build() {
    // Clear in-flight fetches on rebuild to prevent race conditions
    // if the notifier is recreated while fetches are pending.
    _inFlightFetches.clear();
    return {};
  }

  /// Get messages for a thread (from cache or backend).
  ///
  /// Returns cached messages immediately if available. Otherwise, fetches
  /// from backend via [SoliplexApi.getThreadMessages], caches the result,
  /// and returns it.
  ///
  /// Concurrent calls for the same thread share a single fetch request.
  ///
  /// Throws on network/API errors from the backend fetch.
  Future<List<ChatMessage>> getMessages(
    String roomId,
    String threadId,
  ) async {
    // Cache hit
    final cached = state[threadId];
    if (cached != null) return cached;

    // Join existing fetch or start new one
    return _inFlightFetches[threadId] ??= _fetchAndCache(roomId, threadId);
  }

  /// Fetches messages from backend and caches the result.
  ///
  /// On success, caches messages and returns them. On error, the exception
  /// is wrapped with thread context and re-thrown. The in-flight tracking
  /// is always cleaned up, allowing subsequent calls to retry the fetch.
  Future<List<ChatMessage>> _fetchAndCache(
    String roomId,
    String threadId,
  ) async {
    try {
      final api = ref.read(apiProvider);
      final messages = await api.getThreadMessages(roomId, threadId);
      state = {...state, threadId: messages};
      return messages;
    } on Exception catch (e, st) {
      Error.throwWithStackTrace(
        MessageFetchException(threadId: threadId, cause: e),
        st,
      );
    } finally {
      final _ = _inFlightFetches.remove(threadId);
    }
  }

  /// Update cached messages for a thread.
  ///
  /// Call this on run completion to persist the latest messages. Overwrites
  /// any existing cache entry for the thread.
  void updateMessages(String threadId, List<ChatMessage> messages) {
    state = {...state, threadId: messages};
  }

  /// Invalidate cache and refetch messages for a thread.
  ///
  /// Clears the cached entry and fetches fresh data from the backend.
  /// Use this when cached data may be stale and a refresh is needed.
  ///
  /// Throws on network/API errors from the backend fetch.
  Future<List<ChatMessage>> refreshMessages(
    String roomId,
    String threadId,
  ) async {
    // Remove from cache to force refetch
    state = {...state}..remove(threadId);
    // Discard any in-flight fetch for this thread (we'll start a new one)
    final _ = _inFlightFetches.remove(threadId);
    // Fetch fresh data
    return getMessages(roomId, threadId);
  }
}

/// Provider for the thread message cache.
///
/// Manages cached messages per thread with backend fetch on miss.
final threadMessageCacheProvider =
    NotifierProvider<ThreadMessageCache, ThreadMessageCacheState>(
  ThreadMessageCache.new,
);

/// Exception thrown when fetching messages for a thread fails.
///
/// Wraps the underlying exception with thread context for better debugging.
class MessageFetchException implements Exception {
  /// Creates an exception for a failed message fetch.
  MessageFetchException({required this.threadId, required this.cause})
      : assert(threadId.isNotEmpty, 'threadId must not be empty');

  /// The thread that failed to load.
  final String threadId;

  /// The underlying exception that caused the failure.
  final Exception cause;

  @override
  String toString() => 'Failed to load messages for thread $threadId: $cause';
}
