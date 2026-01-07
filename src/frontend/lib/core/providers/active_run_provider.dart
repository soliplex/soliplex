import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/thread_message_cache.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

/// Provider for active run state and actions.
///
/// Manages AG-UI streaming for the current thread. Use this to:
/// - Start a new chat run
/// - Cancel an active run
/// - Watch streaming status and messages
///
/// Example:
/// ```dart
/// // Start a run
/// ref.read(activeRunNotifierProvider.notifier).startRun(
///   roomId: 'room-123',
///   threadId: 'thread-456',
///   userMessage: 'Hello!',
/// );
///
/// // Watch state
/// final runState = ref.watch(activeRunNotifierProvider);
/// if (runState.isRunning) {
///   // Show activity indicator
/// }
/// ```
final activeRunNotifierProvider =
    NotifierProvider<ActiveRunNotifier, ActiveRunState>(ActiveRunNotifier.new);

/// Provider indicating whether a message can be sent.
///
/// Returns true if:
/// - A room is selected
/// - No run is currently active
/// - Either: a thread is selected, OR room has no threads, OR new intent is set
///
/// Example:
/// ```dart
/// final canSend = ref.watch(canSendMessageProvider);
/// ElevatedButton(
///   onPressed: canSend ? _handleSend : null,
///   child: Text('Send'),
/// )
/// ```
final canSendMessageProvider = Provider<bool>((ref) {
  final room = ref.watch(currentRoomProvider);
  final thread = ref.watch(currentThreadProvider);
  final runState = ref.watch(activeRunNotifierProvider);
  final selection = ref.watch(threadSelectionProvider);

  // Must have a room selected
  if (room == null) return false;

  // Can't send while running
  if (runState.isRunning) return false;

  // If thread selected, can send
  if (thread != null) return true;

  // Check selection state
  if (selection is NewThreadIntent) return true;

  // No thread selected - check if room has threads
  final roomId = room.id;
  final threadsAsync = ref.watch(threadsProvider(roomId));

  return threadsAsync.when(
    data: (threads) {
      // Can send if no threads exist (will create first thread)
      return threads.isEmpty;
    },
    loading: () => false,
    error: (_, __) => false,
  );
});

/// Provider for historical messages for a thread.
///
/// Fetches messages from the cache (instant) or backend (on cache miss).
/// The cache is populated on first access and updated when runs complete.
final threadMessagesProvider =
    FutureProvider.family<List<ChatMessage>, String>((ref, threadId) async {
  final room = ref.watch(currentRoomProvider);
  if (room == null) return [];

  return ref.read(threadMessageCacheProvider.notifier).getMessages(
        room.id,
        threadId,
      );
});

/// Provider for all messages to display in chat.
///
/// Merges cached messages (historical) with active run messages (streaming),
/// deduplicating by message ID. Automatically updates as either source changes.
///
/// Example:
/// ```dart
/// final messages = ref.watch(allMessagesProvider);
/// ListView.builder(
///   itemCount: messages.length,
///   itemBuilder: (context, index) => MessageWidget(messages[index]),
/// )
/// ```
final allMessagesProvider = Provider<List<ChatMessage>>((ref) {
  final thread = ref.watch(currentThreadProvider);
  if (thread == null) return [];

  final historyAsync = ref.watch(threadMessagesProvider(thread.id));
  final runState = ref.watch(activeRunNotifierProvider);

  final history = historyAsync.value ?? [];
  return _mergeMessages(history, runState.messages);
});

/// Merges cached and running messages, deduplicating by ID.
///
/// Preserves order: cached messages first, then new running messages.
List<ChatMessage> _mergeMessages(
  List<ChatMessage> cached,
  List<ChatMessage> running,
) {
  final seenIds = <String>{};
  final result = <ChatMessage>[];

  // Add cached first (historical messages)
  for (final msg in cached) {
    if (seenIds.add(msg.id)) {
      result.add(msg);
    }
  }

  // Add running (may include new messages not yet cached)
  for (final msg in running) {
    if (seenIds.add(msg.id)) {
      result.add(msg);
    }
  }

  return result;
}

/// Provider indicating whether a run is currently streaming.
///
/// Example:
/// ```dart
/// final isStreaming = ref.watch(isStreamingProvider);
/// if (isStreaming) {
///   // Show streaming indicator
/// }
/// ```
final isStreamingProvider = Provider<bool>((ref) {
  final runState = ref.watch(activeRunNotifierProvider);
  return runState.isRunning;
});
