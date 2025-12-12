import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/models/chat_models.dart';
import '../../core/models/layout_mode.dart';
import '../../core/services/agui_service.dart';
import '../../core/services/chat_service.dart';
import '../../core/services/feedback_service.dart';
import '../../core/services/markdown_hooks.dart';
import '../../core/services/rooms_service.dart';
import '../layouts/standard_layout.dart';
import '../notes/notes_dialog.dart';
import '../layouts/canvas_layout.dart';
import '../layouts/threecol_layout.dart';

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
  static const String _defaultBaseUrl = 'http://localhost:8000/api/v1';

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
    roomsNotifier.setBaseUrl(_defaultBaseUrl);
    await roomsNotifier.fetchRooms();

    // Select first room by default if none selected
    final rooms = ref.read(roomsProvider).rooms;
    final selectedRoom = ref.read(selectedRoomProvider);
    if (selectedRoom == null && rooms.isNotEmpty) {
      ref.read(selectedRoomProvider.notifier).state = rooms.first.id;
    }

    // Configure AG-UI with selected room
    _updateAgUiConfig();
  }

  void _updateAgUiConfig() {
    final selectedRoom = ref.read(selectedRoomProvider);
    if (selectedRoom != null) {
      ref.read(agUiConfigProvider.notifier).state = AgUiServiceConfig(
        baseUrl: _defaultBaseUrl,
        roomId: selectedRoom,
      );
      // Reset conversation when switching rooms
      ref.read(agUiServiceProvider).resetConversation();
      // Initialize feedback service for this room
      ref.read(feedbackProvider.notifier).initialize(selectedRoom);
    }
  }

  void _onRoomChanged(String? roomId) {
    if (roomId == null) return;

    ref.read(selectedRoomProvider.notifier).state = roomId;
    _updateAgUiConfig();

    // Clear chat when switching rooms
    ref.read(chatProvider.notifier).clearMessages();
  }

  void _addTestGenUiMessage() {
    debugPrint('TEST: _addTestGenUiMessage called');
    final chatNotifier = ref.read(chatProvider.notifier);

    chatNotifier.addGenUiMessage(
      GenUiContent(
        toolCallId: 'test-${DateTime.now().millisecondsSinceEpoch}',
        widgetName: 'InfoCard',
        data: {
          'title': 'Hello from Native Widget!',
          'subtitle': 'This widget was generated dynamically.',
          'icon': Icons.rocket_launch.codePoint,
          'color': Colors.blue.toARGB32(),
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final layoutMode = ref.watch(layoutModeProvider);
    final agUiService = ref.watch(configuredAgUiServiceProvider);
    final roomsState = ref.watch(roomsProvider);
    final selectedRoom = ref.watch(selectedRoomProvider);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Text('AG-UI Dashboard'),
            const SizedBox(width: 8),
            _buildConnectionIndicator(agUiService.state),
            const SizedBox(width: 16),
            _buildRoomSelector(roomsState, selectedRoom),
            const Spacer(),
            _buildLayoutModeSelector(layoutMode),
          ],
        ),
        actions: [
          if (selectedRoom != null)
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
            icon: const Icon(Icons.science),
            tooltip: 'Test GenUI',
            onPressed: _addTestGenUiMessage,
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Clear chat',
            onPressed: () {
              ref.read(chatProvider.notifier).clearMessages();
              ref.read(agUiServiceProvider).resetConversation();
            },
          ),
        ],
      ),
      body: _buildLayout(layoutMode),
    );
  }

  Widget _buildLayoutModeSelector(LayoutMode currentMode) {
    return SegmentedButton<LayoutMode>(
      segments: LayoutMode.values.map((mode) {
        return ButtonSegment(
          value: mode,
          icon: Icon(mode.icon, size: 18),
          label: Text(mode.displayName),
        );
      }).toList(),
      selected: {currentMode},
      onSelectionChanged: (Set<LayoutMode> modes) {
        ref.read(layoutModeProvider.notifier).state = modes.first;
      },
      style: ButtonStyle(
        visualDensity: VisualDensity.compact,
        padding: WidgetStateProperty.all(
          const EdgeInsets.symmetric(horizontal: 12),
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
}
