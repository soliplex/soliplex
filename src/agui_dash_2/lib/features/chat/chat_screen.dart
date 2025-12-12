import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app_shell.dart';
import '../../core/models/layout_mode.dart';
import '../../core/providers/app_providers.dart';
import '../../core/providers/panel_providers.dart';
import '../../core/network/connection_manager.dart';
import '../../core/services/feedback_service.dart';
import '../../core/services/markdown_hooks.dart';
import '../../core/services/rooms_service.dart';
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
/// - Room selection and ConnectionManager configuration
/// - Layout mode switching
/// - App bar with controls
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  /// Track the current server URL to detect changes.
  String? _lastServerUrl;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeMarkdownHooks();
      _initializeConnectionManager();
      _fetchRoomsAndSelectDefault();
      _setupServerChangeListener();
      _setupAuthStateListener();
    });
  }

  /// Set up a listener for server changes.
  ///
  /// When the server changes (user switches to a different server):
  /// 1. Clear the selected room (old room ID is invalid for new server)
  /// 2. Reinitialize ConnectionManager with new server URL
  /// 3. Fetch rooms from the new server
  void _setupServerChangeListener() {
    final server = ref.read(currentServerFromAppStateProvider);
    _lastServerUrl = server?.url;

    ref.listenManual(currentServerFromAppStateProvider, (previous, next) async {
      if (next?.url != _lastServerUrl && next != null) {
        debugPrint('Server changed: $_lastServerUrl -> ${next.url}');
        _lastServerUrl = next.url;

        // Clear selected room - old room ID is invalid for new server
        ref.read(selectedRoomProvider.notifier).state = null;

        // Reinitialize ConnectionManager immediately
        _initializeConnectionManager();

        // Wait for providers to settle before fetching rooms
        // This prevents race conditions with provider invalidation
        await Future.microtask(() {});

        if (mounted) {
          _fetchRoomsAndSelectDefault();
        }
      }
    });
  }

  /// Set up a listener for auth state changes.
  ///
  /// When auth completes (transition to AppStateReady):
  /// 1. Reinitialize ConnectionManager with auth headers
  /// 2. Fetch rooms (may need auth for some endpoints)
  void _setupAuthStateListener() {
    ref.listenManual(appStateStreamProvider, (previous, next) async {
      final prevState = previous?.valueOrNull;
      final nextState = next.valueOrNull;

      // Check if we just transitioned to authenticated state
      final wasNotReady = prevState is! AppStateReady;
      final isNowReady = nextState is AppStateReady;

      if (wasNotReady && isNowReady) {
        debugPrint('Auth completed - reinitializing ConnectionManager with auth headers');

        // Reinitialize ConnectionManager with auth headers
        await _initializeConnectionManager();

        if (mounted) {
          // Refresh rooms in case auth changed what we can access
          _fetchRoomsAndSelectDefault();
        }
      }
    });
  }

  /// Initialize markdown hooks with default behaviors.
  void _initializeMarkdownHooks() {
    final hooks = ref.read(markdownHooksProvider);

    hooks.onLinkTap ??= (href, text, messageId) {
      if (href != null) {
        launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
      }
    };

    hooks.onImageLoad ??= (imageUrl, messageId, state) {
      debugPrint('Image load [$messageId]: $imageUrl -> ${state.name}');
    };

    hooks.onAllImagesLoaded ??= (messageId) {
      debugPrint('All images loaded for message: $messageId');
    };

    hooks.onCodeCopy ??= (code, language, messageId) {
      debugPrint('Code copied [$messageId]: ${language ?? 'unknown'} (${code.length} chars)');
    };
  }

  /// Initialize ConnectionManager with the current server.
  Future<void> _initializeConnectionManager() async {
    final server = ref.read(currentServerFromAppStateProvider);
    debugPrint('_initializeConnectionManager: server=${server?.url}, id=${server?.id}');
    if (server == null) return;

    // Get auth headers if available
    Map<String, String>? headers;
    try {
      final authManager = ref.read(authManagerProvider);
      headers = await authManager.getAuthHeaders(server.id);
      debugPrint('_initializeConnectionManager: got headers: ${headers.keys.toList()}');
    } catch (e) {
      debugPrint('Failed to get auth headers: $e');
    }

    if (!mounted) return;

    // Configure ConnectionManager with server URL
    final connectionManager = ref.read(connectionManagerProvider);
    debugPrint('_initializeConnectionManager: calling switchServer with ${headers?.isNotEmpty == true ? "auth" : "no auth"}');
    connectionManager.switchServer(server.url, headers: headers);
  }

  /// Fetch rooms and select the first one by default.
  Future<void> _fetchRoomsAndSelectDefault() async {
    if (!mounted) return;

    final server = ref.read(currentServerFromAppStateProvider);
    if (server == null) return;

    // Set server URL and fetch rooms
    // Note: We re-read the notifier after async operations because the provider
    // may be invalidated during the fetch (e.g., during server switch).
    ref.read(roomsProvider.notifier).setServerUrl(server.url, serverId: server.id);

    try {
      await ref.read(roomsProvider.notifier).fetchRooms();
    } catch (e) {
      // Provider may have been disposed during fetch - this is expected during server switch
      debugPrint('Rooms fetch interrupted (likely server switch): $e');
      return;
    }

    if (!mounted) return;

    final rooms = ref.read(roomsProvider).rooms;
    final selectedRoom = ref.read(selectedRoomProvider);
    if (selectedRoom == null && rooms.isNotEmpty) {
      ref.read(selectedRoomProvider.notifier).state = rooms.first.id;
    }

    // Initialize feedback service for selected room
    final currentRoom = ref.read(selectedRoomProvider);
    if (mounted && currentRoom != null) {
      ref.read(feedbackProvider.notifier).initialize(currentRoom);
    }
  }

  /// Handle room change from dropdown.
  Future<void> _onRoomChanged(String? roomId) async {
    if (roomId == null || !mounted) return;

    // Stop any active activity indicator from previous room
    ref.read(activityStatusProvider.notifier).stopActivity();

    // Switch room in ConnectionManager
    final connectionManager = ref.read(connectionManagerProvider);
    await connectionManager.switchRoom(roomId);

    // Update selected room state
    ref.read(selectedRoomProvider.notifier).state = roomId;

    // Initialize feedback service for new room
    if (mounted) {
      ref.read(feedbackProvider.notifier).initialize(roomId);
    }
  }

  @override
  Widget build(BuildContext context) {
    final layoutMode = ref.watch(layoutModeProvider);
    final connectionManager = ref.watch(connectionManagerProvider);
    final roomsState = ref.watch(roomsProvider);
    final selectedRoom = ref.watch(selectedRoomProvider);
    final selectedRoomData = ref.watch(selectedRoomDataProvider);

    // Determine connection state from ConnectionManager
    final isConfigured = connectionManager.isConfigured;
    final activeSession = selectedRoom != null
        ? connectionManager.getSession(selectedRoom)
        : null;
    final isStreaming = activeSession?.isStreaming ?? false;

    return KeyboardShortcutsWidget(
      child: Scaffold(
        appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildConnectionIndicator(isConfigured, isStreaming),
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
              if (selectedRoom != null) {
                connectionManager.clearMessages(selectedRoom);
              }
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

  Widget _buildConnectionIndicator(bool isConfigured, bool isStreaming) {
    Color color;
    String tooltip;

    if (isStreaming) {
      color = Colors.blue;
      tooltip = 'Streaming';
    } else if (isConfigured) {
      color = Colors.green;
      tooltip = 'Connected';
    } else {
      color = Colors.grey;
      tooltip = 'Not configured';
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
        value: selectedRoom,
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
    final currentServer = ref.watch(currentServerFromAppStateProvider);
    final appStateAsync = ref.watch(appStateStreamProvider);
    final appState = appStateAsync.valueOrNull;

    return PopupMenuButton<String>(
      icon: const Icon(Icons.dns_outlined),
      tooltip: 'Server options',
      itemBuilder: (context) => [
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
              if (appState is AppStateReady && appState.userName != null) ...[
                const SizedBox(height: 2),
                Text(
                  appState.userName!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        const PopupMenuDivider(),
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

    if (!mounted) return;

    if (confirmed == true) {
      final appStateManager = ref.read(appStateManagerProvider);
      await appStateManager.clearServer();

      if (!mounted) return;

      ref.read(appInitializedProvider.notifier).state = false;
    }
  }
}
