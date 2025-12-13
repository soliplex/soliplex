import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../client/client.dart';
import 'client_provider.dart';

/// Provider for the currently selected room ID.
final currentRoomProvider = StateProvider<String?>((ref) {
  return null;
});

/// Provider for fetching all rooms from the server.
final roomsProvider = FutureProvider<List<Room>>((ref) async {
  final client = ref.watch(soliplexClientProvider);
  // Watch server URL to refetch when it changes
  ref.watch(serverUrlProvider);
  return client.getRooms();
});

/// Provider for fetching a specific room.
final roomProvider = FutureProvider.family<Room, String>((ref, roomId) async {
  final client = ref.watch(soliplexClientProvider);
  return client.getRoom(roomId);
});
