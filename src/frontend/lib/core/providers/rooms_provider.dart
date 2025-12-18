import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

/// Provider for list of rooms.
///
/// Fetches rooms from the backend API using [SoliplexApi.getRooms].
/// The result is automatically cached by Riverpod until explicitly refreshed.
///
/// **Usage**:
/// ```dart
/// // Read rooms
/// final roomsAsync = ref.watch(roomsProvider);
///
/// // Refresh rooms
/// ref.refresh(roomsProvider);
/// ```
///
/// **Error Handling**:
/// Throws [SoliplexException] subtypes which should be handled in the UI:
/// - [NetworkException]: Connection failures, timeouts
/// - [AuthException]: 401/403 authentication errors (AM7+)
/// - [ApiException]: Other server errors
final roomsProvider = FutureProvider<List<Room>>((ref) async {
  final api = ref.watch(apiProvider);
  return api.getRooms();
});

/// Notifier for currently selected room ID.
class CurrentRoomIdNotifier extends Notifier<String?> {
  @override
  String? build() => null;

  // ignore: use_setters_to_change_properties
  void set(String? value) => state = value;
}

/// Provider for currently selected room ID.
///
/// Updated by navigation when user selects a room.
final currentRoomIdProvider =
    NotifierProvider<CurrentRoomIdNotifier, String?>(CurrentRoomIdNotifier.new);

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
