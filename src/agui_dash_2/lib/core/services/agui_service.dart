import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../infrastructure/quick_agui/thread.dart';
import '../../infrastructure/quick_agui/tool_call_state.dart';
import '../models/chat_models.dart';
import '../utils/debug_log.dart';
import 'local_tools_service.dart';

/// Configuration for AG-UI service.
class AgUiServiceConfig {
  final String baseUrl;
  final String roomId;
  final Duration timeout;
  final Map<String, String>? headers;

  const AgUiServiceConfig({
    required this.baseUrl,
    required this.roomId,
    this.timeout = const Duration(seconds: 30),
    this.headers,
  });

  /// Base endpoint for the room
  String get roomEndpoint => '$baseUrl/rooms/$roomId/agui';
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

/// AG-UI Service - manages communication with the AG-UI server using Thread.
///
/// Uses the quick_agui Thread class for:
/// - Message history management
/// - Tool call handling
/// - Event streaming
class AgUiService extends ChangeNotifier {
  AgUiServiceConfig? _config;
  final http.Client _httpClient = http.Client();
  AgUiConnectionState _state = AgUiConnectionState.disconnected;
  String? _lastError;

  Thread? _thread;
  String? _currentRunId;

  // AG-UI client for SSE streaming
  ag_ui.AgUiClient? _agUiClient;

  // Handler for UI tools (canvas_render, genui_render)
  UiToolHandler? _uiToolHandler;

  // Notifier for local tool execution events
  LocalToolNotifier? _localToolNotifier;

  // Mutex to prevent concurrent chat() calls
  Completer<void>? _chatLock;

  /// Tools that should be handled by the UI layer instead of LocalToolsService.
  static const _uiTools = {'canvas_render', 'genui_render'};

  AgUiConnectionState get state => _state;
  String? get lastError => _lastError;
  String? get threadId => _thread?.id;
  String? get runId => _currentRunId;
  bool get isConfigured => _config != null;
  String? get currentRoomId => _config?.roomId;

  /// Stream of all AG-UI events (for UI to listen to).
  Stream<ag_ui.BaseEvent>? get eventsStream => _thread?.stepsStream;

  /// Stream of messages.
  Stream<ag_ui.Message>? get messagesStream => _thread?.messageStream;

  /// Stream of state updates.
  Stream<ag_ui.State>? get stateStream => _thread?.stateStream;

  /// Stream of tool call state changes for UI notifications.
  Stream<ToolCallStateChange>? get toolStateChanges => _thread?.toolStateChanges;

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

    // Reset thread when room changes
    _thread?.dispose();
    _thread = null;
    _currentRunId = null;

    // Create AG-UI client
    _agUiClient = ag_ui.AgUiClient(
      config: ag_ui.AgUiClientConfig(baseUrl: config.baseUrl),
    );

    notifyListeners();
  }

  /// Create a new thread on the server.
  Future<(String, String)> _createThread() async {
    final response = await _httpClient.post(
      Uri.parse(_config!.roomEndpoint),
      headers: {'Content-Type': 'application/json', ...?_config!.headers},
      body: '{}',
    );

    if (response.statusCode != 200) {
      throw Exception(
        'Failed to create thread: ${response.statusCode} ${response.body}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final threadId = data['thread_id'] as String?;
    if (threadId == null) {
      throw Exception('Server did not return thread_id');
    }

    // Server auto-creates initial run
    final runs = data['runs'] as Map<String, dynamic>?;
    if (runs == null || runs.isEmpty) {
      throw Exception('Server did not return any runs');
    }
    final runId = runs.keys.first;

    DebugLog.service('AG-UI: Created thread: $threadId with initial run: $runId');
    return (threadId, runId);
  }

  /// Create a new run for the given thread.
  Future<String> _createRun(String threadId) async {
    final response = await _httpClient.post(
      Uri.parse('${_config!.roomEndpoint}/$threadId'),
      headers: {'Content-Type': 'application/json', ...?_config!.headers},
      body: '{}',
    );

    if (response.statusCode != 200) {
      throw Exception(
        'Failed to create run: ${response.statusCode} ${response.body}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final runId = data['run_id'] as String?;
    if (runId == null) {
      throw Exception('Server did not return run_id');
    }

    DebugLog.service('AG-UI: Created run: $runId');
    return runId;
  }

  /// Register local tools with the thread.
  void _registerTools(LocalToolsService localToolsService) {
    if (_thread == null) return;

    for (final toolDef in localToolsService.tools) {
      final agTool = ag_ui.Tool(
        name: toolDef.name,
        description: toolDef.description,
        parameters: toolDef.parameters,
      );

      // UI tools are fire-and-forget - they execute but don't send results back
      // This prevents infinite loops where the LLM keeps calling the same tool
      final isFireAndForget = _uiTools.contains(toolDef.name);

      _thread!.addTool(agTool, (call) async {
        DebugLog.service('AG-UI: Tool executor callback for ${call.function.name}');

        // Parse arguments
        Map<String, dynamic> args = {};
        try {
          if (call.function.arguments.isNotEmpty) {
            args = jsonDecode(call.function.arguments) as Map<String, dynamic>;
          }
        } catch (e) {
          DebugLog.service('AG-UI: Failed to parse tool args: $e');
        }

        // Check if this is a UI tool that needs special handling
        if (_uiTools.contains(call.function.name) && _uiToolHandler != null) {
          DebugLog.service('AG-UI: Routing ${call.function.name} to UI handler (id=${call.id})');
          _localToolNotifier?.call(call.id, call.function.name, 'executing');
          try {
            final result = await _uiToolHandler!(call.id, call.function.name, args);
            _localToolNotifier?.call(call.id, call.function.name, 'completed');
            return jsonEncode(result);
          } catch (e) {
            DebugLog.service('AG-UI: UI handler error: $e');
            _localToolNotifier?.call(call.id, call.function.name, 'error: $e');
            return jsonEncode({'error': e.toString()});
          }
        }

        // Execute the tool via LocalToolsService
        DebugLog.service('AG-UI: Calling localToolsService.executeTool...');
        _localToolNotifier?.call(call.id, call.function.name, 'executing');
        final result = await localToolsService.executeTool(
          call.id,
          call.function.name,
          args,
        );
        DebugLog.service('AG-UI: Tool execution returned: success=${result.success}');

        if (result.success) {
          final json = jsonEncode(result.result);
          DebugLog.service('AG-UI: Returning success JSON (${json.length} chars)');
          _localToolNotifier?.call(call.id, call.function.name, 'completed');
          return json;
        } else {
          DebugLog.service('AG-UI: Returning error: ${result.error}');
          _localToolNotifier?.call(call.id, call.function.name, 'error');
          return jsonEncode({'error': result.error});
        }
      }, fireAndForget: isFireAndForget);
    }
  }

  /// Send a user message and get the agent's response.
  ///
  /// Returns a stream of events for the UI to process.
  Stream<ag_ui.BaseEvent> sendMessage(
    String userMessage, {
    LocalToolsService? localToolsService,
  }) async* {
    if (_config == null || _agUiClient == null) {
      throw StateError('AgUiService not configured. Call configure() first.');
    }

    _state = AgUiConnectionState.connecting;
    _lastError = null;
    notifyListeners();

    try {
      // Create thread if needed
      if (_thread == null) {
        final (threadId, runId) = await _createThread();
        _currentRunId = runId;

        _thread = Thread(id: threadId, client: _agUiClient!);

        // Register tools
        if (localToolsService != null) {
          _registerTools(localToolsService);
        }
      } else {
        // Create new run for existing thread
        _currentRunId = await _createRun(_thread!.id);
      }

      _state = AgUiConnectionState.streaming;
      notifyListeners();

      // Add user message
      final userMsg = ag_ui.UserMessage(
        id: 'user-${DateTime.now().millisecondsSinceEpoch}',
        content: userMessage,
      );

      // Generate the endpoint
      final endpoint =
          'rooms/${_config!.roomId}/agui/${_thread!.id}/$_currentRunId';
      DebugLog.service('AG-UI: Starting run at $endpoint');

      // Start the run - Thread handles the event loop
      var toolResults = await _thread!.startRun(
        endpoint: endpoint,
        runId: _currentRunId!,
        messages: [userMsg],
      );

      // Yield events from the thread's stream
      // Note: Events are already being processed by Thread.startRun()
      // We yield from the stepsStream for UI updates
      await for (final event in _thread!.stepsStream) {
        yield event;
      }

      // Handle tool result loop
      while (toolResults.isNotEmpty) {
        DebugLog.service('AG-UI: Processing ${toolResults.length} tool results');

        _currentRunId = await _createRun(_thread!.id);
        final newEndpoint =
            'rooms/${_config!.roomId}/agui/${_thread!.id}/$_currentRunId';

        toolResults = await _thread!.sendToolResults(
          endpoint: newEndpoint,
          runId: _currentRunId!,
          toolMessages: toolResults,
        );
      }

      _state = AgUiConnectionState.connected;
      notifyListeners();
    } catch (e, stackTrace) {
      _state = AgUiConnectionState.error;
      _lastError = e.toString();
      DebugLog.service('AgUiService error: $e\n$stackTrace');
      notifyListeners();
      rethrow;
    }
  }

  /// Simplified message sending that handles tool loop internally.
  ///
  /// This is the main method to use - it handles the full conversation flow
  /// including tool execution and returns events as they occur.
  ///
  /// [uiToolHandler] is called for canvas_render and genui_render tools
  /// which need access to UI state (Riverpod providers).
  ///
  /// [onLocalToolExecution] is called when a local tool starts/completes execution.
  ///
  /// [onToolStateChange] is called when tool call states change (start/end execution).
  ///
  /// [state] is optional application state (e.g., canvas contents) to send with the request.
  /// This state is available to the agent for context-aware responses.
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

    // Store handlers for use in tool executor
    _uiToolHandler = uiToolHandler;
    _localToolNotifier = onLocalToolExecution;
    if (_config == null || _agUiClient == null) {
      _chatLock!.complete();
      _chatLock = null;
      throw StateError('AgUiService not configured. Call configure() first.');
    }

    _state = AgUiConnectionState.connecting;
    _lastError = null;
    notifyListeners();

    try {
      // Create thread if needed
      if (_thread == null) {
        final (threadId, runId) = await _createThread();
        _currentRunId = runId;

        _thread = Thread(id: threadId, client: _agUiClient!);

        // Register tools only once when thread is created
        _registerTools(localToolsService);
      } else {
        // Create new run for existing thread
        _currentRunId = await _createRun(_thread!.id);
      }

      _state = AgUiConnectionState.streaming;
      notifyListeners();

      // Listen to events stream
      StreamSubscription<ag_ui.BaseEvent>? subscription;
      StreamSubscription<ToolCallStateChange>? toolStateSubscription;

      try {
        subscription = _thread!.stepsStream.listen(onEvent);

        // Listen to tool state changes for UI notifications
        if (onToolStateChange != null) {
          toolStateSubscription = _thread!.toolStateChanges.listen(onToolStateChange);
        }

        // Add user message
        final userMsg = ag_ui.UserMessage(
          id: 'user-${DateTime.now().millisecondsSinceEpoch}',
          content: userMessage,
        );

        // Generate the endpoint
        final endpoint =
            'rooms/${_config!.roomId}/agui/${_thread!.id}/$_currentRunId';

        // Start the run with optional state
        var toolResults = await _thread!.startRun(
          endpoint: endpoint,
          runId: _currentRunId!,
          messages: [userMsg],
          state: state,
        );

        // Handle tool result loop
        while (toolResults.isNotEmpty) {
          _currentRunId = await _createRun(_thread!.id);
          final newEndpoint =
              'rooms/${_config!.roomId}/agui/${_thread!.id}/$_currentRunId';

          toolResults = await _thread!.sendToolResults(
            endpoint: newEndpoint,
            runId: _currentRunId!,
            toolMessages: toolResults,
          );
        }

        _state = AgUiConnectionState.connected;
        notifyListeners();
      } finally {
        // Always cancel subscriptions
        await subscription?.cancel();
        await toolStateSubscription?.cancel();
      }
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

  /// Resume an existing thread by ID and load its history.
  ///
  /// Returns the chat messages reconstructed from the thread's event history.
  /// The caller should pass these to ChatNotifier.loadMessages().
  Future<List<ChatMessage>> resumeThread(String threadId) async {
    if (_config == null || _agUiClient == null) {
      throw StateError('AgUiService not configured. Call configure() first.');
    }

    DebugLog.service('AgUiService: Resuming thread $threadId');

    // Dispose old thread if exists
    _thread?.dispose();

    // Create new Thread instance with the existing ID
    _thread = Thread(id: threadId, client: _agUiClient!);
    _currentRunId = null;

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
      final response = await _httpClient.get(
        Uri.parse('${_config!.roomEndpoint}/$threadId'),
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

  /// Reset the conversation (clear thread).
  void resetConversation() {
    _thread?.reset();
    _thread?.dispose();
    _thread = null;
    _currentRunId = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _thread?.dispose();
    _httpClient.close();
    super.dispose();
  }
}

/// Riverpod provider for AgUiService.
final agUiServiceProvider = ChangeNotifierProvider<AgUiService>((ref) {
  return AgUiService();
});

/// Provider for AG-UI configuration.
final agUiConfigProvider = StateProvider<AgUiServiceConfig?>((ref) => null);

/// Combined provider that auto-configures AgUiService when config changes.
final configuredAgUiServiceProvider = Provider<AgUiService>((ref) {
  final service = ref.watch(agUiServiceProvider);

  ref.listen<AgUiServiceConfig?>(agUiConfigProvider, (previous, next) {
    if (next != null &&
        (previous?.roomId != next.roomId ||
            previous?.baseUrl != next.baseUrl)) {
      Future.microtask(() => service.configure(next));
    }
  });

  final config = ref.read(agUiConfigProvider);
  if (config != null && !service.isConfigured) {
    Future.microtask(() => service.configure(config));
  }

  return service;
});
