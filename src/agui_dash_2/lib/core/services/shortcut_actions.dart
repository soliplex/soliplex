import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/layout_mode.dart';
import 'chat_search_service.dart';
import 'rooms_service.dart';

// Forward declaration - will be imported when help dialog is created
typedef ShowHelpDialogCallback = void Function(BuildContext context);

/// Centralized action handlers for keyboard shortcuts.
///
/// Provides a clean separation between shortcut registration and action execution.
/// Each action is identified by a string and routed to the appropriate handler.
///
/// Note: Some actions like 'paste' need local state (TextEditingController) and
/// are handled by child widgets. They are excluded from centralized handling
/// but still registered in the service for help display.
class ShortcutActions {
  /// Callback to show the help dialog (set by KeyboardShortcutsWidget).
  static ShowHelpDialogCallback? showHelpDialog;

  /// Execute an action by its identifier.
  static void execute(WidgetRef ref, String action, BuildContext context) {
    // Room navigation by index
    if (action.startsWith('room_') && action.length == 6) {
      final digit = int.tryParse(action.substring(5));
      if (digit != null && digit >= 1 && digit <= 9) {
        _switchToRoomByIndex(ref, digit - 1);
        return;
      }
    }

    switch (action) {
      // Navigation
      case 'room_prev':
        _switchRoomRelative(ref, -1);
        break;
      case 'room_next':
        _switchRoomRelative(ref, 1);
        break;

      // View
      case 'layout_standard':
        ref.read(layoutModeProvider.notifier).state = LayoutMode.standard;
        break;
      case 'layout_canvas':
        ref.read(layoutModeProvider.notifier).state = LayoutMode.canvas;
        break;
      case 'layout_threecol':
        ref.read(layoutModeProvider.notifier).state = LayoutMode.threecol;
        break;

      // General
      case 'show_help':
        showHelpDialog?.call(context);
        break;

      // Editing - search is centralized, paste is handled locally
      case 'search':
        ref.read(chatSearchProvider.notifier).openSearch();
        break;

      default:
        debugPrint('ShortcutActions: Unknown action "$action"');
    }
  }

  /// Switch to a room by its index in the room list.
  static void _switchToRoomByIndex(WidgetRef ref, int index) {
    final roomsState = ref.read(roomsProvider);
    final rooms = roomsState.rooms;

    if (index >= 0 && index < rooms.length) {
      ref.read(selectedRoomProvider.notifier).state = rooms[index].id;
    }
  }

  /// Switch to the previous or next room.
  static void _switchRoomRelative(WidgetRef ref, int delta) {
    final roomsState = ref.read(roomsProvider);
    final rooms = roomsState.rooms;

    if (rooms.isEmpty) return;

    final currentId = ref.read(selectedRoomProvider);
    int currentIndex = rooms.indexWhere((r) => r.id == currentId);

    // If no room selected, start from beginning or end
    if (currentIndex == -1) {
      currentIndex = delta > 0 ? -1 : rooms.length;
    }

    final newIndex = (currentIndex + delta).clamp(0, rooms.length - 1);
    ref.read(selectedRoomProvider.notifier).state = rooms[newIndex].id;
  }
}
