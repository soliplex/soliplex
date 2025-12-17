import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/document_model.dart';
import 'package:soliplex/core/models/room_models.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/utils/api_constants.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/url_builder.dart';

// Re-export Room model for convenience
export '../models/room_models.dart';

/// State for rooms list.
class RoomsState {
  const RoomsState({this.rooms = const [], this.isLoading = false, this.error});
  final List<Room> rooms;
  final bool isLoading;
  final String? error;

  RoomsState copyWith({List<Room>? rooms, bool? isLoading, String? error}) {
    return RoomsState(
      rooms: rooms ?? this.rooms,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// Notifier for managing rooms state.
///
/// Uses NetworkTransportLayer for:
/// - Automatic auth header injection
/// - 401 retry with header refresh
/// - Network Inspector visibility
class RoomsNotifier extends StateNotifier<RoomsState> {
  RoomsNotifier({NetworkTransportLayer? transportLayer})
    : _transportLayer = transportLayer,
      super(const RoomsState());
  NetworkTransportLayer? _transportLayer;
  UrlBuilder _urlBuilder = UrlBuilder(ApiConstants.defaultServerUrl);

  /// Update the transport layer and URL builder.
  ///
  /// Called when server changes to update the network layer.
  void setTransportLayer(
    NetworkTransportLayer? transportLayer,
    String serverUrl,
  ) {
    _transportLayer = transportLayer;
    _urlBuilder = UrlBuilder(serverUrl);
  }

  /// Get the URL builder for constructing API endpoints.
  UrlBuilder get urlBuilder => _urlBuilder;

  /// Fetch available rooms from the server.
  Future<void> fetchRooms() async {
    if (_transportLayer == null) {
      DebugLog.network('Rooms: No transport layer available');
      state = state.copyWith(
        isLoading: false,
        error: 'No transport layer configured',
      );
      return;
    }

    state = state.copyWith(isLoading: true);

    try {
      final response = await _transportLayer!.get(_urlBuilder.rooms());

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
              .map(
                (entry) => Room.fromJson(entry.value as Map<String, dynamic>),
              )
              .toList();
        }
      } else {
        throw Exception('Unexpected response format');
      }

      DebugLog.agui('Rooms: Fetched ${rooms.length} rooms');
      state = state.copyWith(rooms: rooms, isLoading: false);
    } on Object catch (e) {
      DebugLog.error('Rooms: Error fetching rooms: $e');
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  /// Fetch documents for a given room from the server.
  Future<List<Document>> fetchDocuments(String roomId) async {
    if (_transportLayer == null) {
      DebugLog.network('Rooms: No transport layer available for documents');
      throw Exception(
        'No transport layer configured',
      );
    }

    try {
      final response = await _transportLayer!.get(
        _urlBuilder.roomDocuments(roomId),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to fetch documents: ${response.statusCode}');
      }

      final data = jsonDecode(response.body);
      if (data is Map<String, dynamic> && data.containsKey('document_set')) {
        final documentSet = data['document_set'] as Map<String, dynamic>;
        return documentSet.values
            .map((d) => Document.fromJson(d as Map<String, dynamic>))
            .toList();
      } else {
        throw Exception('Unexpected response format for documents');
      }
    } on Object catch (e) {
      DebugLog.error('Rooms: Error fetching documents: $e');
      rethrow;
    }
  }

  /// Refresh rooms list.
  Future<void> refresh() => fetchRooms();
}

/// Provider for rooms state.
///
/// Watches [currentServerFromAppStateProvider] to reset when server changes.
/// The transport layer and fetch are triggered by ChatScreen after
/// ConnectionManager is initialized (which registers the transport layer).
///
/// Uses NetworkTransportLayer for:
/// - Automatic auth header injection
/// - 401 retry with header refresh
/// - Network Inspector visibility
final roomsProvider = StateNotifierProvider<RoomsNotifier, RoomsState>((ref) {
  // Watch server changes to reset state when server changes
  ref.watch(currentServerFromAppStateProvider);

  // Don't auto-fetch here - ChatScreen._fetchRoomsAndSelectDefault() handles
  // setting the transport layer and fetching after ConnectionManager is ready.
  return RoomsNotifier();
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
/// Returns the full Room object for the selected room, or null if no room
/// is selected or the room data hasn't been loaded yet.
final selectedRoomDataProvider = Provider<Room?>((ref) {
  final selectedRoomId = ref.watch(selectedRoomProvider);
  if (selectedRoomId == null) return null;

  final roomsState = ref.watch(roomsProvider);
  try {
    return roomsState.rooms.firstWhere((r) => r.id == selectedRoomId);
  } on Object catch (_) {
    return null;
  }
});
