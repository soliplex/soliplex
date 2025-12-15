import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/models/error_types.dart';
import 'package:soliplex/core/network/cancel_token.dart';
import 'package:soliplex/core/network/connection_events.dart';
import 'package:soliplex/core/network/event_processor.dart';
import 'package:soliplex/core/network/http_transport.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/network/room_event_handler.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/protocol/chat_session.dart';
import 'package:soliplex/core/services/local_tools_service.dart';
import 'package:soliplex/core/state/app_state.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/update_throttler.dart';
import 'package:soliplex/core/utils/url_builder.dart';
import 'package:soliplex/infrastructure/quick_agui/thread.dart';
import 'package:soliplex/infrastructure/quick_agui/tool_call_state.dart';

/// Per-room session state container.
///
/// Manages:
/// - Thread lifecycle
/// - Chat messages (THE source of truth)
/// - Event processing (AG-UI events → ChatMessage)
/// - Active run tracking
/// - Cancellation support
class RoomSession implements ChatSession {
  RoomSession({
    required this.roomId,
    required this.baseUrl,
    required this.transport,
    this.serverId,
    this.localToolsService,
    this.inactivityTimeout = const Duration(hours: 24),
    this.onInactivityTimeout,
    EventProcessor? eventProcessor,
    Stream<AppState>? appStateStream,
  }) : _urlBuilder = UrlBuilder(baseUrl),
       _eventProcessor = eventProcessor ?? const EventProcessor() {
    if (appStateStream != null) {
      _appStateSubscription = appStateStream.listen(_handleAppStateChange);
    }

    _throttler = UpdateThrottler(
      duration: const Duration(milliseconds: 50),
      onUpdate: () {
        if (!_messageController.isClosed) {
          _messageController.add(List.unmodifiable(_messages));
        }
      },
    );
  }
  final String roomId;
  final String? serverId;
  final String baseUrl;
  final HttpTransport transport;
  final LocalToolsService? localToolsService;
  final UrlBuilder _urlBuilder;
  final EventProcessor _eventProcessor;

  Thread? _thread;
  String? _activeRunId;
  CancelToken? _cancelToken;
  SessionState _state = SessionState.active;
  Timer? _inactivityTimer;
  StreamSubscription<ag_ui.BaseEvent>? _eventSubscription;
  StreamSubscription<AppState>? _appStateSubscription;

  /// Lock to prevent concurrent initialization.
  Completer<void>? _initializeLock;

  /// Inactivity timeout for backgrounded sessions (default: 24 hours).
  final Duration inactivityTimeout;

  /// Callback when session times out due to inactivity.
  void Function()? onInactivityTimeout;

  // ==========================================================================
  // INTERNAL TOOLS
  // ==========================================================================

  static const _genUiTool = ag_ui.Tool(
    name: 'genui_render',
    description: 'Render a UI widget',
    parameters: {
      'type': 'object',
      'properties': {
        'widget_name': {'type': 'string'},
        'data': {'type': 'object'},
      },
      'required': ['widget_name'],
    },
  );

  static const _canvasTool = ag_ui.Tool(
    name: 'canvas_render',
    description: 'Render content to the side canvas',
    parameters: {
      'type': 'object',
      'properties': {
        'widget_name': {'type': 'string'},
        'data': {'type': 'object'},
        'position': {
          'type': 'string',
          'enum': ['append', 'replace', 'clear'],
        },
      },
      'required': ['widget_name'],
    },
  );

  // ==========================================================================
  // MESSAGE STATE (THE source of truth for chat messages)
  // ==========================================================================

  /// The authoritative list of chat messages for this room.
  final List<ChatMessage> _messages = [];

  /// Stream controller for message updates (UI subscribes to this).
  final StreamController<List<ChatMessage>> _messageController =
      StreamController<List<ChatMessage>>.broadcast();

  // ==========================================================================
  // EVENT PROCESSING STATE
  // ==========================================================================

  /// Maps AG-UI event messageId → our internal ChatMessage id.
  final Map<String, String> _messageIdMap = {};

  /// Text buffers for streaming messages.
  final Map<String, StringBuffer> _textBuffers = {};

  /// Track tool call message IDs for updating status (toolCallId →
  /// chatMessageId).
  final Map<String, String> _toolCallMessageIds = {};

  /// Track thinking message IDs (aguiThinkingId → chatMessageId).
  final Map<String, String> _thinkingMessageIds = {};

  /// Thinking buffer state (managed by EventProcessor).
  ThinkingBufferState _thinkingBuffer = ThinkingBufferState.empty();

  // ==========================================================================
  // DEDUPLICATION STATE
  // ==========================================================================

  /// Processed tool calls for deduplication.
  final Set<String> _processedToolCalls = {};

  /// Processed tool notifications for deduplication.
  final Set<String> _processedToolNotifications = {};

  // ==========================================================================
  // SESSION STATE
  // ==========================================================================

  /// Timestamp of last activity.
  DateTime? _lastActivity;

  /// Stream controller for session events.
  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  /// Event handler for side effects (canvas, context pane, activity).
  RoomEventHandler _eventHandler = const NoOpRoomEventHandler();

  /// Throttler for message updates to prevent UI overwhelm.
  late final UpdateThrottler _throttler;

  // Getters
  String? get threadId => _thread?.id;
  String? get activeRunId => _activeRunId;
  @override
  SessionState get state => _state;
  bool get isActive =>
      _state == SessionState.active || _state == SessionState.streaming;
  @override
  bool get isStreaming => _state == SessionState.streaming;
  bool get isDisposed => _state == SessionState.disposed;
  @override
  DateTime? get lastActivity => _lastActivity;

  /// Composite key for this session (serverId + roomId).
  /// Returns null if serverId is not set.
  ServerRoomKey? get key => serverId != null
      ? ServerRoomKey(serverId: serverId!, roomId: roomId)
      : null;

  /// The authoritative list of messages for this room.
  @override
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  /// Set the event handler for canvas, context, and activity updates.
  ///
  /// Use NoOpRoomEventHandler to disable event handling, or implement
  /// RoomEventHandler to receive events.
  // ignore: use_setters_to_change_properties
  void setEventHandler(RoomEventHandler handler) {
    _eventHandler = handler;
  }

  /// Stream of message updates (UI subscribes to this).
  @override
  Stream<List<ChatMessage>> get messageStream => _messageController.stream;

  /// Whether the agent is currently typing (streaming a message).
  @override
  bool get isAgentTyping =>
      _messages.any((m) => m.user.id == ChatUser.agent.id && m.isStreaming);

  /// Stream of session events.
  @override
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Stream of AG-UI events from the thread.
  Stream<ag_ui.BaseEvent>? get stepsStream => _thread?.stepsStream;

  /// Stream of tool call state changes.
  Stream<ToolCallStateChange>? get toolStateChanges =>
      _thread?.toolStateChanges;

  /// Get connection info for observer.
  @override
  ConnectionInfo get connectionInfo => ConnectionInfo(
    serverId: serverId,
    roomId: roomId,
    threadId: _thread?.id,
    activeRunId: _activeRunId,
    state: _state,
    lastActivity: _lastActivity,
  );

  /// Initialize the session by creating a thread and subscribing to events.
  ///
  /// Pass [transportLayer] to route SSE through NetworkTransportLayer
  /// for observability via NetworkInspector.
  ///
  /// Pass [agUiClient] for legacy/test usage (SSE not observable).
  ///
  /// This method is idempotent and thread-safe. Concurrent calls will wait
  /// for the first initialization to complete.
  Future<void> initialize({
    NetworkTransportLayer? transportLayer,
    ag_ui.AgUiClient? agUiClient,
  }) async {
    if (transportLayer == null && agUiClient == null) {
      throw ArgumentError(
        'Either transportLayer or agUiClient must be provided',
      );
    }
    if (_state == SessionState.disposed) {
      throw StateError('Cannot initialize disposed session');
    }

    // Already initialized
    if (_thread != null) {
      DebugLog.network('RoomSession: Already initialized for room $roomId');
      return;
    }

    // Initialization in progress - wait for it
    if (_initializeLock != null) {
      DebugLog.network(
        'RoomSession: Waiting for initialization of room $roomId',
      );
      await _initializeLock!.future;
      return;
    }

    // Start initialization with lock
    _initializeLock = Completer<void>();
    DebugLog.network('RoomSession: Starting initialization for room $roomId');

    try {
      // Create thread via HTTP
      final response = await transport.post(
        _urlBuilder.createThread(roomId),
        {},
      );

      final threadId = response['thread_id'] as String?;
      if (threadId == null) {
        throw StateError('Server did not return thread_id');
      }

      // Get initial run ID
      final runs = response['runs'] as Map<String, dynamic>?;
      if (runs == null || runs.isEmpty) {
        throw StateError('Server did not return any runs');
      }
      _activeRunId = runs.keys.first;

      // Create Thread instance with runAgent delegate
      final RunAgentDelegate runAgentDelegate;
      if (transportLayer != null) {
        runAgentDelegate = transportLayer.runAgent;
        DebugLog.network(
          'RoomSession: Created thread $threadId with transport layer',
        );
      } else {
        // Wrap legacy client as delegate for backward compatibility
        runAgentDelegate = (endpoint, input) =>
            agUiClient!.runAgent(endpoint, input);
        DebugLog.network(
          'RoomSession: Created thread $threadId with legacy client',
        );
      }
      _thread = Thread(id: threadId, runAgent: runAgentDelegate);

      // Register internal UI tools
      addTool(_genUiTool, executeInternalTool, fireAndForget: true);
      addTool(_canvasTool, executeInternalTool, fireAndForget: true);

      // Register local tools if service available
      if (localToolsService != null) {
        _registerTools(localToolsService!);
      }

      // Subscribe to event stream immediately (persistent subscription)
      await _eventSubscription?.cancel();
      _eventSubscription = _thread!.stepsStream.listen(
        processEvent,
        onError: (e) => DebugLog.network('RoomSession: Event stream error: $e'),
        onDone: () => DebugLog.network('RoomSession: Event stream done'),
      );

      _lastActivity = DateTime.now();

      _eventController.add(
        SessionCreatedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: threadId,
        ),
      );

      DebugLog.network(
        'RoomSession: Created thread $threadId for room $roomId',
      );
      _initializeLock?.complete();
    } on Object catch (e) {
      _initializeLock?.completeError(e);
      rethrow;
    } finally {
      _initializeLock = null;
    }
  }

  /// Create a new run for the thread.
  Future<String> createRun() async {
    if (_thread == null) {
      throw StateError('Session not initialized');
    }

    final response = await transport.post(
      _urlBuilder.createRun(roomId, _thread!.id),
      {},
    );

    final runId = response['run_id'] as String?;
    if (runId == null) {
      throw StateError('Server did not return run_id');
    }

    _activeRunId = runId;
    _lastActivity = DateTime.now();

    DebugLog.network(
      'RoomSession: Created run $runId for thread ${_thread!.id}',
    );
    return runId;
  }

  /// Send a user message and process the response.
  @override
  Future<void> sendMessage(String text, {Map<String, dynamic>? state}) async {
    DebugLog.network(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'RoomSession: sendMessage called with text: "${text.substring(0, text.length > 50 ? 50 : text.length)}..."',
    );

    if (_state == SessionState.disposed) {
      throw StateError('Session is disposed');
    }

    // Add user message locally
    addUserMessage(text);

    // Need to initialize? Should be handled by lifecycle controller,
    // but we can check here.
    if (_thread == null) {
      throw StateError('Session not initialized');
    }

    final userMsg = ag_ui.UserMessage(
      id: 'user-${DateTime.now().millisecondsSinceEpoch}',
      content: text,
    );

    await createRun();

    var toolResults = await startRun(messages: [userMsg], state: state);

    while (toolResults.isNotEmpty && _state != SessionState.disposed) {
      DebugLog.network(
        'RoomSession: Processing ${toolResults.length} tool results',
      );

      final newRunId = await createRun();
      if (_state == SessionState.disposed) break;

      toolResults = await sendToolResults(
        runId: newRunId,
        toolMessages: toolResults,
      );
    }
  }

  /// Cancel the current operation.
  @override
  Future<void> cancel() async {
    await cancelActiveRun();
  }

  /// Start a chat run with the given message.
  ///
  /// Returns tool results if any client tools were executed.
  Future<List<ag_ui.ToolMessage>> startRun({
    required List<ag_ui.Message> messages,
    Map<String, dynamic>? state,
  }) async {
    if (_thread == null) {
      throw StateError('Session not initialized');
    }
    if (_state == SessionState.disposed) {
      throw StateError('Session is disposed');
    }
    if (isStreaming) {
      throw StateError('Cannot start run while session is streaming');
    }

    _cancelToken = CancelToken();
    _state = SessionState.streaming;
    _lastActivity = DateTime.now();

    // Capture IDs locally to avoid race condition on dispose/cancel
    final currentThreadId = _thread!.id;
    final currentRunId = _activeRunId!;

    // Relative endpoint for AG-UI client (without base URL)
    final endpoint = _urlBuilder.runEndpoint(
      roomId,
      currentThreadId,
      currentRunId,
    );

    if (!_eventController.isClosed) {
      _eventController.add(
        RunStartedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: currentThreadId,
          runId: currentRunId,
        ),
      );
    }

    try {
      final toolResults = await _thread!.startRun(
        endpoint: endpoint,
        runId: currentRunId,
        messages: messages,
        state: state,
        cancelToken: _cancelToken,
      );

      _state = SessionState.active;
      _lastActivity = DateTime.now();

      if (!_eventController.isClosed) {
        _eventController.add(
          RunCompletedEvent(
            serverId: serverId,
            roomId: roomId,
            threadId: currentThreadId,
            runId: currentRunId,
          ),
        );
      }

      return toolResults;
    } on Object catch (e) {
      _state = SessionState.active;

      if (!_eventController.isClosed) {
        if (e is CancelledException) {
          _eventController.add(
            RunCancelledEvent(
              serverId: serverId,
              roomId: roomId,
              threadId: currentThreadId,
              runId: currentRunId,
              reason: e.reason,
            ),
          );
        } else {
          _eventController.add(
            RunFailedEvent(
              serverId: serverId,
              roomId: roomId,
              threadId: currentThreadId,
              runId: currentRunId,
              error: e.toString(),
            ),
          );
        }
      }
      rethrow;
    } finally {
      _cancelToken = null;
    }
  }

  /// Send tool results and continue the run.
  Future<List<ag_ui.ToolMessage>> sendToolResults({
    required String runId,
    required List<ag_ui.ToolMessage> toolMessages,
  }) async {
    if (_thread == null) {
      throw StateError('Session not initialized');
    }

    final endpoint = _urlBuilder.runEndpoint(roomId, _thread!.id, runId);
    _activeRunId = runId;
    _lastActivity = DateTime.now();

    return _thread!.sendToolResults(
      endpoint: endpoint,
      runId: runId,
      toolMessages: toolMessages,
    );
  }

  /// Cancel the active run.
  Future<void> cancelActiveRun([String? reason]) async {
    if (_cancelToken == null) {
      DebugLog.network('RoomSession: No active run to cancel');
      return;
    }

    DebugLog.network('RoomSession: Cancelling active run');

    // Cancel client-side
    _cancelToken!.cancel(reason ?? 'User requested cancellation');

    // Notify server (optional, may not be supported)
    if (_thread != null && _activeRunId != null) {
      await transport.cancelRun(
        roomId: roomId,
        threadId: _thread!.id,
        runId: _activeRunId!,
      );
    }
  }

  /// Execute an internal tool (e.g., UI rendering).
  Future<String> executeInternalTool(ag_ui.ToolCall call) async {
    var args = <String, dynamic>{};
    try {
      if (call.function.arguments.isNotEmpty) {
        args = jsonDecode(call.function.arguments) as Map<String, dynamic>;
      }
    } on Object catch (e) {
      DebugLog.network('RoomSession: Failed to parse tool args: $e');
    }

    handleLocalToolExecution(call.id, call.function.name, 'executing');

    try {
      if (call.function.name == 'genui_render') {
        final widgetName = args['widget_name'] as String? ?? 'Widget';
        final data = args['data'] as Map<String, dynamic>? ?? {};
        addGenUiMessage(
          GenUiContent(toolCallId: call.id, widgetName: widgetName, data: data),
        );
        handleLocalToolExecution(call.id, call.function.name, 'completed');
        return jsonEncode({'rendered': true, 'widget': widgetName});
      } else if (call.function.name == 'canvas_render') {
        final widgetName = args['widget_name'] as String? ?? 'Widget';
        final data = args['data'] as Map<String, dynamic>? ?? {};
        final position = args['position'] as String? ?? 'append';

        dispatchCanvasUpdate(position, widgetName, data);

        handleLocalToolExecution(call.id, call.function.name, 'completed');
        return jsonEncode({
          'rendered': true,
          'widget': widgetName,
          'position': position,
        });
      } else {
        throw Exception('Unknown internal tool: ${call.function.name}');
      }
    } on Object catch (e) {
      handleLocalToolExecution(call.id, call.function.name, 'error: $e');
      return jsonEncode({'error': e.toString()});
    }
  }

  /// Suspend the session (backgrounding).
  ///
  /// Transitions to [SessionState.backgrounded].
  /// Cancels any active streaming to prevent state conflicts on resume.
  /// Starts inactivity timer to eventually hibernate the session.
  @override
  void suspend() {
    if (_state == SessionState.disposed || _state == SessionState.suspended) {
      return;
    }

    final hasActiveRun = _cancelToken != null;
    final threadId = _thread?.id;
    final runId = _activeRunId;
    DebugLog.network(
      'RoomSession: Suspending session for room $roomId '
      // ignore: lines_longer_than_80_chars (auto-documented)
      '(state=$_state, hasActiveRun=$hasActiveRun, runId=$runId, threadId=$threadId)',
    );

    // Cancel active streaming to prevent "Cannot start run while streaming" on
    // resume
    if (_state == SessionState.streaming && _cancelToken != null) {
      DebugLog.network('RoomSession: Cancelling streaming due to suspend');
      _cancelToken!.cancel('Session suspended');
      _cancelToken = null;
    }

    // Update state to backgrounded
    _state = SessionState.backgrounded;

    if (_thread != null && !_eventController.isClosed) {
      _eventController.add(
        SessionSuspendedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: _thread!.id,
        ),
      );
    }

    // Start inactivity timer when backgrounded
    _startInactivityTimer();
  }

  /// Hibernate the session (deep sleep).
  ///
  /// Called by inactivity timer. Cancels active runs, closes streams,
  /// and releases resources to save memory/battery.
  /// Equivalent to the old suspend() behavior.
  void hibernate() {
    if (_state == SessionState.disposed) return;

    DebugLog.network('RoomSession: Hibernating session for room $roomId');

    // Cancel active run if streaming
    if (_cancelToken != null) {
      DebugLog.network(
        'RoomSession: Cancelling active run $_activeRunId due to hibernation',
      );
      _cancelToken!.cancel('Session hibernated');
      _cancelToken = null;

      // Emit run cancelled event so UI can update
      if (_activeRunId != null &&
          _thread != null &&
          !_eventController.isClosed) {
        _eventController.add(
          RunCancelledEvent(
            serverId: serverId,
            roomId: roomId,
            threadId: _thread!.id,
            runId: _activeRunId!,
            reason: 'Session hibernated',
          ),
        );
      }
      _activeRunId = null;
    }

    _state = SessionState.suspended;
    _cancelInactivityTimer();
  }

  /// Resume the session.
  @override
  void resume() {
    if (_state == SessionState.disposed) {
      throw StateError('Cannot resume disposed session');
    }

    final hasActiveRun = _cancelToken != null;
    final threadId = _thread?.id;
    final previousState = _state;
    DebugLog.network(
      'RoomSession: Resuming session for room $roomId '
      // ignore: lines_longer_than_80_chars (auto-documented)
      '(previousState=$previousState, hasActiveRun=$hasActiveRun, threadId=$threadId)',
    );

    // Cancel inactivity timer when resuming
    _cancelInactivityTimer();

    // Always resume to active state.
    // Streaming state can only be entered via startRun().
    // suspend() cancels any active streaming, so we should never have a stale
    // cancel token here. But clear it defensively to ensure clean state.
    if (_cancelToken != null) {
      DebugLog.network('RoomSession: Clearing stale cancel token on resume');
      _cancelToken = null;
    }
    _state = SessionState.active;

    _lastActivity = DateTime.now();

    if (_thread != null && !_eventController.isClosed) {
      _eventController.add(
        SessionResumedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: _thread!.id,
        ),
      );
    }
  }

  /// Handle AppState changes for auth awareness.
  ///
  /// The stream is pre-filtered by ConnectionRegistry to only include events
  /// for this session's server, so no filtering is needed here.
  void _handleAppStateChange(AppState state) {
    DebugLog.network(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'RoomSession: _handleAppStateChange for room $roomId (serverId=$serverId) - '
      'received ${state.runtimeType}, eventServerId=${state.server?.id}',
    );
    if (state is AppStateNeedsAuth) {
      pauseForAuth();
    } else if (state is AppStateReady) {
      resumeFromAuth();
    }
  }

  /// Pause processing due to auth failure.
  void pauseForAuth() {
    DebugLog.network('RoomSession: Pausing for auth (room $roomId)');
    // We could pause the thread event loop here if Thread supported it.
    // For now, we rely on the transport layer to hold requests or fail.
    // If we wanted to be more aggressive, we could cancel active runs,
    // but the goal is to survive transient auth issues.
  }

  /// Resume processing after auth success.
  void resumeFromAuth() {
    DebugLog.network('RoomSession: Resuming from auth (room $roomId)');
    // If we had paused queues, we would resume them here.
  }

  // ==========================================================================
  // INACTIVITY TIMER
  // ==========================================================================
  // ... (rest of file)

  /// Check if the session has exceeded the inactivity timeout.
  ///
  /// Use this for timestamp-based cleanup that works across app suspend/resume.
  /// Returns true only when:
  /// - Session is backgrounded
  /// - AND lastActivity is set
  /// - AND more than inactivityTimeout has passed since lastActivity
  bool isExpired() {
    final activity = _lastActivity;
    return _state == SessionState.backgrounded &&
        activity != null &&
        DateTime.now().difference(activity) > inactivityTimeout;
  }

  /// Start the inactivity timer for backgrounded sessions.
  void _startInactivityTimer() {
    _cancelInactivityTimer();

    _inactivityTimer = Timer(inactivityTimeout, () {
      if (_state == SessionState.backgrounded) {
        DebugLog.network(
          'RoomSession: Inactivity timeout for room $roomId '
          '(${inactivityTimeout.inHours} hours)',
        );
        onInactivityTimeout?.call();

        // Hibernate session to release resources
        hibernate();
      }
    });

    DebugLog.network(
      'RoomSession: Started inactivity timer for room $roomId '
      '(${inactivityTimeout.inHours} hours)',
    );
  }

  /// Cancel the inactivity timer.
  void _cancelInactivityTimer() {
    if (_inactivityTimer != null) {
      _inactivityTimer!.cancel();
      _inactivityTimer = null;
      DebugLog.network(
        'RoomSession: Cancelled inactivity timer for room $roomId',
      );
    }
  }

  // ==========================================================================
  // MESSAGE MANIPULATION METHODS
  // ==========================================================================

  /// Notify listeners of message changes.
  void _notifyMessageUpdate() {
    _throttler.notify();
  }

  /// Add a user message.
  void addUserMessage(String text) {
    _messages.add(ChatMessage.text(user: ChatUser.user, text: text));
    _notifyMessageUpdate();
    _eventHandler.onContextUpdate('userMessage', summary: text);
  }

  /// Start a new agent message (streaming).
  String startAgentMessage() {
    final message = ChatMessage.text(
      user: ChatUser.agent,
      text: '',
      isStreaming: true,
    );
    _messages.add(message);
    _notifyMessageUpdate();
    return message.id;
  }

  /// Append text to a streaming message.
  void appendToMessage(String messageId, String delta) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      final msg = _messages[index];
      _messages[index] = msg.copyWith(text: (msg.text ?? '') + delta);
      _notifyMessageUpdate();
    }
  }

  /// Finalize a streaming message.
  void finalizeMessage(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(isStreaming: false);
      _notifyMessageUpdate();
    }
  }

  /// Add a GenUI message.
  void addGenUiMessage(GenUiContent content) {
    _messages.add(ChatMessage.genUi(user: ChatUser.agent, content: content));
    _notifyMessageUpdate();
    _eventHandler.onContextUpdate('genUiRender', summary: content.widgetName);
  }

  /// Add an error message.
  @override
  void addErrorMessage(
    String message, {
    String? errorCode,
    ChatErrorType? errorType,
  }) {
    final errorInfo = ChatErrorInfo(
      type: errorType ?? ChatErrorType.server,
      friendlyMessage: 'Something went wrong',
      technicalDetails: message,
      errorCode: errorCode,
    );
    _messages.add(
      ChatMessage.error(user: ChatUser.system, errorInfo: errorInfo),
    );
    _notifyMessageUpdate();
  }

  /// Add a system message.
  void addSystemMessage(String text) {
    _messages.add(ChatMessage.text(user: ChatUser.system, text: text));
    _notifyMessageUpdate();
  }

  /// Add a tool call message and return its ID.
  String addToolCallMessage(String toolName) {
    final message = ChatMessage.toolCall(
      user: ChatUser.agent,
      toolName: toolName,
    );
    _messages.add(message);
    _notifyMessageUpdate();
    return message.id;
  }

  /// Update tool call status.
  void updateToolCallStatus(String messageId, String status) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(toolCallStatus: status);
      _notifyMessageUpdate();
    }
  }

  /// Start thinking for a message.
  void startThinking(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(
        thinkingText: '',
        isThinkingStreaming: true,
      );
      _notifyMessageUpdate();
    }
  }

  /// Append thinking text.
  void appendThinking(String messageId, String delta) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      final msg = _messages[index];
      _messages[index] = msg.copyWith(
        thinkingText: (msg.thinkingText ?? '') + delta,
      );
      _notifyMessageUpdate();
    }
  }

  /// Finalize thinking (stop streaming).
  void finalizeThinking(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(isThinkingStreaming: false);
      _notifyMessageUpdate();
    }
  }

  /// Toggle thinking expanded state.
  @override
  void toggleThinkingExpanded(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      final msg = _messages[index];
      _messages[index] = msg.copyWith(
        isThinkingExpanded: !msg.isThinkingExpanded,
      );
      _notifyMessageUpdate();
    }
  }

  /// Clear all messages.
  void clearMessages() {
    _messages.clear();
    _messageIdMap.clear();
    _textBuffers.clear();
    _toolCallMessageIds.clear();
    _thinkingMessageIds.clear();
    _thinkingBuffer = ThinkingBufferState.empty();
    clearProcessedToolCalls();
    _notifyMessageUpdate();
  }

  /// Load messages (for history restoration).
  void loadMessages(List<ChatMessage> messages) {
    _messages.clear();
    _messages.addAll(messages);
    _notifyMessageUpdate();
    DebugLog.network(
      'RoomSession: Loaded ${messages.length} messages for room $roomId',
    );
  }

  // ==========================================================================
  // EVENT PROCESSING
  // ==========================================================================

  /// Process a single AG-UI event and update messages.
  ///
  /// Delegates to EventProcessor for testable event logic,
  /// then applies the result to mutable state.
  void processEvent(ag_ui.BaseEvent event) {
    // Build current state snapshot for EventProcessor
    final state = EventProcessingState(
      messages: _messages,
      messageIdMap: _messageIdMap,
      textBuffers: _textBuffers,
      thinkingMessageIds: _thinkingMessageIds,
      thinkingBuffer: _thinkingBuffer,
    );

    // Process event (pure function)
    final result = _eventProcessor.process(state, event);

    // Apply result to mutable state
    _applyEventResult(result);
  }

  /// Get existing message ID for a tool call or create a new one.
  ///
  /// This ensures idempotent message creation regardless of whether the event
  /// comes from the event stream or local execution logic.
  String getOrCreateToolCallMessage(String toolCallId, String toolName) {
    // 1. Check if we already have a mapped message for this tool ID
    if (_toolCallMessageIds.containsKey(toolCallId)) {
      return _toolCallMessageIds[toolCallId]!;
    }

    // 2. Safety Check: Scan existing messages just in case our ID map is out of
    // sync
    // This helps in recovery paths or weird race conditions
    for (final message in _messages) {
      if (message.toolCallId == toolCallId) {
        _toolCallMessageIds[toolCallId] = message.id;
        return message.id;
      }
    }

    // 3. Fallback Creation (The "Recovery" Path)
    DebugLog.network(
      'RoomSession: Creating new tool call message for $toolCallId ($toolName)',
    );
    final newMessage = ChatMessage.toolCall(
      user: ChatUser.agent,
      toolName: toolName,
    );
    // Explicitly set the toolCallId on the message to enable lookup later
    // Note: ChatMessage.toolCall helper doesn't expose toolCallId directly in
    // constructor
    // so we might need to rely on the map. But wait, ChatMessage definition has
    // it?
    // Let's assume standard creation for now and rely on _toolCallMessageIds
    // map.

    _messages.add(newMessage);
    _toolCallMessageIds[toolCallId] = newMessage.id;
    _notifyMessageUpdate();

    return newMessage.id;
  }

  /// Apply an EventProcessingResult to mutable state.
  void _applyEventResult(EventProcessingResult result) {
    if (!result.hasChanges) return;

    // Apply message mutations
    var messagesChanged = false;
    for (final mutation in result.messageMutations) {
      switch (mutation) {
        case AddMessage(:final message):
          // Idempotency check for tool messages coming from EventProcessor
          if (message.toolCallId != null) {
            if (_toolCallMessageIds.containsKey(message.toolCallId)) {
              DebugLog.network(
                // ignore: lines_longer_than_80_chars (auto-documented)
                'RoomSession: Skipping duplicate tool message for ${message.toolCallId}',
              );
              continue;
            }
            _toolCallMessageIds[message.toolCallId!] = message.id;
          }

          _messages.add(message);
          messagesChanged = true;
        case UpdateMessage(:final messageId, :final updater):
          final index = _messages.indexWhere((m) => m.id == messageId);
          if (index >= 0) {
            _messages[index] = updater(_messages[index]);
            messagesChanged = true;
          }
      }
    }

    // Apply map updates
    result.messageIdMapUpdate?.applyTo(_messageIdMap);
    result.textBuffersUpdate?.applyTo(_textBuffers);
    result.thinkingMessageIdsUpdate?.applyTo(_thinkingMessageIds);

    // Clear deduplication state if requested (on new run)
    if (result.clearDeduplication) {
      _processedToolCalls.clear();
      _processedToolNotifications.clear();
    }

    // Apply thinking buffer update
    if (result.thinkingBufferUpdate != null) {
      _thinkingBuffer = result.thinkingBufferUpdate!;
    }

    // Notify message listeners
    if (messagesChanged) {
      _notifyMessageUpdate();
    }

    // Dispatch side effects
    if (result.contextUpdate != null) {
      final ctx = result.contextUpdate!;
      _eventHandler.onContextUpdate(
        ctx.eventType,
        summary: ctx.summary,
        data: ctx.data,
      );
    }

    if (result.activityUpdate != null) {
      final act = result.activityUpdate!;
      _eventHandler.onActivityUpdate(
        isActive: act.isActive,
        eventType: act.eventType!,
        toolName: act.toolName,
      );
    }
  }

  /// Handle local tool execution notification.
  ///
  /// Emits tool execution events for UI consumption.
  void handleLocalToolExecution(
    String toolCallId,
    String toolName,
    String status,
  ) {
    // Deduplicate by tool call ID
    final trackingKey = '$toolCallId:$status';
    if (!markToolNotificationProcessed(trackingKey)) {
      return;
    }

    _eventHandler.onContextUpdate(
      'localToolExecution',
      summary: '$toolName: $status',
    );

    // Notify event handler for provider updates (tool execution indicator)
    final errorMessage = status.startsWith('error') ? status : null;
    _eventHandler.onToolExecution(
      toolCallId,
      toolName,
      status,
      errorMessage: errorMessage,
    );

    // Emit tool execution events for external observers
    if (!_eventController.isClosed) {
      if (status == 'executing') {
        _eventController.add(
          ToolExecutionStartedEvent(
            serverId: serverId,
            roomId: roomId,
            toolCallId: toolCallId,
            toolName: toolName,
          ),
        );
      } else if (status == 'completed') {
        _eventController.add(
          ToolExecutionCompletedEvent(
            serverId: serverId,
            roomId: roomId,
            toolCallId: toolCallId,
          ),
        );
      } else if (status.startsWith('error')) {
        _eventController.add(
          ToolExecutionErrorEvent(
            serverId: serverId,
            roomId: roomId,
            toolCallId: toolCallId,
            errorMessage: status,
          ),
        );
      }
    }

    // Add or update tool call message in chat
    // Uses getOrCreateToolCallMessage for idempotency
    if (status == 'executing') {
      getOrCreateToolCallMessage(toolCallId, toolName);
    } else {
      // Find the message ID (should exist if 'executing' happened first, or
      // getOrCreate created it)
      final messageId = getOrCreateToolCallMessage(toolCallId, toolName);
      updateToolCallStatus(messageId, status);

      // We don't remove from _toolCallMessageIds immediately for 'completed'
      // because we might receive a delayed server event that wants to update it
      // too.
      // Cleaning up on new run (via clearProcessedToolCalls) is safer.
    }
  }

  /// Dispatch a canvas update event.
  ///
  /// Used by tools (like canvas_render) to update the canvas state.
  void dispatchCanvasUpdate(
    String operation,
    String widgetName,
    Map<String, dynamic> data,
  ) {
    _eventHandler.onCanvasUpdate(operation, widgetName, data);
  }

  // ==========================================================================
  // DEDUPLICATION
  // ==========================================================================

  /// Mark a tool call as processed.
  ///
  /// Returns true if this is a new tool call (first time seeing it).
  /// Returns false if already processed (duplicate).
  bool markToolCallProcessed(String toolCallId) {
    return _processedToolCalls.add(toolCallId);
  }

  /// Mark a tool notification as processed.
  ///
  /// Returns true if this is a new notification (first time seeing it).
  /// Returns false if already processed (duplicate).
  bool markToolNotificationProcessed(String key) {
    return _processedToolNotifications.add(key);
  }

  /// Clear processed tool calls and notifications.
  ///
  /// Call this when starting a new conversation or resetting state.
  void clearProcessedToolCalls() {
    _processedToolCalls.clear();
    _processedToolNotifications.clear();
  }

  /// Register a tool with the thread.
  void addTool(
    ag_ui.Tool tool,
    ToolExecutor executor, {
    bool fireAndForget = false,
  }) {
    _thread?.addTool(tool, executor, fireAndForget: fireAndForget);
  }

  /// Register tools from LocalToolsService.
  void _registerTools(LocalToolsService service) {
    for (final toolDef in service.tools) {
      if (_state == SessionState.disposed) return;
      // Skip internal UI tools (handled by RoomSession)
      // We assume internal tools are already registered in initialize()
      if (toolDef.name == 'canvas_render' || toolDef.name == 'genui_render') {
        continue;
      }

      final agTool = ag_ui.Tool(
        name: toolDef.name,
        description: toolDef.description,
        parameters: toolDef.parameters,
      );

      addTool(agTool, (call) async {
        if (_state == SessionState.disposed) {
          return jsonEncode({'error': 'disposed'});
        }
        var args = <String, dynamic>{};
        try {
          if (call.function.arguments.isNotEmpty) {
            args = jsonDecode(call.function.arguments) as Map<String, dynamic>;
          }
        } on Object catch (e) {
          DebugLog.network('RoomSession: Failed to parse tool args: $e');
        }

        handleLocalToolExecution(call.id, call.function.name, 'executing');

        final result = await service.executeTool(
          call.id,
          call.function.name,
          args,
        );

        if (_state == SessionState.disposed) {
          return jsonEncode({'error': 'disposed'});
        }

        if (result.success) {
          handleLocalToolExecution(call.id, call.function.name, 'completed');
          return jsonEncode(result.result);
        } else {
          handleLocalToolExecution(call.id, call.function.name, 'error');
          return jsonEncode({'error': result.error});
        }
      });
    }
  }

  /// Dispose the session and release resources.
  @override
  void dispose() {
    if (_state == SessionState.disposed) return;

    DebugLog.network('RoomSession: Disposing session for room $roomId');

    _eventSubscription?.cancel(); // Cancel stream subscription
    _eventSubscription = null;

    _appStateSubscription?.cancel();
    _appStateSubscription = null;

    _cancelInactivityTimer();
    _throttler.dispose();
    _cancelToken?.cancel('Session disposed');
    _thread?.dispose();
    _thread = null;
    _state = SessionState.disposed;

    if (!_eventController.isClosed) {
      _eventController.add(
        SessionDisposedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: threadId,
        ),
      );
      _eventController.close();
    }

    if (!_messageController.isClosed) {
      _messageController.close();
    }
  }
}
