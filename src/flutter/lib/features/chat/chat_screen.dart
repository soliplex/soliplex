import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex/app_shell.dart'; // For extension methods (Inspector)
import 'package:soliplex/core/controllers/session_lifecycle_controller.dart';
import 'package:soliplex/core/models/layout_mode.dart';
import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/services/rooms_service.dart';
import 'package:soliplex/features/chat/controllers/chat_screen_controller.dart';
import 'package:soliplex/features/keyboard/keyboard_shortcuts_help_dialog.dart';
import 'package:soliplex/features/keyboard/keyboard_shortcuts_widget.dart';
import 'package:soliplex/features/layouts/canvas_layout.dart';
import 'package:soliplex/features/layouts/standard_layout.dart';
import 'package:soliplex/features/layouts/threecol_layout.dart';
import 'package:soliplex/features/notes/notes_dialog.dart';
import 'package:soliplex/features/room/room_info_drawer.dart';

/// Main chat screen widget - acts as app shell with layout switching.
///
/// Manages:
/// - Layout mode switching
/// - App bar with controls
/// - Synchronizing Route State via ChatScreenController
class ChatScreen extends ConsumerWidget {
  const ChatScreen({super.key, this.roomId});
  final String? roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Sync Provider -> URL (e.g. when default room is selected)
    ref.listen(selectedRoomProvider, (previous, next) {
      if (next != null && next != roomId) {
        context.go('/chat/$next');
      }
    });

    // 1. Ensure Session Lifecycle is active
    ref.watch(sessionLifecycleProvider);

    // 2. Synchronize Route State (URL -> Provider/Connection)
    final state = ref.watch(
      chatScreenControllerProvider(ChatRouteParams(roomId: roomId)),
    );

    return state.when(
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, st) =>
          Scaffold(body: Center(child: Text('Error loading chat: $e'))),
      data: (_) => _buildScaffold(context, ref),
    );
  }

  Widget _buildScaffold(BuildContext context, WidgetRef ref) {
    final layoutMode = ref.watch(layoutModeProvider);
    final connectionManager = ref.watch(connectionManagerProvider);
    final selectedRoom = ref.watch(selectedRoomProvider);
    final selectedRoomData = ref.watch(selectedRoomDataProvider);

    // Simple responsive check (should match AppScaffold)
    final isDesktop = MediaQuery.of(context).size.width > 800;

    return KeyboardShortcutsWidget(
      child: Scaffold(
        appBar: AppBar(
          leading: !isDesktop
              ? IconButton(
                  icon: const Icon(Icons.menu),
                  onPressed: () {
                    Scaffold.of(context).openDrawer();
                  },
                )
              : null,
          title: Text(selectedRoomData?.name ?? 'Chat'),
          actions: [
            _buildLayoutModeSelector(ref, layoutMode),
            const SizedBox(width: 8),
            if (selectedRoomData != null)
              IconButton(
                icon: const Icon(Icons.info_outline),
                tooltip: 'Room info',
                onPressed: () => RoomInfoDrawer.show(context, selectedRoomData),
              ),
            if (selectedRoom != null && !kIsWeb)
              IconButton(
                icon: const Icon(Icons.note_alt_outlined),
                tooltip: 'Room notes',
                onPressed: () => NotesDialog.show(context, selectedRoom),
              ),
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh rooms',
              onPressed: () => ref.read(roomsProvider.notifier).fetchRooms(),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Clear chat',
              onPressed: () {
                if (selectedRoom != null) {
                  connectionManager.clearMessages(selectedRoom);
                }
              },
            ),
            IconButton(
              icon: const Icon(Icons.keyboard_outlined),
              tooltip: 'Keyboard shortcuts',
              onPressed: () =>
                  KeyboardShortcutsHelpDialog.show(context: context),
            ),
            IconButton(
              icon: const Icon(Icons.bug_report_outlined),
              tooltip: 'Network inspector',
              onPressed: () => context.showNetworkInspector(),
            ),
          ],
        ),
        body: _buildLayout(layoutMode),
      ),
    );
  }

  Widget _buildLayoutModeSelector(WidgetRef ref, LayoutMode currentMode) {
    return SegmentedButton<LayoutMode>(
      segments: LayoutMode.values.map((mode) {
        return ButtonSegment(
          value: mode,
          icon: Icon(mode.icon, size: 18),
          tooltip: mode.displayName,
        );
      }).toList(),
      selected: {currentMode},
      onSelectionChanged: (Set<LayoutMode> modes) {
        ref.read(layoutModeProvider.notifier).state = modes.first;
      },
      showSelectedIcon: false,
      style: ButtonStyle(
        visualDensity: VisualDensity.compact,
        padding: WidgetStateProperty.all(
          const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
    );
  }

  Widget _buildLayout(LayoutMode mode) {
    switch (mode) {
      case LayoutMode.standard:
        return StandardLayout(roomId: roomId);
      case LayoutMode.canvas:
        return CanvasLayout(roomId: roomId);
      case LayoutMode.threecol:
        return ThreeColumnLayout(roomId: roomId);
    }
  }
}
