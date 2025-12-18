import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';

/// Provider for threads in a specific room.
///
/// Fetches threads from the backend API using [SoliplexApi.getThreads].
/// Each room's threads are cached separately by Riverpod's family provider.
///
/// **Usage**:
/// ```dart
/// // Read threads for a room
/// final threadsAsync = ref.watch(threadsProvider('room-id'));
///
/// // Refresh threads for a room
/// ref.refresh(threadsProvider('room-id'));
/// ```
///
/// **Error Handling**:
/// Throws [SoliplexException] subtypes which should be handled in the UI:
/// - [NetworkException]: Connection failures, timeouts
/// - [NotFoundException]: Room not found (404)
/// - [AuthException]: 401/403 authentication errors (AM7+)
/// - [ApiException]: Other server errors
final threadsProvider = FutureProvider.family<List<ThreadInfo>, String>(
  (ref, roomId) async {
    final api = ref.watch(apiProvider);
    return api.getThreads(roomId);
  },
);

/// Sealed class representing the current thread selection state.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (selection) {
///   case NoThreadSelected():
///     // Show "Select a thread" message
///   case ThreadSelected(:final threadId):
///     // Load and display thread
///   case NewThreadIntent():
///     // Ready to create a new thread
/// }
/// ```
@immutable
sealed class ThreadSelection {
  const ThreadSelection();
}

/// No thread is currently selected.
///
/// This is the initial state before the user selects or creates a thread.
@immutable
class NoThreadSelected extends ThreadSelection {
  const NoThreadSelected();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is NoThreadSelected;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NoThreadSelected()';
}

/// A specific thread is selected.
@immutable
class ThreadSelected extends ThreadSelection {
  const ThreadSelected(this.threadId);

  /// The ID of the selected thread.
  final String threadId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ThreadSelected &&
          runtimeType == other.runtimeType &&
          threadId == other.threadId;

  @override
  int get hashCode => threadId.hashCode;

  @override
  String toString() => 'ThreadSelected(threadId: $threadId)';
}

/// User intends to create a new thread.
///
/// The next message sent will create a new thread instead of
/// using an existing one.
@immutable
class NewThreadIntent extends ThreadSelection {
  const NewThreadIntent();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is NewThreadIntent;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NewThreadIntent()';
}

/// Notifier for thread selection state.
class ThreadSelectionNotifier extends Notifier<ThreadSelection> {
  @override
  ThreadSelection build() => const NoThreadSelected();

  // ignore: use_setters_to_change_properties
  void set(ThreadSelection value) => state = value;
}

/// Provider for current thread selection state.
///
/// Updated by navigation when user selects a thread.
///
/// **Usage**:
/// ```dart
/// // Select a thread
/// ref.read(threadSelectionProvider.notifier).set(ThreadSelected('thread-id'));
///
/// // Signal new thread intent
/// ref.read(threadSelectionProvider.notifier).set(const NewThreadIntent());
///
/// // Clear selection
/// ref.read(threadSelectionProvider.notifier).set(const NoThreadSelected());
/// ```
final threadSelectionProvider =
    NotifierProvider<ThreadSelectionNotifier, ThreadSelection>(
  ThreadSelectionNotifier.new,
);

/// Provider for currently selected thread ID.
///
/// Returns the thread ID if a thread is selected, null otherwise.
/// This is a convenience accessor for code that only needs the ID.
final currentThreadIdProvider = Provider<String?>((ref) {
  final selection = ref.watch(threadSelectionProvider);
  return switch (selection) {
    ThreadSelected(:final threadId) => threadId,
    _ => null,
  };
});

/// Provider for the currently selected thread.
///
/// Returns null if no thread is selected, no room is selected,
/// or thread not found.
final currentThreadProvider = Provider<ThreadInfo?>((ref) {
  final selection = ref.watch(threadSelectionProvider);
  final threadId = switch (selection) {
    ThreadSelected(:final threadId) => threadId,
    _ => null,
  };
  if (threadId == null) return null;

  final roomId = ref.watch(currentRoomIdProvider);
  if (roomId == null) return null;

  final threadsAsync = ref.watch(threadsProvider(roomId));
  return threadsAsync.whenOrNull(
    data: (threads) {
      try {
        return threads.firstWhere((thread) => thread.id == threadId);
      } catch (_) {
        return null;
      }
    },
  );
});
