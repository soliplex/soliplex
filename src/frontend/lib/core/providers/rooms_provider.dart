import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/mock_data.dart';

/// Provider for list of rooms.
///
/// AM1: Returns hardcoded mock data.
/// AM2: Replace with `api.getRooms()`.
final roomsProvider = FutureProvider<List<Room>>((ref) async {
  // Simulate network delay
  await Future<void>.delayed(const Duration(milliseconds: 300));

  // TODO(AM2): Replace with real API call
  // final api = ref.watch(soliplexApiProvider);
  // return await api.getRooms();

  return MockData.rooms;
});

/// Provider for currently selected room ID.
///
/// Updated by navigation when user selects a room.
final currentRoomIdProvider = StateProvider<String?>((ref) => null);

/// Provider for the currently selected room.
///
/// Returns null if no room is selected or room not found.
final currentRoomProvider = Provider<Room?>((ref) {
  final roomId = ref.watch(currentRoomIdProvider);
  if (roomId == null) return null;

  final roomsAsync = ref.watch(roomsProvider);
  return roomsAsync.whenOrNull(
    data: (rooms) {
      try {
        return rooms.firstWhere((room) => room.id == roomId);
      } catch (_) {
        return null;
      }
    },
  );
});
