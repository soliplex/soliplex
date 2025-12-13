import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../client/client.dart';
import 'client_provider.dart';
import 'room_provider.dart';

/// Provider for the currently selected thread ID.
final currentThreadProvider = StateProvider<String?>((ref) {
  return null;
});

/// Provider for fetching all threads in the current room.
final threadsProvider = FutureProvider<List<ThreadInfo>>((ref) async {
  final client = ref.watch(soliplexClientProvider);
  final roomId = ref.watch(currentRoomProvider);

  if (roomId == null) {
    return [];
  }

  return client.getThreads(roomId);
});

/// Provider for fetching threads in a specific room.
final roomThreadsProvider = FutureProvider.family<List<ThreadInfo>, String>((
  ref,
  roomId,
) async {
  final client = ref.watch(soliplexClientProvider);
  return client.getThreads(roomId);
});

/// Provider for fetching a specific thread.
final threadProvider = FutureProvider.family<ThreadInfo, ({String roomId, String threadId})>((
  ref,
  params,
) async {
  final client = ref.watch(soliplexClientProvider);
  return client.getThread(params.roomId, params.threadId);
});

/// Provider for creating a new thread.
final createThreadProvider = Provider<Future<({String threadId, String runId})> Function(String)>((ref) {
  final client = ref.watch(soliplexClientProvider);
  return (String roomId) => client.createThread(roomId);
});

/// Provider for deleting a thread.
final deleteThreadProvider = Provider<Future<void> Function(String, String)>((ref) {
  final client = ref.watch(soliplexClientProvider);
  return (String roomId, String threadId) => client.deleteThread(roomId, threadId);
});
