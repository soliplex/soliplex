import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../../infrastructure/quick_agui/thread.dart';
import '../../infrastructure/quick_agui/tool_call_state.dart';
import '../models/chat_models.dart';
import '../models/error_types.dart';
import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'cancel_token.dart';
import 'connection_events.dart';
import 'event_processor.dart';
import 'http_transport.dart';
import 'room_event_handler.dart';
import 'network_transport_layer.dart';
import 'server_room_key.dart';

/// Per-room session state container.
///
/// Manages:
/// - Thread lifecycle
/// - Chat messages (THE source of truth)
/// - Event processing (AG-UI events → ChatMessage)
/// - Active run tracking
/// - Cancellation support
class RoomSession {
  final String roomId;
  final String? serverId;
  final String baseUrl;
  final HttpTransport transport;
  final UrlBuilder _urlBuilder;
  final EventProcessor _eventProcessor;

  Thread? _thread;
  String? _activeRunId;
  CancelToken? _cancelToken;
  SessionState _state = SessionState.active;
  Timer? _inactivityTimer;

  /// Inactivity timeout for backgrounded sessions (default: 24 hours).
  final Duration inactivityTimeout;

  /// Callback when session times out due to inactivity.
  void Function()? onInactivityTimeout;

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

  /// Track tool call message IDs for updating status (toolCallId → chatMessageId).
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

  RoomSession({
    required this.roomId,
    this.serverId,
    required this.baseUrl,
    required this.transport,
    this.inactivityTimeout = const Duration(hours: 24),
    this.onInactivityTimeout,
    EventProcessor? eventProcessor,
  }) : _urlBuilder = UrlBuilder(baseUrl),
       _eventProcessor = eventProcessor ?? const EventProcessor();

  // Getters
  String? get threadId => _thread?.id;
  String? get activeRunId => _activeRunId;
  SessionState get state => _state;
  bool get isActive =>
      _state == SessionState.active || _state == SessionState.streaming;
  bool get isStreaming => _state == SessionState.streaming;
  bool get isDisposed => _state == SessionState.disposed;
  DateTime? get lastActivity => _lastActivity;

  /// Composite key for this session (serverId + roomId).
  /// Returns null if serverId is not set.
  ServerRoomKey? get key => serverId != null
      ? ServerRoomKey(serverId: serverId!, roomId: roomId)
      : null;

  /// The authoritative list of messages for this room.
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  /// Set the event handler for canvas, context, and activity updates.
  ///
  /// Use [NoOpRoomEventHandler] to disable event handling, or implement
  /// [RoomEventHandler] to receive events.
  void setEventHandler(RoomEventHandler handler) {
    _eventHandler = handler;
  }

  /// Stream of message updates (UI subscribes to this).
  Stream<List<ChatMessage>> get messageStream => _messageController.stream;

  /// Whether the agent is currently typing (streaming a message).
  bool get isAgentTyping =>
      _messages.any((m) => m.user.id == ChatUser.agent.id && m.isStreaming);

  /// Stream of session events.
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Stream of AG-UI events from the thread.
  Stream<ag_ui.BaseEvent>? get stepsStream => _thread?.stepsStream;

  /// Stream of tool call state changes.
  Stream<ToolCallStateChange>? get toolStateChanges =>
      _thread?.toolStateChanges;

  /// Get connection info for observer.
  ConnectionInfo get connectionInfo => ConnectionInfo(
    serverId: serverId,
    roomId: roomId,
    threadId: _thread?.id,
    activeRunId: _activeRunId,
    state: _state,
    lastActivity: _lastActivity,
  );

  /// Initialize the session by creating a thread.
  ///
  /// Pass [transportLayer] to route SSE through NetworkTransportLayer
  /// for observability via NetworkInspector.
  ///
  /// Pass [agUiClient] for legacy/test usage (SSE not observable).
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

    // Create thread via HTTP
    final response = await transport.post(_urlBuilder.createThread(roomId), {});

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
    _lastActivity = DateTime.now();

    _eventController.add(
      SessionCreatedEvent(
        serverId: serverId,
        roomId: roomId,
        threadId: threadId,
      ),
    );

    DebugLog.network('RoomSession: Created thread $threadId for room $roomId');
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

    _cancelToken = CancelToken();
    _state = SessionState.streaming;
    _lastActivity = DateTime.now();

    // Relative endpoint for AG-UI client (without base URL)
    final endpoint = _urlBuilder.runEndpoint(
      roomId,
      _thread!.id,
      _activeRunId!,
    );

    _eventController.add(
      RunStartedEvent(
        serverId: serverId,
        roomId: roomId,
        threadId: _thread!.id,
        runId: _activeRunId!,
      ),
    );

    try {
      final toolResults = await _thread!.startRun(
        endpoint: endpoint,
        runId: _activeRunId!,
        messages: messages,
        state: state,
      );

      _state = SessionState.active;
      _lastActivity = DateTime.now();

      _eventController.add(
        RunCompletedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: _thread!.id,
          runId: _activeRunId!,
        ),
      );

      return toolResults;
    } catch (e) {
      _state = SessionState.active;

      if (e is CancelledException) {
        _eventController.add(
          RunCancelledEvent(
            serverId: serverId,
            roomId: roomId,
            threadId: _thread!.id,
            runId: _activeRunId!,
            reason: e.reason,
          ),
        );
      } else {
        _eventController.add(
          RunFailedEvent(
            serverId: serverId,
            roomId: roomId,
            threadId: _thread!.id,
            runId: _activeRunId!,
            error: e.toString(),
          ),
        );
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

  /// Suspend the session (backgrounding).
  void suspend() {
    if (_state == SessionState.disposed) return;

    DebugLog.network('RoomSession: Suspending session for room $roomId');
    _state = SessionState.backgrounded;

    if (_thread != null) {
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

  /// Resume the session.
  void resume() {
    if (_state == SessionState.disposed) {
      throw StateError('Cannot resume disposed session');
    }

    DebugLog.network('RoomSession: Resuming session for room $roomId');

    // Cancel inactivity timer when resuming
    _cancelInactivityTimer();

    _state = SessionState.active;
    _lastActivity = DateTime.now();

    if (_thread != null) {
      _eventController.add(
        SessionResumedEvent(
          serverId: serverId,
          roomId: roomId,
          threadId: _thread!.id,
        ),
      );
    }
  }

  // ==========================================================================
  // INACTIVITY TIMER
  // ==========================================================================
  //
  // NOTE: On mobile platforms (Android/iOS), Timer does not fire reliably when
  // the app is suspended by the OS. This timer is for *session* backgrounding
  // (switching between rooms within the active app), not *app* backgrounding.
  //
  // For app lifecycle events:
  // - ConnectionRegistry should check `lastActivity` timestamps on app resume
  // - Use `isExpired()` to determine if a session should be cleaned up
  // ==========================================================================

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
        // Don't auto-dispose here - let the registry handle it
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
    if (!_messageController.isClosed) {
      _messageController.add(List.unmodifiable(_messages));
    }
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
      status: 'executing',
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
  /// Delegates to [EventProcessor] for testable event logic,
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

  /// Apply an [EventProcessingResult] to mutable state.
  void _applyEventResult(EventProcessingResult result) {
    if (!result.hasChanges) return;

    // Apply message mutations
    bool messagesChanged = false;
    for (final mutation in result.messageMutations) {
      switch (mutation) {
        case AddMessage(:final message):
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
        act.isActive,
        eventType: act.eventType,
        toolName: act.toolName,
      );
    }
  }

  /// Handle local tool execution notification.
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

    _eventHandler.onContextUpdate('localToolExecution', summary: '$toolName: $status');

    // Add or update tool call message in chat
    if (status == 'executing') {
      final messageId = addToolCallMessage(toolName);
      _toolCallMessageIds[toolCallId] = messageId;
    } else {
      final messageId = _toolCallMessageIds[toolCallId];
      if (messageId != null) {
        updateToolCallStatus(messageId, status);
        if (status == 'completed' || status.startsWith('error')) {
          _toolCallMessageIds.remove(toolCallId);
        }
      }
    }
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

  /// Dispose the session and release resources.
  void dispose() {
    if (_state == SessionState.disposed) return;

    DebugLog.network('RoomSession: Disposing session for room $roomId');

    _cancelInactivityTimer();
    _cancelToken?.cancel('Session disposed');
    _thread?.dispose();
    _thread = null;
    _state = SessionState.disposed;

    _eventController.add(
      SessionDisposedEvent(
        serverId: serverId,
        roomId: roomId,
        threadId: threadId,
      ),
    );

    _eventController.close();
    _messageController.close();
  }
}
