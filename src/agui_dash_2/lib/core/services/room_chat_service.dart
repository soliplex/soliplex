import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'chat_service.dart';

/// Per-room chat provider using family modifier.
///
/// Each room gets its own independent ChatNotifier instance,
/// preserving chat history when switching between rooms.
///
/// Usage:
/// ```dart
/// // Get chat state for a specific room
/// final chatState = ref.watch(roomChatProvider('room-123'));
///
/// // Get notifier for a specific room
/// final notifier = ref.read(roomChatProvider('room-123').notifier);
/// ```
final roomChatProvider =
    StateNotifierProvider.family<ChatNotifier, ChatState, String>((ref, roomId) {
  return ChatNotifier();
});

/// Provider for the currently selected room ID.
///
/// This should be set when the user selects a room.
final selectedRoomIdProvider = StateProvider<String?>((ref) => null);

/// Active chat provider - derives from the selected room.
///
/// Returns the ChatState for the currently selected room.
/// Returns an empty ChatState if no room is selected.
///
/// Usage:
/// ```dart
/// // In widgets - automatically updates when room changes
/// final chatState = ref.watch(activeChatProvider);
///
/// // Get the active notifier
/// final notifier = ref.read(activeChatNotifierProvider);
/// ```
final activeChatProvider = Provider<ChatState>((ref) {
  final selectedRoomId = ref.watch(selectedRoomIdProvider);
  if (selectedRoomId == null) {
    return const ChatState();
  }
  return ref.watch(roomChatProvider(selectedRoomId));
});

/// Active chat notifier provider - returns the notifier for the selected room.
///
/// Returns null if no room is selected.
final activeChatNotifierProvider = Provider<ChatNotifier?>((ref) {
  final selectedRoomId = ref.watch(selectedRoomIdProvider);
  if (selectedRoomId == null) {
    return null;
  }
  return ref.read(roomChatProvider(selectedRoomId).notifier);
});

/// Helper class for room chat operations.
///
/// Provides convenience methods for common room chat operations.
class RoomChatHelper {
  final Ref ref;

  RoomChatHelper(this.ref);

  /// Get the chat notifier for a specific room.
  ChatNotifier getNotifier(String roomId) {
    return ref.read(roomChatProvider(roomId).notifier);
  }

  /// Get the chat state for a specific room.
  ChatState getState(String roomId) {
    return ref.read(roomChatProvider(roomId));
  }

  /// Get the active room's notifier (if any).
  ChatNotifier? get activeNotifier {
    return ref.read(activeChatNotifierProvider);
  }

  /// Get the active room's state.
  ChatState get activeState {
    return ref.read(activeChatProvider);
  }

  /// Select a room and return its notifier.
  ChatNotifier selectRoom(String roomId) {
    ref.read(selectedRoomIdProvider.notifier).state = roomId;
    return getNotifier(roomId);
  }

  /// Clear the selected room.
  void clearSelection() {
    ref.read(selectedRoomIdProvider.notifier).state = null;
  }

  /// Check if a room has messages.
  bool hasMessages(String roomId) {
    return ref.read(roomChatProvider(roomId)).messages.isNotEmpty;
  }

  /// Clear messages for a specific room.
  void clearRoom(String roomId) {
    ref.read(roomChatProvider(roomId).notifier).clearMessages();
  }
}

/// Provider for RoomChatHelper.
final roomChatHelperProvider = Provider<RoomChatHelper>((ref) {
  return RoomChatHelper(ref);
});
