import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../infrastructure/quick_agui/tool_call_state.dart';
import '../models/chat_models.dart';
import '../network/connection_manager.dart';
import '../utils/api_constants.dart';
import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'local_tools_service.dart';
import 'server_config_service.dart';

/// Configuration for AG-UI service.
class AgUiServiceConfig {
  final String baseUrl;
  final String roomId;
  final Duration timeout;
  final Map<String, String>? headers;
  final UrlBuilder _urlBuilder;

  AgUiServiceConfig({
    required this.baseUrl,
    required this.roomId,
    this.timeout = const Duration(seconds: 30),
    this.headers,
  }) : _urlBuilder = UrlBuilder(baseUrl);

  /// Get the URL builder for constructing endpoints.
  UrlBuilder get urlBuilder => _urlBuilder;

  /// Create thread endpoint: POST /api/v1/rooms/{roomId}/agui
  Uri get createThreadUri => _urlBuilder.createThread(roomId);

  /// Create run endpoint: POST /api/v1/rooms/{roomId}/agui/{threadId}
  Uri createRunUri(String threadId) => _urlBuilder.createRun(roomId, threadId);

  /// Execute run endpoint: POST /api/v1/rooms/{roomId}/agui/{threadId}/{runId}
  Uri executeRunUri(String threadId, String runId) =>
      _urlBuilder.executeRun(roomId, threadId, runId);
}

/// Connection state for the AG-UI service.
enum AgUiConnectionState {
  disconnected,
  connecting,
  connected,
  streaming,
  error,
}

/// Callback for UI tool handlers (canvas_render, genui_render).
typedef UiToolHandler =
    Future<Map<String, dynamic>> Function(
      String toolCallId,
      String toolName,
      Map<String, dynamic> args,
    );

/// Callback for local tool execution notifications.
typedef LocalToolNotifier = void Function(String toolCallId, String toolName, String status);

/// AG-UI Service - facade over ConnectionManager for UI layer.
///
/// Provides a simplified API for the UI layer while delegating
/// all networking and session management to ConnectionManager.
///
/// Key responsibilities:
/// - Configuration management (room selection)
/// - State tracking for UI binding
/// - Delegating chat operations to ConnectionManager
/// - Thread history loading
class AgUiService extends ChangeNotifier {
  final ConnectionManager _connectionManager;
  final http.Client _httpClient = http.Client();

  AgUiServiceConfig? _config;
  AgUiConnectionState _state = AgUiConnectionState.disconnected;
  String? _lastError;

  // Mutex to prevent concurrent chat() calls
  Completer<void>? _chatLock;

  AgUiService(this._connectionManager);

  AgUiConnectionState get state => _state;
  String? get lastError => _lastError;
  bool get isConfigured => _config != null;
  String? get currentRoomId => _config?.roomId;

  /// Get thread ID from the active session.
  String? get threadId {
    if (_config == null) return null;
    return _connectionManager.getSession(_config!.roomId).threadId;
  }

  /// Get run ID from the active session.
  String? get runId {
    if (_config == null) return null;
    return _connectionManager.getSession(_config!.roomId).activeRunId;
  }

  /// Stream of AG-UI events from the active session.
  Stream<ag_ui.BaseEvent>? get eventsStream {
    if (_config == null) return null;
    return _connectionManager.getSession(_config!.roomId).stepsStream;
  }

  /// Stream of tool call state changes from the active session.
  Stream<ToolCallStateChange>? get toolStateChanges {
    if (_config == null) return null;
    return _connectionManager.getSession(_config!.roomId).toolStateChanges;
  }

  /// Configure the AG-UI service with server details.
  void configure(AgUiServiceConfig config) {
    // Skip if config hasn't changed
    if (_config?.baseUrl == config.baseUrl &&
        _config?.roomId == config.roomId) {
      return;
    }

    DebugLog.service('AgUiService: Configuring for room "${config.roomId}"');
    _config = config;
    _state = AgUiConnectionState.disconnected;
    _lastError = null;

    // Switch room in ConnectionManager (handles session lifecycle)
    _connectionManager.switchRoom(config.roomId);

    notifyListeners();
  }

  /// Send a message and handle the full conversation flow.
  ///
  /// Delegates to ConnectionManager.chat() which handles:
  /// - Session initialization
  /// - Tool registration
  /// - Event streaming
  /// - Tool result loops
  ///
  /// [uiToolHandler] is called for canvas_render and genui_render tools
  /// which need access to UI state (Riverpod providers).
  ///
  /// [onLocalToolExecution] is called when a local tool starts/completes execution.
  ///
  /// [onToolStateChange] is called when tool call states change (start/end execution).
  ///
  /// [state] is optional application state (e.g., canvas contents) to send with the request.
  ///
  /// Note: Calls are serialized to prevent concurrent streaming issues.
  Future<void> chat(
    String userMessage, {
    required LocalToolsService localToolsService,
    required void Function(ag_ui.BaseEvent event) onEvent,
    UiToolHandler? uiToolHandler,
    LocalToolNotifier? onLocalToolExecution,
    void Function(ToolCallStateChange change)? onToolStateChange,
    Map<String, dynamic>? state,
  }) async {
    // Wait for any pending chat() to complete
    while (_chatLock != null) {
      DebugLog.service('AG-UI: Waiting for previous chat() to complete...');
      await _chatLock!.future;
    }

    // Acquire lock
    _chatLock = Completer<void>();

    if (_config == null) {
      _chatLock!.complete();
      _chatLock = null;
      throw StateError('AgUiService not configured. Call configure() first.');
    }

    _state = AgUiConnectionState.connecting;
    _lastError = null;
    notifyListeners();

    try {
      _state = AgUiConnectionState.streaming;
      notifyListeners();

      // Delegate to ConnectionManager
      await _connectionManager.chat(
        roomId: _config!.roomId,
        userMessage: userMessage,
        localToolsService: localToolsService,
        onEvent: onEvent,
        uiToolHandler: uiToolHandler,
        onLocalToolExecution: onLocalToolExecution,
        onToolStateChange: onToolStateChange,
        state: state,
      );

      _state = AgUiConnectionState.connected;
      notifyListeners();
    } catch (e, stackTrace) {
      _state = AgUiConnectionState.error;
      _lastError = e.toString();
      DebugLog.error('AgUiService error: $e');
      notifyListeners();
      rethrow;
    } finally {
      // Always release lock
      _chatLock?.complete();
      _chatLock = null;
    }
  }

  /// Cancel the current active run.
  Future<void> cancelCurrentRun() async {
    if (_config == null) {
      DebugLog.service('AgUiService: Cannot cancel - not configured');
      return;
    }

    await _connectionManager.cancelRun(_config!.roomId);
    _state = AgUiConnectionState.connected;
    notifyListeners();
  }

  /// Resume an existing thread by ID and load its history.
  ///
  /// Returns the chat messages reconstructed from the thread's event history.
  /// The caller should pass these to ChatNotifier.loadMessages().
  Future<List<ChatMessage>> resumeThread(String threadId) async {
    if (_config == null) {
      throw StateError('AgUiService not configured. Call configure() first.');
    }

    DebugLog.service('AgUiService: Resuming thread $threadId');

    _state = AgUiConnectionState.connected;
    notifyListeners();

    // Load and return thread history
    return await loadThreadHistory(threadId);
  }

  /// Fetch thread history from the server and convert events to chat messages.
  Future<List<ChatMessage>> loadThreadHistory(String threadId) async {
    if (_config == null) {
      throw StateError('AgUiService not configured.');
    }

    DebugLog.service('AgUiService: Loading history for thread $threadId');

    try {
      // Use createRunUri to get thread details (same endpoint, different method)
      final response = await _httpClient.get(
        _config!.createRunUri(threadId),
        headers: {'Content-Type': 'application/json', ...?_config!.headers},
      );

      if (response.statusCode != 200) {
        DebugLog.service('AgUiService: Failed to load thread: ${response.statusCode}');
        return [];
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final runs = data['runs'] as Map<String, dynamic>? ?? {};

      DebugLog.service('AgUiService: Found ${runs.length} runs');

      // Collect all messages from all runs, sorted by creation time
      final List<ChatMessage> messages = [];

      // Sort runs by creation time
      final sortedRuns = runs.entries.toList()
        ..sort((a, b) {
          final aCreated = (a.value as Map<String, dynamic>)['created'] as String? ?? '';
          final bCreated = (b.value as Map<String, dynamic>)['created'] as String? ?? '';
          return aCreated.compareTo(bCreated);
        });

      for (final entry in sortedRuns) {
        final runData = entry.value as Map<String, dynamic>;
        final runInput = runData['run_input'] as Map<String, dynamic>?;
        final events = runData['events'] as List<dynamic>? ?? [];

        DebugLog.service('AgUiService: Run ${entry.key} has ${events.length} events');

        // Extract user messages from run_input
        if (runInput != null) {
          final inputMessages = runInput['messages'] as List<dynamic>? ?? [];
          for (final msg in inputMessages) {
            if (msg is Map<String, dynamic>) {
              final role = msg['role'] as String?;
              final content = msg['content'] as String?;
              if (role == 'user' && content != null && content.isNotEmpty) {
                messages.add(ChatMessage.text(
                  user: ChatUser.user,
                  text: content,
                ));
              }
            }
          }
        }

        // Process events to extract assistant messages
        messages.addAll(_eventsToMessages(events));
      }

      DebugLog.service('AgUiService: Loaded ${messages.length} messages from history');
      return messages;
    } catch (e, stackTrace) {
      DebugLog.service('AgUiService: Error loading thread history: $e\n$stackTrace');
      return [];
    }
  }

  /// Convert AG-UI events to chat messages.
  List<ChatMessage> _eventsToMessages(List<dynamic> events) {
    final List<ChatMessage> messages = [];
    StringBuffer currentText = StringBuffer();

    // Track tool calls for GenUI
    final Map<String, Map<String, dynamic>> toolCalls = {};
    String? currentToolCallId;
    StringBuffer currentToolArgs = StringBuffer();

    for (final event in events) {
      if (event is! Map<String, dynamic>) continue;

      final type = event['type'] as String?;

      switch (type) {
        case 'TEXT_MESSAGE_START':
          currentText = StringBuffer();
          break;

        case 'TEXT_MESSAGE_CONTENT':
          final delta = event['delta'] as String? ?? '';
          currentText.write(delta);
          break;

        case 'TEXT_MESSAGE_END':
          if (currentText.isNotEmpty) {
            messages.add(ChatMessage.text(
              user: ChatUser.agent,
              text: currentText.toString(),
            ));
          }
          currentText = StringBuffer();
          break;

        case 'TOOL_CALL_START':
          currentToolCallId = event['toolCallId'] as String?;
          final toolName = event['name'] as String? ?? event['toolName'] as String?;
          if (currentToolCallId != null) {
            toolCalls[currentToolCallId] = {
              'name': toolName,
              'args': '',
            };
          }
          currentToolArgs = StringBuffer();
          break;

        case 'TOOL_CALL_ARGS':
          final args = event['args'] as String? ?? event['delta'] as String? ?? '';
          currentToolArgs.write(args);
          if (currentToolCallId != null && toolCalls.containsKey(currentToolCallId)) {
            toolCalls[currentToolCallId]!['args'] = currentToolArgs.toString();
          }
          break;

        case 'TOOL_CALL_END':
          if (currentToolCallId != null && toolCalls.containsKey(currentToolCallId)) {
            final toolData = toolCalls[currentToolCallId]!;
            final toolName = toolData['name'] as String?;

            // Check if this is a genui_render tool call
            if (toolName == 'genui_render') {
              try {
                final argsJson = toolData['args'] as String? ?? '{}';
                final args = jsonDecode(argsJson) as Map<String, dynamic>;
                final widgetName = args['widget_name'] as String? ?? 'Widget';
                final widgetData = args['data'] as Map<String, dynamic>? ?? {};

                messages.add(ChatMessage.genUi(
                  user: ChatUser.agent,
                  content: GenUiContent(
                    toolCallId: currentToolCallId,
                    widgetName: widgetName,
                    data: widgetData,
                  ),
                ));
              } catch (e) {
                DebugLog.service('AgUiService: Failed to parse genui_render args: $e');
              }
            }
          }
          currentToolCallId = null;
          currentToolArgs = StringBuffer();
          break;
      }
    }

    return messages;
  }

  /// Reset the conversation (clear session state).
  void resetConversation() {
    if (_config != null) {
      // Dispose the current session
      _connectionManager.disposeSession(_config!.roomId);
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _httpClient.close();
    super.dispose();
  }
}

// =============================================================================
// PROVIDERS
// =============================================================================

/// Provider for ConnectionManager (server-scoped).
///
/// Watches [currentServerProvider] - recreated when server changes.
/// Does NOT watch agUiConfigProvider to avoid circular invalidation.
final connectionManagerProvider = ChangeNotifierProvider<ConnectionManager>((ref) {
  final server = ref.watch(currentServerProvider);
  final baseUrl = server?.url ?? ApiConstants.defaultServerUrl;

  DebugLog.service('ConnectionManager: Created for server ${server?.id}');
  final manager = ConnectionManager(baseUrl: baseUrl);

  ref.onDispose(() {
    DebugLog.service('ConnectionManager: Disposed for server ${server?.id}');
    manager.dispose();
  });

  return manager;
});

/// Provider for AgUiService.
///
/// Depends on ConnectionManager for all networking operations.
final agUiServiceProvider = ChangeNotifierProvider<AgUiService>((ref) {
  final connectionManager = ref.watch(connectionManagerProvider);
  return AgUiService(connectionManager);
});

/// Provider for AG-UI configuration.
///
/// Watches [currentServerProvider] - config resets when server changes.
final agUiConfigProvider = StateProvider<AgUiServiceConfig?>((ref) {
  ref.watch(currentServerProvider);  // Reactive: resets on server change
  return null;
});

/// Provider for configured AgUiService.
///
/// Simply returns the AgUiService. Configuration is managed explicitly
/// by the UI layer via chat_screen.dart calling service.configure().
/// This avoids lifecycle issues with auto-configuration.
final configuredAgUiServiceProvider = Provider<AgUiService>((ref) {
  return ref.watch(agUiServiceProvider);
});
