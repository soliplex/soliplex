import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat_models.dart';
import '../providers/app_providers.dart';
import '../services/local_tools_service.dart';
import '../utils/debug_log.dart';
import 'connection_events.dart';
import 'connection_registry.dart';
import 'room_session.dart';
import 'server_connection_state.dart';
import 'server_room_key.dart';

/// UI tool handler callback type.
typedef UiToolHandler = Future<Map<String, dynamic>> Function(
  String toolCallId,
  String toolName,
  Map<String, dynamic> args,
);

/// Local tool execution notifier callback type.
typedef LocalToolNotifier = void Function(
  String toolCallId,
  String toolName,
  String status,
);

/// Callback to refresh auth headers on 401.
typedef HeaderRefresher = Future<Map<String, String>> Function(String serverId);

/// Facade over [ConnectionRegistry] for backward compatibility.
///
/// This class provides the same API as the original ConnectionManager
/// while delegating to the multi-server ConnectionRegistry internally.
///
/// Key changes from original:
/// - `switchServer()` is now NON-DESTRUCTIVE (sessions preserved per server)
/// - Added `focusServer()` for multi-server switching
/// - All session operations delegate to registry
///
/// Handles:
/// - Session pool per server (via ConnectionRegistry)
/// - Server switching (non-destructive, preserves sessions)
/// - Room switching with state preservation
/// - Run cancellation
/// - Connection observability
class ConnectionManager extends ChangeNotifier {
  /// Connection registry for multi-server support.
  final ConnectionRegistry _registry;

  /// Callback to refresh auth headers on 401.
  final HeaderRefresher? _headerRefresher;

  /// Currently active server ID.
  String? _activeServerId;

  /// Event stream for all sessions.
  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  /// Tools that should be handled by the UI layer.
  static const _uiTools = {'canvas_render', 'genui_render'};

  /// Whether the manager has been configured with a server.
  bool get isConfigured => _activeServerId != null && _registry.hasServer(_activeServerId!);

  /// Current server URL.
  String get serverUrl => _activeServerState?.baseUrl ?? '';

  /// Current server ID.
  String? get activeServerId => _activeServerId;

  /// Currently active room ID.
  String? get activeRoomId => _registry.activeRoomId;

  /// Get the active server state, or null if none.
  ServerConnectionState? get _activeServerState =>
      _activeServerId != null ? _registry.getServerState(_activeServerId!) : null;

  /// Max backgrounded sessions before LRU eviction (delegated to registry config).
  int get maxBackgroundedSessions => 5;

  ConnectionManager({
    ConnectionRegistry? registry,
    String baseUrl = '',
    Map<String, String>? headers,
    HeaderRefresher? headerRefresher,
  }) : _registry = registry ?? ConnectionRegistry(),
       _headerRefresher = headerRefresher {
    // Listen to registry changes
    _registry.addListener(_onRegistryChanged);

    // If baseUrl provided, connect immediately (backward compat)
    if (baseUrl.isNotEmpty) {
      switchServer(baseUrl, headers: headers);
    }
  }

  void _onRegistryChanged() {
    notifyListeners();
  }

  /// Switch to a different server (NON-DESTRUCTIVE).
  ///
  /// Creates or retrieves a server connection. Sessions on other servers
  /// are preserved (not destroyed like the old implementation).
  ///
  /// Call this when the user selects a different server.
  void switchServer(String newBaseUrl, {Map<String, String>? headers}) {
    // Generate a server ID from the URL (or use provided ID)
    final serverId = _serverIdFromUrl(newBaseUrl);

    if (_activeServerId == serverId) {
      DebugLog.network('ConnectionManager: Server unchanged, skipping switch');
      return;
    }

    DebugLog.network('ConnectionManager: Switching server to $newBaseUrl (id: $serverId)');

    // Create header refresher bound to this server ID
    final serverHeaderRefresher = _headerRefresher != null
        ? () => _headerRefresher(serverId)
        : null;

    // Connect to the server (or get existing connection)
    _registry.connectServer(
      serverId,
      newBaseUrl,
      headers: headers,
      headerRefresher: serverHeaderRefresher,
    );
    _activeServerId = serverId;
    _registry.focusServer(serverId);

    notifyListeners();
  }

  /// Focus a different server by ID (for multi-server support).
  ///
  /// Unlike [switchServer], this only changes the active server
  /// without connecting to a new one.
  void focusServer(String serverId) {
    if (!_registry.hasServer(serverId)) {
      throw StateError('Server $serverId not connected. Call switchServer() first.');
    }

    if (_activeServerId == serverId) {
      return;
    }

    DebugLog.network('ConnectionManager: Focusing server $serverId');
    _activeServerId = serverId;
    _registry.focusServer(serverId);
    notifyListeners();
  }

  /// Get list of connected server IDs.
  List<String> get connectedServerIds => _registry.serverIds;

  /// Check if a server is connected.
  bool hasServer(String serverId) => _registry.hasServer(serverId);

  /// Generate a server ID from a URL.
  String _serverIdFromUrl(String url) {
    // Extract host:port as ID (e.g., "localhost:8080")
    final uri = Uri.parse(url);
    return '${uri.host}:${uri.port}';
  }

  // Getters
  RoomSession? get activeSession {
    final roomId = activeRoomId;
    final serverId = _activeServerId;
    if (roomId == null || serverId == null) return null;
    return _registry.getExistingSession(ServerRoomKey(serverId: serverId, roomId: roomId));
  }

  /// Stream of connection events for observability.
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Get all active connections info (for current server).
  List<ConnectionInfo> get activeConnections {
    final serverState = _activeServerState;
    if (serverState == null) return [];
    return serverState.sessions.values.map((s) => s.connectionInfo).toList();
  }

  /// Get connection info for a specific room (on current server).
  ConnectionInfo? getConnectionInfo(String roomId) {
    if (_activeServerId == null) return null;
    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    return session?.connectionInfo;
  }

  /// Get or create a session for a room (on current server).
  RoomSession getSession(String roomId) {
    if (_activeServerId == null) {
      throw StateError('No server configured. Call switchServer() first.');
    }

    final key = ServerRoomKey(serverId: _activeServerId!, roomId: roomId);
    final session = _registry.getSession(key);

    // Forward session events (subscribe if new)
    _subscribeToSession(session);

    return session;
  }

  /// Track subscriptions for proper cleanup.
  final Map<String, StreamSubscription<ConnectionEvent>> _sessionSubscriptions = {};

  void _subscribeToSession(RoomSession session) {
    final sessionKey = '${session.serverId}:${session.roomId}';
    if (_sessionSubscriptions.containsKey(sessionKey)) return;

    _sessionSubscriptions[sessionKey] = session.events.listen(_eventController.add);
  }

  /// Get messages for a room (reads from RoomSession).
  List<ChatMessage> getMessages(String roomId) {
    return getSession(roomId).messages;
  }

  /// Get message stream for a room (for UI subscription).
  Stream<List<ChatMessage>> getMessageStream(String roomId) {
    return getSession(roomId).messageStream;
  }

  /// Check if agent is typing in a room.
  bool isAgentTyping(String roomId) {
    if (_activeServerId == null) return false;
    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    return session?.isAgentTyping ?? false;
  }

  /// Switch to a different room (on current server).
  ///
  /// Suspends the current session (if any) and resumes or creates the new one.
  Future<RoomSession> switchRoom(String newRoomId) async {
    if (_activeServerId == null) {
      throw StateError('No server configured. Call switchServer() first.');
    }

    final key = ServerRoomKey(serverId: _activeServerId!, roomId: newRoomId);
    final previousRoomId = _registry.activeRoomId;

    if (previousRoomId == newRoomId) {
      // Already on this room
      return getSession(newRoomId);
    }

    DebugLog.network('ConnectionManager: Switching from $previousRoomId to $newRoomId');

    // Use registry's setActive which handles suspend/resume
    _registry.setActive(key);

    // Get the session and subscribe
    final newSession = getSession(newRoomId);

    _eventController.add(RoomSwitchedEvent(
      serverId: _activeServerId,
      roomId: newRoomId,
      previousRoomId: previousRoomId,
    ));

    notifyListeners();
    return newSession;
  }

  /// Initialize a session for a room (create thread).
  Future<void> initializeSession(String roomId) async {
    final serverState = _activeServerState;
    if (serverState == null) {
      throw StateError('No server configured. Call switchServer() first.');
    }

    final session = getSession(roomId);
    if (session.threadId == null) {
      await session.initialize(transportLayer: serverState.transportLayer);
      notifyListeners();
    }
  }

  /// Chat in a room.
  ///
  /// Handles the full conversation flow including tool execution.
  /// Events are processed by RoomSession and messages are updated automatically.
  /// Subscribe to getMessageStream(roomId) to receive message updates.
  ///
  /// [uiToolHandler] is called for canvas_render and genui_render tools
  /// which need access to UI state.
  ///
  /// [onLocalToolExecution] is called when local tools start/complete.
  Future<void> chat({
    required String roomId,
    required String userMessage,
    required LocalToolsService localToolsService,
    UiToolHandler? uiToolHandler,
    LocalToolNotifier? onLocalToolExecution,
    CanvasCallback? onCanvasUpdate,
    ContextCallback? onContextUpdate,
    ActivityCallback? onActivityUpdate,
    Map<String, dynamic>? state,
  }) async {
    if (!isConfigured) {
      throw StateError('ConnectionManager not configured. Call switchServer() first.');
    }

    final session = getSession(roomId);

    // Set up callbacks for side effects
    session.onCanvasUpdate = onCanvasUpdate;
    session.onContextUpdate = onContextUpdate;
    session.onActivityUpdate = onActivityUpdate;

    // Initialize if needed
    if (session.threadId == null) {
      await initializeSession(roomId);
    }

    // Add user message to session
    session.addUserMessage(userMessage);

    // Register tools
    _registerTools(session, localToolsService, uiToolHandler, onLocalToolExecution);

    // Listen to event streams - session processes events internally
    StreamSubscription<ag_ui.BaseEvent>? stepsSub;

    try {
      stepsSub = session.stepsStream?.listen((event) {
        session.processEvent(event);
      });

      // Create user message for AG-UI
      final userMsg = ag_ui.UserMessage(
        id: 'user-${DateTime.now().millisecondsSinceEpoch}',
        content: userMessage,
      );

      // Start run
      var toolResults = await session.startRun(
        messages: [userMsg],
        state: state,
      );

      // Tool result loop
      while (toolResults.isNotEmpty) {
        DebugLog.network('ConnectionManager: Processing ${toolResults.length} tool results');

        final newRunId = await session.createRun();
        toolResults = await session.sendToolResults(
          runId: newRunId,
          toolMessages: toolResults,
        );
      }
    } finally {
      await stepsSub?.cancel();
    }
  }

  /// Cancel the active run for a room.
  Future<void> cancelRun(String roomId) async {
    if (_activeServerId == null) {
      DebugLog.network('ConnectionManager: No server configured');
      return;
    }

    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    if (session == null) {
      DebugLog.network('ConnectionManager: No session for room $roomId');
      return;
    }

    await session.cancelActiveRun();
    notifyListeners();
  }

  /// Clear messages for a room.
  void clearMessages(String roomId) {
    if (_activeServerId == null) return;
    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    session?.clearMessages();
    notifyListeners();
  }

  /// Load messages for a room (for history restoration).
  void loadMessages(String roomId, List<ChatMessage> messages) {
    final session = getSession(roomId);
    session.loadMessages(messages);
  }

  /// Register tools with a session.
  void _registerTools(
    RoomSession session,
    LocalToolsService localToolsService,
    UiToolHandler? uiToolHandler,
    LocalToolNotifier? onLocalToolExecution,
  ) {
    for (final toolDef in localToolsService.tools) {
      final agTool = ag_ui.Tool(
        name: toolDef.name,
        description: toolDef.description,
        parameters: toolDef.parameters,
      );

      final isFireAndForget = _uiTools.contains(toolDef.name);

      session.addTool(agTool, (call) async {
        Map<String, dynamic> args = {};
        try {
          if (call.function.arguments.isNotEmpty) {
            args = jsonDecode(call.function.arguments) as Map<String, dynamic>;
          }
        } catch (e) {
          DebugLog.network('ConnectionManager: Failed to parse tool args: $e');
        }

        // UI tools (canvas_render, genui_render)
        if (_uiTools.contains(call.function.name) && uiToolHandler != null) {
          session.handleLocalToolExecution(call.id, call.function.name, 'executing');
          try {
            final result = await uiToolHandler(call.id, call.function.name, args);
            session.handleLocalToolExecution(call.id, call.function.name, 'completed');
            return jsonEncode(result);
          } catch (e) {
            session.handleLocalToolExecution(call.id, call.function.name, 'error: $e');
            return jsonEncode({'error': e.toString()});
          }
        }

        // Regular tools
        session.handleLocalToolExecution(call.id, call.function.name, 'executing');
        final result = await localToolsService.executeTool(
          call.id,
          call.function.name,
          args,
        );

        if (result.success) {
          session.handleLocalToolExecution(call.id, call.function.name, 'completed');
          return jsonEncode(result.result);
        } else {
          session.handleLocalToolExecution(call.id, call.function.name, 'error');
          return jsonEncode({'error': result.error});
        }
      }, fireAndForget: isFireAndForget);
    }
  }

  /// Dispose a specific room session (on current server).
  void disposeSession(String roomId) {
    final serverState = _activeServerState;
    if (serverState == null) return;

    serverState.disposeSession(roomId);
    notifyListeners();
  }

  /// Remove a server and all its sessions.
  void removeServer(String serverId) {
    _registry.removeServer(serverId);
    if (_activeServerId == serverId) {
      _activeServerId = null;
    }
    notifyListeners();
  }

  /// Dispose all sessions and the manager.
  @override
  void dispose() {
    _registry.removeListener(_onRegistryChanged);

    // Cancel all session subscriptions
    for (final subscription in _sessionSubscriptions.values) {
      subscription.cancel();
    }
    _sessionSubscriptions.clear();

    _eventController.close();
    // Note: Don't dispose registry here - it may be shared
    super.dispose();
  }
}

/// Singleton provider for ConnectionManager.
/// Persists for app lifetime - NOT server-scoped.
final connectionManagerProvider = ChangeNotifierProvider<ConnectionManager>((ref) {
  final registry = ref.read(connectionRegistryProvider);
  final authManager = ref.read(authManagerProvider);

  final manager = ConnectionManager(
    registry: registry,
    headerRefresher: (serverId) => authManager.getAuthHeaders(serverId),
  );
  ref.onDispose(() => manager.dispose());
  return manager;
});
