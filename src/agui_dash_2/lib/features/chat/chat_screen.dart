import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app_shell.dart';
import '../../core/models/layout_mode.dart';
import '../../core/providers/panel_providers.dart';
import '../../core/services/agui_service.dart';
import '../../core/services/auth_service.dart';
import '../../core/services/feedback_service.dart';
import '../../core/services/markdown_hooks.dart';
import '../../core/services/room_chat_service.dart';
import '../../core/services/rooms_service.dart';
import '../../core/services/server_config_service.dart';
import '../../core/utils/api_constants.dart';
import '../../core/utils/url_builder.dart';
import '../layouts/standard_layout.dart';
import '../notes/notes_dialog.dart';
import '../layouts/canvas_layout.dart';
import '../layouts/threecol_layout.dart';
import '../room/capability_badges.dart';
import '../room/room_info_drawer.dart';
import '../keyboard/keyboard_shortcuts_widget.dart';
import '../keyboard/keyboard_shortcuts_help_dialog.dart';

/// Main chat screen widget - acts as app shell with layout switching.
///
/// Manages:
/// - Room selection and AG-UI configuration
/// - Layout mode switching
/// - App bar with controls
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  /// Get the URL builder for the current server.
  UrlBuilder get _urlBuilder {
    final server = ref.read(currentServerProvider);
    final url = server?.url ?? ApiConstants.defaultServerUrl;
    return UrlBuilder(url);
  }

  /// Get the server URL (bare server, no /api path).
  String get _serverUrl => _urlBuilder.serverUrl;

  @override
  void initState() {
    super.initState();
    // Fetch rooms and configure AG-UI service on startup
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeMarkdownHooks();
      _fetchRoomsAndConfigure();
    });
  }

  /// Initialize markdown hooks with default behaviors
  void _initializeMarkdownHooks() {
    final hooks = ref.read(markdownHooksProvider);

    // Default link handling: open in external browser
    hooks.onLinkTap ??= (href, text, messageId) {
      if (href != null) {
        launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
      }
    };

    // Optional: Log image load states for debugging
    hooks.onImageLoad ??= (imageUrl, messageId, state) {
      debugPrint('Image load [$messageId]: $imageUrl -> ${state.name}');
    };

    // Optional: Log when all images in a message are loaded
    hooks.onAllImagesLoaded ??= (messageId) {
      debugPrint('All images loaded for message: $messageId');
    };

    // Optional: Log code copy events
    hooks.onCodeCopy ??= (code, language, messageId) {
      debugPrint('Code copied [$messageId]: ${language ?? 'unknown'} (${code.length} chars)');
    };
  }

  Future<void> _fetchRoomsAndConfigure() async {
    // Fetch available rooms
    final roomsNotifier = ref.read(roomsProvider.notifier);
    roomsNotifier.setServerUrl(_serverUrl);
    await roomsNotifier.fetchRooms();

    // Select first room by default if none selected
    final rooms = ref.read(roomsProvider).rooms;
    final selectedRoom = ref.read(selectedRoomProvider);
    if (selectedRoom == null && rooms.isNotEmpty) {
      ref.read(selectedRoomProvider.notifier).state = rooms.first.id;
    }

    // Configure AG-UI with selected room
    await _updateAgUiConfig();
  }

  Future<void> _updateAgUiConfig() async {
    final selectedRoom = ref.read(selectedRoomProvider);
    if (selectedRoom != null) {
      // Get auth headers if available
      final authService = ref.read(authServiceProvider);
      final headers = await authService.getAuthHeaders();

      final config = AgUiServiceConfig(
        baseUrl: _serverUrl,
        roomId: selectedRoom,
        headers: headers.isNotEmpty ? headers : null,
      );

      // Store config for other providers that need it
      ref.read(agUiConfigProvider.notifier).state = config;

      // Explicitly configure the service (no auto-configuration)
      ref.read(agUiServiceProvider).configure(config);

      // Initialize feedback service for this room
      ref.read(feedbackProvider.notifier).initialize(selectedRoom);
    }
  }

  Future<void> _onRoomChanged(String? roomId) async {
    if (roomId == null) return;

    final previousRoomId = ref.read(selectedRoomProvider);

    // Stop any active activity indicator from previous room
    ref.read(activityStatusProvider.notifier).stopActivity();

    // Save current chat history to the per-room provider before switching
    if (previousRoomId != null && previousRoomId != roomId) {
      final currentMessages = ref.read(chatProvider).messages;
      if (currentMessages.isNotEmpty) {
        ref.read(roomChatProvider(previousRoomId).notifier).loadMessages(currentMessages);
      }
    }

    ref.read(selectedRoomProvider.notifier).state = roomId;
    ref.read(selectedRoomIdProvider.notifier).state = roomId;
    await _updateAgUiConfig();

    // Restore chat history from per-room provider, or clear if empty
    final savedMessages = ref.read(roomChatProvider(roomId)).messages;
    if (savedMessages.isNotEmpty) {
      ref.read(chatProvider.notifier).loadMessages(savedMessages);
    } else {
      ref.read(chatProvider.notifier).clearMessages();
    }
  }

  @override
  Widget build(BuildContext context) {
    final layoutMode = ref.watch(layoutModeProvider);
    final agUiService = ref.watch(configuredAgUiServiceProvider);
    final roomsState = ref.watch(roomsProvider);
    final selectedRoom = ref.watch(selectedRoomProvider);
    final selectedRoomData = ref.watch(selectedRoomDataProvider);

    return KeyboardShortcutsWidget(
      child: Scaffold(
        appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildConnectionIndicator(agUiService.state),
            const SizedBox(width: 8),
            Flexible(
              child: _buildRoomSelector(roomsState, selectedRoom),
            ),
            if (selectedRoomData != null) ...[
              const SizedBox(width: 8),
              CapabilityIcons(room: selectedRoomData),
            ],
            const SizedBox(width: 8),
            _buildLayoutModeSelector(layoutMode),
          ],
        ),
        actions: [
          if (selectedRoomData != null)
            IconButton(
              icon: const Icon(Icons.info_outline),
              tooltip: 'Room info',
              onPressed: () => RoomInfoDrawer.show(context, selectedRoomData),
            ),
          // Notes feature not available on web (uses local file storage)
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
              ref.read(chatProvider.notifier).clearMessages();
              ref.read(agUiServiceProvider).resetConversation();
            },
          ),
          IconButton(
            icon: const Icon(Icons.keyboard_outlined),
            tooltip: 'Keyboard shortcuts',
            onPressed: () => KeyboardShortcutsHelpDialog.show(context),
          ),
          _buildServerMenu(),
        ],
        ),
        body: _buildLayout(layoutMode),
      ),
    );
  }

  Widget _buildLayoutModeSelector(LayoutMode currentMode) {
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
        return const StandardLayout();
      case LayoutMode.canvas:
        return const CanvasLayout();
      case LayoutMode.threecol:
        return const ThreeColumnLayout();
    }
  }

  Widget _buildConnectionIndicator(AgUiConnectionState state) {
    Color color;
    String tooltip;

    switch (state) {
      case AgUiConnectionState.connected:
        color = Colors.green;
        tooltip = 'Connected';
      case AgUiConnectionState.streaming:
        color = Colors.blue;
        tooltip = 'Streaming';
      case AgUiConnectionState.connecting:
        color = Colors.orange;
        tooltip = 'Connecting...';
      case AgUiConnectionState.error:
        color = Colors.red;
        tooltip = 'Error';
      case AgUiConnectionState.disconnected:
        color = Colors.grey;
        tooltip = 'Disconnected';
    }

    return Tooltip(
      message: tooltip,
      child: Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
    );
  }

  Widget _buildRoomSelector(RoomsState roomsState, String? selectedRoom) {
    if (roomsState.isLoading) {
      return const SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }

    if (roomsState.error != null) {
      return Tooltip(
        message: 'Error: ${roomsState.error}',
        child: IconButton(
          icon: const Icon(Icons.error_outline, color: Colors.red),
          onPressed: () => ref.read(roomsProvider.notifier).fetchRooms(),
        ),
      );
    }

    if (roomsState.rooms.isEmpty) {
      return const Text(
        'No rooms',
        style: TextStyle(fontSize: 12, color: Colors.grey),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: DropdownButton<String>(
        value: selectedRoom,  // Guaranteed valid by reactive provider chain
        hint: const Text('Select room'),
        underline: const SizedBox(),
        isDense: true,
        icon: const Icon(Icons.arrow_drop_down),
        items: roomsState.rooms.map((room) {
          return DropdownMenuItem<String>(
            value: room.id,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.meeting_room, size: 16),
                const SizedBox(width: 8),
                Text(room.name),
              ],
            ),
          );
        }).toList(),
        onChanged: _onRoomChanged,
      ),
    );
  }

  Widget _buildServerMenu() {
    final currentServer = ref.watch(currentServerProvider);
    final authState = ref.watch(authStateProvider);

    return PopupMenuButton<String>(
      icon: const Icon(Icons.dns_outlined),
      tooltip: 'Server options',
      itemBuilder: (context) => [
        // Show current server info
        PopupMenuItem<String>(
          enabled: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Connected to:',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                currentServer?.label ?? 'Unknown',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              if (authState.userName != null) ...[
                const SizedBox(height: 2),
                Text(
                  authState.userName!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        const PopupMenuDivider(),
        // Switch server option
        const PopupMenuItem<String>(
          value: 'switch',
          child: Row(
            children: [
              Icon(Icons.swap_horiz, size: 20),
              SizedBox(width: 12),
              Text('Switch Server'),
            ],
          ),
        ),
        // Logout option
        const PopupMenuItem<String>(
          value: 'logout',
          child: Row(
            children: [
              Icon(Icons.logout, size: 20),
              SizedBox(width: 12),
              Text('Logout'),
            ],
          ),
        ),
      ],
      onSelected: (value) async {
        switch (value) {
          case 'switch':
            context.showServerSetup();
            break;
          case 'logout':
            await _handleLogout();
            break;
        }
      },
    );
  }

  Future<void> _handleLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text(
          'Are you sure you want to logout? You will need to reconnect to a server.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    // Check if widget is still mounted after async dialog
    if (!mounted) return;

    if (confirmed == true) {
      // Get references before any async operations that might dispose the widget
      final authService = ref.read(authServiceProvider);
      final serverConfig = ref.read(serverConfigProvider);

      // Logout from auth service
      await authService.logout();

      // Check mounted again after async operation
      if (!mounted) return;

      // Clear server config to force re-setup
      await serverConfig.clearAll();

      // Check mounted again after async operation
      if (!mounted) return;

      // Reset app initialized state to show setup screen
      ref.read(appInitializedProvider.notifier).state = false;
    }
  }
}
