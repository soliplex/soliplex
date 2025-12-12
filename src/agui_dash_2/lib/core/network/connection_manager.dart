import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';

import '../models/chat_models.dart';
import '../services/local_tools_service.dart';
import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'connection_events.dart';
import 'http_transport.dart';
import 'room_session.dart';

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

/// Central hub managing all room sessions.
///
/// Singleton for app lifetime - handles server changes internally via switchServer().
///
/// Handles:
/// - Session pool (Map<roomId, RoomSession>)
/// - Server switching (clears sessions on server change)
/// - Room switching with state preservation
/// - Run cancellation
/// - Connection observability
class ConnectionManager extends ChangeNotifier {
  String _baseUrl;
  Map<String, String>? _headers;
  HttpTransport _transport;
  UrlBuilder _urlBuilder;
  ag_ui.AgUiClient? _agUiClient;

  /// All room sessions.
  final Map<String, RoomSession> _sessions = {};

  /// Currently active room ID.
  String? _activeRoomId;

  /// Max backgrounded sessions before LRU eviction.
  final int maxBackgroundedSessions;

  /// Event stream for all sessions.
  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  /// Tools that should be handled by the UI layer.
  static const _uiTools = {'canvas_render', 'genui_render'};

  /// Whether the manager has been configured with a server.
  bool get isConfigured => _baseUrl.isNotEmpty;

  /// Current server URL.
  String get serverUrl => _urlBuilder.serverUrl;

  ConnectionManager({
    String baseUrl = '',
    Map<String, String>? headers,
    this.maxBackgroundedSessions = 5,
    HttpTransport? transport,
  }) : _baseUrl = baseUrl,
       _headers = headers,
       _urlBuilder = UrlBuilder(baseUrl.isNotEmpty ? baseUrl : 'http://localhost'),
       _transport = transport ?? HttpTransport(baseUrl: baseUrl.isNotEmpty ? baseUrl : 'http://localhost', defaultHeaders: headers) {
    if (baseUrl.isNotEmpty) {
      _initializeClient();
    }
  }

  void _initializeClient() {
    // Use serverUrl (not apiBaseUrl) because runEndpoint includes the api path.
    // The ag_ui client replaces the path instead of appending to it.
    _agUiClient = ag_ui.AgUiClient(
      config: ag_ui.AgUiClientConfig(
        baseUrl: _urlBuilder.serverUrl,
        defaultHeaders: _headers ?? {},
      ),
    );
  }

  /// Switch to a different server.
  ///
  /// Disposes all existing sessions and reinitializes for the new server.
  /// Call this when the user selects a different server.
  void switchServer(String newBaseUrl, {Map<String, String>? headers}) {
    if (_baseUrl == newBaseUrl && _headersEqual(headers)) {
      DebugLog.network('ConnectionManager: Server unchanged, skipping switch');
      return;
    }

    DebugLog.network('ConnectionManager: Switching server from $_baseUrl to $newBaseUrl');

    // Dispose all existing sessions
    for (final session in _sessions.values) {
      session.dispose();
    }
    _sessions.clear();
    _activeRoomId = null;

    // Update configuration
    _baseUrl = newBaseUrl;
    _headers = headers;
    _urlBuilder = UrlBuilder(newBaseUrl);
    _transport = HttpTransport(baseUrl: newBaseUrl, defaultHeaders: headers);
    _initializeClient();

    notifyListeners();
  }

  bool _headersEqual(Map<String, String>? newHeaders) {
    if (_headers == null && newHeaders == null) return true;
    if (_headers == null || newHeaders == null) return false;
    if (_headers!.length != newHeaders.length) return false;
    for (final key in _headers!.keys) {
      if (_headers![key] != newHeaders[key]) return false;
    }
    return true;
  }

  // Getters
  String? get activeRoomId => _activeRoomId;
  RoomSession? get activeSession =>
      _activeRoomId != null ? _sessions[_activeRoomId] : null;

  /// Stream of connection events for observability.
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Get all active connections info.
  List<ConnectionInfo> get activeConnections =>
      _sessions.values.map((s) => s.connectionInfo).toList();

  /// Get connection info for a specific room.
  ConnectionInfo? getConnectionInfo(String roomId) =>
      _sessions[roomId]?.connectionInfo;

  /// Get or create a session for a room.
  RoomSession getSession(String roomId) {
    var session = _sessions[roomId];
    if (session == null) {
      session = RoomSession(
        roomId: roomId,
        baseUrl: _baseUrl,
        transport: _transport,
      );
      _sessions[roomId] = session;

      // Forward session events
      session.events.listen((event) {
        _eventController.add(event);
        notifyListeners();
      });

      // Forward message updates
      session.messageStream.listen((_) {
        notifyListeners();
      });
    }
    return session;
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
    return _sessions[roomId]?.isAgentTyping ?? false;
  }

  /// Switch to a different room.
  ///
  /// Suspends the current session (if any) and resumes or creates the new one.
  Future<RoomSession> switchRoom(String newRoomId) async {
    final previousRoomId = _activeRoomId;

    if (previousRoomId == newRoomId) {
      // Already on this room
      return getSession(newRoomId);
    }

    DebugLog.network('ConnectionManager: Switching from $previousRoomId to $newRoomId');

    // Suspend previous session
    if (previousRoomId != null) {
      final previousSession = _sessions[previousRoomId];
      previousSession?.suspend();
    }

    // Get or create new session
    final newSession = getSession(newRoomId);

    // Resume if backgrounded
    if (newSession.state == SessionState.backgrounded) {
      newSession.resume();
    }

    _activeRoomId = newRoomId;

    _eventController.add(RoomSwitchedEvent(
      roomId: newRoomId,
      previousRoomId: previousRoomId,
    ));

    // LRU eviction of backgrounded sessions
    _evictOldSessions();

    notifyListeners();
    return newSession;
  }

  /// Initialize a session for a room (create thread).
  Future<void> initializeSession(String roomId) async {
    final session = getSession(roomId);
    if (session.threadId == null && _agUiClient != null) {
      await session.initialize(_agUiClient!);
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
    final session = _sessions[roomId];
    if (session == null) {
      DebugLog.network('ConnectionManager: No session for room $roomId');
      return;
    }

    await session.cancelActiveRun();
    notifyListeners();
  }

  /// Clear messages for a room.
  void clearMessages(String roomId) {
    final session = _sessions[roomId];
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

  /// Evict oldest backgrounded sessions if over limit.
  void _evictOldSessions() {
    final backgrounded = _sessions.entries
        .where((e) => e.value.state == SessionState.backgrounded)
        .toList()
      ..sort((a, b) =>
          (a.value.lastActivity ?? DateTime(0)).compareTo(b.value.lastActivity ?? DateTime(0)));

    while (backgrounded.length > maxBackgroundedSessions) {
      final oldest = backgrounded.removeAt(0);
      DebugLog.network('ConnectionManager: Evicting old session for room ${oldest.key}');
      oldest.value.dispose();
      _sessions.remove(oldest.key);
    }
  }

  /// Dispose a specific room session.
  void disposeSession(String roomId) {
    final session = _sessions.remove(roomId);
    session?.dispose();

    if (_activeRoomId == roomId) {
      _activeRoomId = null;
    }

    notifyListeners();
  }

  /// Dispose all sessions.
  @override
  void dispose() {
    for (final session in _sessions.values) {
      session.dispose();
    }
    _sessions.clear();
    _transport.close();
    _eventController.close();
    super.dispose();
  }
}

// Note: connectionManagerProvider is declared in lib/core/services/agui_service.dart
// to avoid circular dependencies and ensure proper server-scoped lifecycle.
