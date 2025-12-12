import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/room_models.dart';
import 'auth_service.dart';

// Re-export Room model for convenience
export '../models/room_models.dart';

/// State for rooms list.
class RoomsState {
  final List<Room> rooms;
  final bool isLoading;
  final String? error;

  const RoomsState({this.rooms = const [], this.isLoading = false, this.error});

  RoomsState copyWith({List<Room>? rooms, bool? isLoading, String? error}) {
    return RoomsState(
      rooms: rooms ?? this.rooms,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// Notifier for managing rooms state.
class RoomsNotifier extends StateNotifier<RoomsState> {
  final http.Client _httpClient;
  final AuthService? _authService;
  String _serverUrl = 'http://localhost:8000';

  RoomsNotifier({http.Client? httpClient, AuthService? authService})
    : _httpClient = httpClient ?? http.Client(),
      _authService = authService,
      super(const RoomsState());

  /// Update the server URL (without /api path).
  void setServerUrl(String serverUrl) {
    // Strip trailing slash and any /api suffix
    _serverUrl = serverUrl
        .replaceAll(RegExp(r'/+$'), '')
        .replaceAll(RegExp(r'/api(/v\d+)?$'), '');
  }

  /// Get the full API base URL.
  String get _apiBaseUrl => '$_serverUrl/api/v1';

  /// Fetch available rooms from the server.
  Future<void> fetchRooms() async {
    state = state.copyWith(isLoading: true, error: null);

    try {
      // Build headers with auth token if available
      final headers = <String, String>{'Accept': 'application/json'};
      if (_authService != null) {
        final authHeaders = await _authService.getAuthHeaders();
        headers.addAll(authHeaders);
      }

      final response = await _httpClient.get(
        Uri.parse('$_apiBaseUrl/rooms'),
        headers: headers,
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to fetch rooms: ${response.statusCode}');
      }

      final data = jsonDecode(response.body);
      final List<Room> rooms;

      // Handle different response formats
      if (data is List) {
        // Array of rooms
        rooms = data
            .map((r) => Room.fromJson(r as Map<String, dynamic>))
            .toList();
      } else if (data is Map<String, dynamic>) {
        // Object with rooms array or room_ids
        if (data.containsKey('rooms')) {
          final roomsList = data['rooms'] as List;
          rooms = roomsList
              .map((r) => Room.fromJson(r as Map<String, dynamic>))
              .toList();
        } else if (data.containsKey('room_ids')) {
          // Simple list of room IDs
          final roomIds = data['room_ids'] as List;
          rooms = roomIds
              .map((id) => Room(id: id.toString(), name: id.toString()))
              .toList();
        } else {
          // Dictionary of room_id -> room_data (Soliplex format)
          rooms = data.entries
              .map((entry) => Room.fromJson(entry.value as Map<String, dynamic>))
              .toList();
        }
      } else {
        throw Exception('Unexpected response format');
      }

      debugPrint('Rooms: Fetched ${rooms.length} rooms');
      state = state.copyWith(rooms: rooms, isLoading: false);
    } catch (e) {
      debugPrint('Rooms: Error fetching rooms: $e');
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  /// Refresh rooms list.
  Future<void> refresh() => fetchRooms();
}

/// Provider for rooms state.
final roomsProvider = StateNotifierProvider<RoomsNotifier, RoomsState>((ref) {
  final authService = ref.read(authServiceProvider);
  return RoomsNotifier(authService: authService);
});

/// Provider for the currently selected room ID.
final selectedRoomProvider = StateProvider<String?>((ref) => null);

/// Provider for the currently selected room's full data.
///
/// Returns the full [Room] object for the selected room, or null if no room
/// is selected or the room data hasn't been loaded yet.
final selectedRoomDataProvider = Provider<Room?>((ref) {
  final selectedRoomId = ref.watch(selectedRoomProvider);
  if (selectedRoomId == null) return null;

  final roomsState = ref.watch(roomsProvider);
  try {
    return roomsState.rooms.firstWhere((r) => r.id == selectedRoomId);
  } catch (_) {
    return null;
  }
});
