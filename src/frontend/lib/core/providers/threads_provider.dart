import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
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
///
/// Note: Variants implement equality/hashCode/toString manually rather than
/// using codegen (freezed/equatable) to avoid adding dependencies for these
/// few classes. If more sealed classes emerge, consider adding codegen.
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
      other is ThreadSelected && threadId == other.threadId;

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
      return threads.where((thread) => thread.id == threadId).firstOrNull;
    },
  );
});

// ---------------------------------------------------------------------------
// Last Viewed Thread Providers
// ---------------------------------------------------------------------------

/// Sealed class representing the last viewed thread state.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (lastViewed) {
///   case HasLastViewed(:final threadId):
///     // Use the previously viewed thread
///   case NoLastViewed():
///     // No previous thread for this room
/// }
/// ```
@immutable
sealed class LastViewed {
  const LastViewed();
}

/// A thread was previously viewed in this room.
@immutable
class HasLastViewed extends LastViewed {
  const HasLastViewed(this.threadId);

  final String threadId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is HasLastViewed && threadId == other.threadId;

  @override
  int get hashCode => threadId.hashCode;

  @override
  String toString() => 'HasLastViewed($threadId)';
}

/// No thread was previously viewed in this room.
@immutable
class NoLastViewed extends LastViewed {
  const NoLastViewed();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is NoLastViewed;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NoLastViewed()';
}

const _lastViewedKeyPrefix = 'lastViewedThread_';

/// Selects a thread and persists it as the last viewed for the room.
///
/// This is a shared helper used by both RoomScreen and HistoryPanel.
/// It handles:
/// 1. Setting the thread selection state
/// 2. Fire-and-forget persistence to SharedPreferences
///
/// For selection with navigation, use [selectThread] instead.
void selectAndPersistThread({
  required WidgetRef ref,
  required String roomId,
  required String threadId,
}) {
  ref.read(threadSelectionProvider.notifier).set(ThreadSelected(threadId));
  unawaited(
    setLastViewedThread(
      roomId: roomId,
      threadId: threadId,
      invalidate: invalidateLastViewed(ref),
    ).catchError((Object e) {
      debugPrint('Failed to persist last viewed thread: $e');
    }),
  );
}

/// Selects a thread, persists it, and navigates to the thread URL.
///
/// Use this for user-initiated thread selection (e.g., tapping a thread).
/// For programmatic selection without navigation, use [selectAndPersistThread].
void selectThread({
  required WidgetRef ref,
  required String roomId,
  required String threadId,
  required void Function(String path) navigate,
}) {
  selectAndPersistThread(ref: ref, roomId: roomId, threadId: threadId);
  navigate('/rooms/$roomId?thread=$threadId');
}

/// Provider for getting the last viewed thread ID for a room.
///
/// Returns [HasLastViewed] with the thread ID if previously viewed,
/// or [NoLastViewed] if no thread was viewed in this room.
final lastViewedThreadProvider = FutureProvider.family<LastViewed, String>(
  (ref, roomId) async {
    final prefs = await SharedPreferences.getInstance();
    final threadId = prefs.getString('$_lastViewedKeyPrefix$roomId');
    if (threadId != null) {
      return HasLastViewed(threadId);
    }
    return const NoLastViewed();
  },
);

/// Callback for invalidating the last viewed thread provider.
typedef InvalidateLastViewed = void Function(String roomId);

/// Creates an [InvalidateLastViewed] callback from a ref.
///
/// Use this to pass to [setLastViewedThread] or [clearLastViewedThread]:
/// ```dart
/// setLastViewedThread(
///   roomId: roomId,
///   threadId: threadId,
///   invalidate: invalidateLastViewed(ref),
/// );
/// ```
InvalidateLastViewed invalidateLastViewed(WidgetRef ref) {
  return (roomId) => ref.invalidate(lastViewedThreadProvider(roomId));
}

/// Saves the last viewed thread for a room.
///
/// After saving, calls [invalidate] to refresh [lastViewedThreadProvider].
Future<void> setLastViewedThread({
  required String roomId,
  required String threadId,
  required InvalidateLastViewed invalidate,
}) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('$_lastViewedKeyPrefix$roomId', threadId);
  invalidate(roomId);
}

/// Clears the last viewed thread for a room.
///
/// After clearing, calls [invalidate] to refresh [lastViewedThreadProvider].
Future<void> clearLastViewedThread({
  required String roomId,
  required InvalidateLastViewed invalidate,
}) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove('$_lastViewedKeyPrefix$roomId');
  invalidate(roomId);
}
