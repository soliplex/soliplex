import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import 'agui/thread.dart';
import 'api/soliplex_api.dart';
import 'models/models.dart';
import 'session/connection_manager.dart';
import 'session/room_session.dart';
import 'utils/url_builder.dart';

/// Callback for AG-UI events.
typedef OnEvent = void Function(ag_ui.BaseEvent event);

/// Callback for UI tool execution.
typedef UiToolHandler =
    Future<Map<String, dynamic>> Function(
      String toolCallId,
      String toolName,
      Map<String, dynamic> args,
    );

/// Main client for Soliplex backend.
///
/// This is the single entry point for interacting with the Soliplex backend.
class SoliplexClient {
  SoliplexClient({
    String baseUrl = 'http://localhost:8000',
    Map<String, String>? headers,
    SoliplexApi? api,
    ConnectionManager? connectionManager,
  }) : _headers = headers {
    _configure(baseUrl, headers, api: api, connectionManager: connectionManager);
  }

  late SoliplexApi _api;
  late ConnectionManager _connectionManager;
  Map<String, String>? _headers;

  static const _uiTools = {'canvas_render', 'genui_render'};

  /// API client for direct endpoint access.
  SoliplexApi get api => _api;

  /// Connection manager for session management.
  ConnectionManager get connectionManager => _connectionManager;

  /// URL builder.
  UrlBuilder get urlBuilder => _connectionManager.urlBuilder;

  /// Current base URL.
  String get baseUrl => _connectionManager.baseUrl;

  void _configure(
    String baseUrl,
    Map<String, String>? headers, {
    SoliplexApi? api,
    ConnectionManager? connectionManager,
  }) {
    final normalizedUrl = UrlBuilder.normalizeBaseUrl(baseUrl);
    _api = api ?? SoliplexApi(baseUrl: normalizedUrl, headers: headers);
    _connectionManager = connectionManager ??
        ConnectionManager(
          baseUrl: normalizedUrl,
          headers: headers,
        );
    _headers = headers;
  }

  /// Configure the client with a new base URL.
  void configure(String baseUrl, {Map<String, String>? headers}) {
    _connectionManager.switchServer(baseUrl, headers: headers);
    _api = SoliplexApi(
      baseUrl: _connectionManager.baseUrl,
      headers: headers ?? _headers,
    );
    _headers = headers ?? _headers;
  }

  // === Room operations ===

  /// Get all rooms.
  Future<List<Room>> getRooms() => _api.getRooms();

  /// Get a specific room.
  Future<Room> getRoom(String roomId) => _api.getRoom(roomId);

  // === Thread operations ===

  /// Get all threads in a room.
  Future<List<ThreadInfo>> getThreads(String roomId) => _api.getThreads(roomId);

  /// Get a specific thread.
  Future<ThreadInfo> getThread(String roomId, String threadId) =>
      _api.getThread(roomId, threadId);

  /// Create a new thread in a room.
  ///
  /// Returns the thread ID and initial run ID.
  Future<({String threadId, String runId})> createThread(String roomId) async {
    final result = await _api.createThread(roomId);
    final threadId = result['thread_id'] as String;
    final runId = result['run_id'] as String;
    _connectionManager.initializeSession(roomId, threadId);
    return (threadId: threadId, runId: runId);
  }

  /// Delete a thread.
  Future<void> deleteThread(String roomId, String threadId) =>
      _api.deleteThread(roomId, threadId);

  /// Set thread metadata.
  Future<void> setThreadMeta(
    String roomId,
    String threadId, {
    String? name,
    String? description,
  }) => _api.setThreadMeta(
    roomId,
    threadId,
    name: name,
    description: description,
  );

  // === Run operations ===

  /// Get a specific run.
  Future<RunInfo> getRun(String roomId, String threadId, String runId) =>
      _api.getRun(roomId, threadId, runId);

  /// Create a new run.
  Future<String> createRun(String roomId, String threadId) async {
    final result = await _api.createRun(roomId, threadId);
    return result['run_id'] as String;
  }

  /// Set run metadata.
  Future<void> setRunMeta(
    String roomId,
    String threadId,
    String runId, {
    String? label,
  }) => _api.setRunMeta(roomId, threadId, runId, label: label);

  // === Chat operations ===

  /// Send a chat message and process the response.
  ///
  /// This handles the full conversation flow including tool execution.
  Future<void> chat({
    required String roomId,
    required String userMessage,
    Map<String, ag_ui.Tool>? tools,
    Map<String, ToolExecutor>? toolExecutors,
    UiToolHandler? uiToolHandler,
    OnEvent? onEvent,
    CanvasCallback? onCanvasUpdate,
    ContextCallback? onContextUpdate,
    ActivityCallback? onActivityUpdate,
    Map<String, dynamic>? state,
  }) async {
    final session = _connectionManager.getSession(roomId);

    // Set up callbacks
    session.onCanvasUpdate = onCanvasUpdate;
    session.onContextUpdate = onContextUpdate;
    session.onActivityUpdate = onActivityUpdate;

    // Initialize thread if needed
    if (session.threadId == null) {
      final result = await createThread(roomId);
      session.initializeThread(result.threadId);
    }

    final thread = session.thread;
    if (thread == null) {
      throw StateError('Thread not initialized');
    }

    // Register tools
    if (tools != null && toolExecutors != null) {
      _registerTools(session, thread, tools, toolExecutors, uiToolHandler);
    }

    // Add user message
    session.addUserMessage(userMessage);

    // Create AG-UI user message
    final userMsg = ag_ui.UserMessage(
      id: 'user-${DateTime.now().millisecondsSinceEpoch}',
      content: userMessage,
    );

    // Listen to events
    StreamSubscription<ag_ui.BaseEvent>? stepsSub;
    try {
      stepsSub = thread.stepsStream.listen((event) {
        session.processEvent(event);
        onEvent?.call(event);
      });

      // Get or create run ID
      final runId = await createRun(roomId, session.threadId!);
      final endpoint = urlBuilder.runEndpointPath(
        roomId,
        session.threadId!,
        runId,
      );

      // Start run
      var toolResults = await thread.startRun(
        endpoint: endpoint,
        runId: runId,
        messages: [userMsg],
        state: state,
      );

      // Tool result loop
      while (toolResults.isNotEmpty) {
        final newRunId = await createRun(roomId, session.threadId!);
        final newEndpoint = urlBuilder.runEndpointPath(
          roomId,
          session.threadId!,
          newRunId,
        );
        toolResults = await thread.startRun(
          endpoint: newEndpoint,
          runId: newRunId,
          messages: toolResults,
        );
      }
    } finally {
      await stepsSub?.cancel();
    }
  }

  void _registerTools(
    RoomSession session,
    Thread thread,
    Map<String, ag_ui.Tool> tools,
    Map<String, ToolExecutor> executors,
    UiToolHandler? uiToolHandler,
  ) {
    for (final entry in tools.entries) {
      final toolName = entry.key;
      final tool = entry.value;
      final executor = executors[toolName];
      final isFireAndForget = _uiTools.contains(toolName);

      thread.addTool(tool, (call) async {
        Map<String, dynamic> args = {};
        try {
          if (call.function.arguments.isNotEmpty) {
            args = jsonDecode(call.function.arguments) as Map<String, dynamic>;
          }
        } catch (_) {
          // Ignore parse errors
        }

        // UI tools
        if (_uiTools.contains(call.function.name) && uiToolHandler != null) {
          session.handleLocalToolExecution(
            call.id,
            call.function.name,
            'executing',
          );
          try {
            final result = await uiToolHandler(
              call.id,
              call.function.name,
              args,
            );
            session.handleLocalToolExecution(
              call.id,
              call.function.name,
              'completed',
            );
            return jsonEncode(result);
          } catch (e) {
            session.handleLocalToolExecution(
              call.id,
              call.function.name,
              'error: $e',
            );
            return jsonEncode({'error': e.toString()});
          }
        }

        // Regular tools
        if (executor != null) {
          session.handleLocalToolExecution(
            call.id,
            call.function.name,
            'executing',
          );
          try {
            final result = await executor(call);
            session.handleLocalToolExecution(
              call.id,
              call.function.name,
              'completed',
            );
            return result;
          } catch (e) {
            session.handleLocalToolExecution(
              call.id,
              call.function.name,
              'error: $e',
            );
            return jsonEncode({'error': e.toString()});
          }
        }

        return jsonEncode({
          'error': 'No executor for tool ${call.function.name}',
        });
      }, fireAndForget: isFireAndForget);
    }
  }

  // === Session operations ===

  /// Get messages for a room.
  List<ChatMessage> getMessages(String roomId) {
    final session = _connectionManager.getSession(roomId);
    return session.messages;
  }

  /// Get message stream for a room.
  Stream<List<ChatMessage>> getMessageStream(String roomId) {
    final session = _connectionManager.getSession(roomId);
    return session.messageStream;
  }

  /// Switch to a different room.
  void switchRoom(String roomId) {
    _connectionManager.switchRoom(roomId);
  }

  /// Cancel the current operation for a room.
  void cancelRun(String roomId) {
    _connectionManager.cancelRun(roomId);
  }

  /// Dispose the client.
  void dispose() {
    _api.close();
    _connectionManager.dispose();
  }
}
