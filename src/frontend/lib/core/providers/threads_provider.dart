import 'package:flutter_riverpod/flutter_riverpod.dart';
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

/// Provider for currently selected thread ID.
///
/// Updated by navigation when user selects a thread.
final currentThreadIdProvider = StateProvider<String?>((ref) => null);

/// Provider for the currently selected thread.
///
/// Returns null if no thread is selected, no room is selected, or thread not found.
final currentThreadProvider = Provider<ThreadInfo?>((ref) {
  final threadId = ref.watch(currentThreadIdProvider);
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
