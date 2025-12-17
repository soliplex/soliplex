import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

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
