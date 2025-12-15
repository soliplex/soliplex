import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/models/endpoint_models.dart'; // Import EndpointModels
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/connection_registry.dart'; // Import connectionRegistryProvider
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/services/endpoint_config_service.dart';
import 'package:soliplex/core/services/markdown_hooks.dart';
import 'package:soliplex/core/services/rooms_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:url_launcher/url_launcher.dart';

/// Controller that manages the lifecycle of the chat session.
///
/// Responsibilities:
/// - Listens to AppState changes (Server/Auth).
/// - Configures ConnectionManager when a server is ready.
/// - Fetching rooms.
/// - Selects a default room if none selected.
/// - Initializes global MarkdownHooks.
class SessionLifecycleController extends AsyncNotifier<void> {
  @override
  Future<void> build() async {
    // Initialize hooks once
    _initializeMarkdownHooks();

    // Watch app state to react to server/auth changes
    final appState = await ref.watch(appStateStreamProvider.future);

    if (appState is AppStateReady) {
      await _initializeSession(appState.server);
    }
  }

  void _initializeMarkdownHooks() {
    final hooks = ref.read(markdownHooksProvider);

    hooks.onLinkTap ??= (href, text, messageId) {
      if (href != null) {
        launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
      }
    };

    hooks.onImageLoad ??= (imageUrl, messageId, state) {
      DebugLog.service('Image load [$messageId]: $imageUrl -> ${state.name}');
    };

    hooks.onAllImagesLoaded ??= (messageId) {
      DebugLog.service('All images loaded for message: $messageId');
    };

    hooks.onCodeCopy ??= (code, language, messageId) {
      DebugLog.service(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'Code copied [$messageId]: ${language ?? 'unknown'} (${code.length} chars)',
      );
    };
  }

  Future<void> _initializeSession(ServerConnection server) async {
    final connectionManager = ref.read(connectionManagerProvider);
    final endpointService = ref.read(endpointConfigServiceProvider);

    // Prepare headers based on endpoint type
    var headers = <String, String>{};
    if (server.config is CompletionsEndpoint) {
      final apiKey = await endpointService.getApiKey(server.id);
      if (apiKey != null) {
        headers['Authorization'] = 'Bearer $apiKey';
      }
    } else {
      // AG-UI auth (OIDC or Token)
      final authManager = ref.read(authManagerProvider);
      headers = await authManager.getAuthHeaders(server.id);
    }

    final isNewServer = connectionManager.activeServerId != server.id;

    DebugLog.service(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'SessionLifecycle: Configuring connection for ${server.id} (new: $isNewServer)',
    );

    // Switch server using persistent ID.
    connectionManager.switchServer(
      server.url,
      headers: headers,
      serverId: server.id,
      config: server.config,
    );

    // If we switched servers, or if rooms are empty/error, fetch rooms.
    try {
      // Logic branch based on endpoint type
      if (server.config is CompletionsEndpoint) {
        // Completions endpoint: No rooms to fetch. Select 'default' room.
        ref.read(selectedRoomProvider.notifier).state = 'default';
        DebugLog.service('SessionLifecycle: Initialized Completions session');
      } else {
        // AG-UI endpoint: Fetch rooms
        final registry = ref.read(connectionRegistryProvider);
        final serverState = registry.getServerState(server.id);

        ref
            .read(roomsProvider.notifier)
            .setTransportLayer(serverState?.transportLayer, server.url);

        await ref.read(roomsProvider.notifier).fetchRooms();
        _selectDefaultRoom();
      }
    } on Object catch (e) {
      DebugLog.error('SessionLifecycle: Error configuring session: $e');
      // Non-fatal, UI will show error state from roomsProvider
    }
  }

  void _selectDefaultRoom() {
    final roomsState = ref.read(roomsProvider);
    final selectedRoom = ref.read(selectedRoomProvider);

    if (selectedRoom == null && roomsState.rooms.isNotEmpty) {
      DebugLog.service(
        'SessionLifecycle: Selecting default room ${roomsState.rooms.first.id}',
      );
      ref.read(selectedRoomProvider.notifier).state = roomsState.rooms.first.id;
    }
  }
}

/// Provider for the session lifecycle controller.
/// Watch this in the main chat UI to keep the session alive and managed.
final sessionLifecycleProvider =
    AsyncNotifierProvider<SessionLifecycleController, void>(() {
      return SessionLifecycleController();
    });
