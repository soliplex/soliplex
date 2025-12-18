import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
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

/// Provider for historical messages for the current thread.
///
/// In AM3, this returns an empty list since the backend doesn't provide
/// a dedicated endpoint for historical messages. AM4 will implement
/// message caching/persistence.
///
/// See: planning/ui/chat.md - Phase 2 (Message History)
final threadMessagesProvider =
    FutureProvider.family<List<ChatMessage>, String>((ref, threadId) async {
  // AM3: No historical messages
  // AM4: Implement message caching
  return [];
});

/// Provider for all messages to display in chat.
///
/// Merges historical messages (from API) with active run messages (streaming).
/// Automatically updates as either source changes.
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
  return [...history, ...runState.messages];
});

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
