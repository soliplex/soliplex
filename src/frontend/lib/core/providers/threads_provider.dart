import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/mock_data.dart';

/// Provider for threads in a specific room.
///
/// AM1: Returns hardcoded mock data for room.
/// AM2: Replace with `api.getThreads(roomId)`.
final threadsProvider = FutureProvider.family<List<ThreadInfo>, String>(
  (ref, roomId) async {
    // Simulate network delay
    await Future<void>.delayed(const Duration(milliseconds: 200));

    // TODO(AM2): Replace with real API call
    // final api = ref.watch(soliplexApiProvider);
    // return await api.getThreads(roomId);

    return MockData.threads[roomId] ?? [];
  },
);

/// Provider for currently selected thread ID.
///
/// Updated by navigation when user selects a thread.
final currentThreadIdProvider = StateProvider<String?>((ref) => null);
