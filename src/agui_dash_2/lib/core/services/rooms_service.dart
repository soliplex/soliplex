import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/room_models.dart';
import '../providers/app_providers.dart';
import '../utils/api_constants.dart';
import '../utils/url_builder.dart';
import 'auth_manager.dart';

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
  final AuthManager? _authManager;
  String? _serverId;
  UrlBuilder _urlBuilder = UrlBuilder(ApiConstants.defaultServerUrl);

  RoomsNotifier({http.Client? httpClient, AuthManager? authManager})
    : _httpClient = httpClient ?? http.Client(),
      _authManager = authManager,
      super(const RoomsState());

  /// Update the server URL and ID.
  ///
  /// Uses [UrlBuilder] for consistent URL normalization.
  void setServerUrl(String serverUrl, {String? serverId}) {
    _urlBuilder = UrlBuilder(serverUrl);
    _serverId = serverId;
  }

  /// Get the URL builder for constructing API endpoints.
  UrlBuilder get urlBuilder => _urlBuilder;

  /// Fetch available rooms from the server.
  Future<void> fetchRooms() async {
    state = state.copyWith(isLoading: true, error: null);

    try {
      // Build headers with auth token if available
      final headers = <String, String>{'Accept': 'application/json'};
      if (_authManager != null && _serverId != null) {
        final authHeaders = await _authManager.getAuthHeaders(_serverId!);
        headers.addAll(authHeaders);
        debugPrint('Rooms: Using auth headers for server $_serverId');
      }

      final response = await _httpClient.get(
        _urlBuilder.rooms(),
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
///
/// Watches [currentServerFromAppStateProvider] to auto-refresh rooms when server changes.
final roomsProvider = StateNotifierProvider<RoomsNotifier, RoomsState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  final authManager = ref.read(authManagerProvider);

  final notifier = RoomsNotifier(authManager: authManager);

  if (server != null) {
    notifier.setServerUrl(server.url, serverId: server.id);
    notifier.fetchRooms();
  }

  return notifier;
});

/// Provider for the currently selected room ID.
///
/// Resets to null when [currentServerFromAppStateProvider] changes.
final selectedRoomProvider = StateProvider<String?>((ref) {
  // Watch server - when it changes, this provider rebuilds and returns null
  ref.watch(currentServerFromAppStateProvider);
  return null;
});

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
