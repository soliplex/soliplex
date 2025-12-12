import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';

import '../../infrastructure/quick_agui/tool_call_state.dart';
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
/// Handles:
/// - Session pool (Map<roomId, RoomSession>)
/// - Room switching with state preservation
/// - Run cancellation
/// - Connection observability
class ConnectionManager extends ChangeNotifier {
  final String baseUrl;
  final Map<String, String>? headers;
  final HttpTransport _transport;
  final UrlBuilder _urlBuilder;
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

  ConnectionManager({
    required this.baseUrl,
    this.headers,
    this.maxBackgroundedSessions = 5,
    HttpTransport? transport,
  }) : _urlBuilder = UrlBuilder(baseUrl),
       _transport = transport ?? HttpTransport(baseUrl: baseUrl, defaultHeaders: headers) {
    // Use serverUrl (not apiBaseUrl) because runEndpoint includes the api path.
    // The ag_ui client replaces the path instead of appending to it.
    _agUiClient = ag_ui.AgUiClient(
      config: ag_ui.AgUiClientConfig(
        baseUrl: _urlBuilder.serverUrl,
        defaultHeaders: headers ?? {},
      ),
    );
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
        baseUrl: baseUrl,
        transport: _transport,
      );
      _sessions[roomId] = session;

      // Forward session events
      session.events.listen((event) {
        _eventController.add(event);
        notifyListeners();
      });
    }
    return session;
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
  Future<void> chat({
    required String roomId,
    required String userMessage,
    required LocalToolsService localToolsService,
    required void Function(ag_ui.BaseEvent event) onEvent,
    UiToolHandler? uiToolHandler,
    LocalToolNotifier? onLocalToolExecution,
    void Function(ToolCallStateChange change)? onToolStateChange,
    Map<String, dynamic>? state,
  }) async {
    final session = getSession(roomId);

    // Initialize if needed
    if (session.threadId == null) {
      await initializeSession(roomId);
    }

    // Register tools
    _registerTools(session, localToolsService, uiToolHandler, onLocalToolExecution);

    // Listen to event streams
    StreamSubscription<ag_ui.BaseEvent>? stepsSub;
    StreamSubscription<ToolCallStateChange>? toolStateSub;

    try {
      stepsSub = session.stepsStream?.listen(onEvent);
      if (onToolStateChange != null) {
        toolStateSub = session.toolStateChanges?.listen(onToolStateChange);
      }

      // Create user message
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
      await toolStateSub?.cancel();
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

  /// Resume a thread for a room.
  ///
  /// Returns chat messages reconstructed from history.
  Future<List<ChatMessage>> resumeThread(String roomId, String threadId) async {
    final session = getSession(roomId);

    // TODO: Fetch thread history from server
    // For now, return preserved chat history
    DebugLog.network('ConnectionManager: Resuming thread $threadId for room $roomId');
    return session.chatHistory;
  }

  /// Save chat history for a room.
  void saveChatHistory(String roomId, List<ChatMessage> messages) {
    final session = _sessions[roomId];
    session?.saveChatHistory(messages);
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

        // UI tools
        if (_uiTools.contains(call.function.name) && uiToolHandler != null) {
          onLocalToolExecution?.call(call.id, call.function.name, 'executing');
          try {
            final result = await uiToolHandler(call.id, call.function.name, args);
            onLocalToolExecution?.call(call.id, call.function.name, 'completed');
            return jsonEncode(result);
          } catch (e) {
            onLocalToolExecution?.call(call.id, call.function.name, 'error: $e');
            return jsonEncode({'error': e.toString()});
          }
        }

        // Regular tools
        onLocalToolExecution?.call(call.id, call.function.name, 'executing');
        final result = await localToolsService.executeTool(
          call.id,
          call.function.name,
          args,
        );

        if (result.success) {
          onLocalToolExecution?.call(call.id, call.function.name, 'completed');
          return jsonEncode(result.result);
        } else {
          onLocalToolExecution?.call(call.id, call.function.name, 'error');
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
