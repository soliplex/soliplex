import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../../infrastructure/quick_agui/thread.dart';
import '../../infrastructure/quick_agui/tool_call_state.dart';
import '../models/chat_models.dart';
import '../utils/debug_log.dart';
import 'cancel_token.dart';
import 'connection_events.dart';
import 'http_transport.dart';

/// Per-room session state container.
///
/// Manages:
/// - Thread lifecycle
/// - Chat history preservation
/// - Active run tracking
/// - Cancellation support
class RoomSession {
  final String roomId;
  final String baseUrl;
  final HttpTransport transport;

  Thread? _thread;
  String? _activeRunId;
  CancelToken? _cancelToken;
  SessionState _state = SessionState.active;

  /// Preserved chat history for room switching.
  List<ChatMessage> _chatHistory = [];

  /// Timestamp of last activity.
  DateTime? _lastActivity;

  /// Stream controller for session events.
  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  RoomSession({
    required this.roomId,
    required this.baseUrl,
    required this.transport,
  });

  // Getters
  String? get threadId => _thread?.id;
  String? get activeRunId => _activeRunId;
  SessionState get state => _state;
  bool get isActive => _state == SessionState.active || _state == SessionState.streaming;
  bool get isStreaming => _state == SessionState.streaming;
  bool get isDisposed => _state == SessionState.disposed;
  List<ChatMessage> get chatHistory => List.unmodifiable(_chatHistory);
  DateTime? get lastActivity => _lastActivity;

  /// Stream of session events.
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Stream of AG-UI events from the thread.
  Stream<ag_ui.BaseEvent>? get stepsStream => _thread?.stepsStream;

  /// Stream of tool call state changes.
  Stream<ToolCallStateChange>? get toolStateChanges => _thread?.toolStateChanges;

  /// Get connection info for observer.
  ConnectionInfo get connectionInfo => ConnectionInfo(
        roomId: roomId,
        threadId: _thread?.id,
        activeRunId: _activeRunId,
        state: _state,
        lastActivity: _lastActivity,
      );

  /// Initialize the session by creating a thread.
  Future<void> initialize(ag_ui.AgUiClient agUiClient) async {
    if (_state == SessionState.disposed) {
      throw StateError('Cannot initialize disposed session');
    }

    // Create thread via HTTP
    final endpoint = '$baseUrl/rooms/$roomId/agui';
    final response = await transport.post(Uri.parse(endpoint), {});

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

    // Create Thread instance
    _thread = Thread(id: threadId, client: agUiClient);
    _lastActivity = DateTime.now();

    _eventController.add(SessionCreatedEvent(
      roomId: roomId,
      threadId: threadId,
    ));

    DebugLog.network('RoomSession: Created thread $threadId for room $roomId');
  }

  /// Create a new run for the thread.
  Future<String> createRun() async {
    if (_thread == null) {
      throw StateError('Session not initialized');
    }

    final endpoint = '$baseUrl/rooms/$roomId/agui/${_thread!.id}';
    final response = await transport.post(Uri.parse(endpoint), {});

    final runId = response['run_id'] as String?;
    if (runId == null) {
      throw StateError('Server did not return run_id');
    }

    _activeRunId = runId;
    _lastActivity = DateTime.now();

    DebugLog.network('RoomSession: Created run $runId for thread ${_thread!.id}');
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

    final endpoint = 'rooms/$roomId/agui/${_thread!.id}/$_activeRunId';

    _eventController.add(RunStartedEvent(
      roomId: roomId,
      threadId: _thread!.id,
      runId: _activeRunId!,
    ));

    try {
      final toolResults = await _thread!.startRun(
        endpoint: endpoint,
        runId: _activeRunId!,
        messages: messages,
        state: state,
      );

      _state = SessionState.active;
      _lastActivity = DateTime.now();

      _eventController.add(RunCompletedEvent(
        roomId: roomId,
        threadId: _thread!.id,
        runId: _activeRunId!,
      ));

      return toolResults;
    } catch (e) {
      _state = SessionState.active;

      if (e is CancelledException) {
        _eventController.add(RunCancelledEvent(
          roomId: roomId,
          threadId: _thread!.id,
          runId: _activeRunId!,
          reason: e.reason,
        ));
      } else {
        _eventController.add(RunFailedEvent(
          roomId: roomId,
          threadId: _thread!.id,
          runId: _activeRunId!,
          error: e.toString(),
        ));
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

    final endpoint = 'rooms/$roomId/agui/${_thread!.id}/$runId';
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
      _eventController.add(SessionSuspendedEvent(
        roomId: roomId,
        threadId: _thread!.id,
      ));
    }
  }

  /// Resume the session.
  void resume() {
    if (_state == SessionState.disposed) {
      throw StateError('Cannot resume disposed session');
    }

    DebugLog.network('RoomSession: Resuming session for room $roomId');
    _state = SessionState.active;
    _lastActivity = DateTime.now();

    if (_thread != null) {
      _eventController.add(SessionResumedEvent(
        roomId: roomId,
        threadId: _thread!.id,
      ));
    }
  }

  /// Save chat history for preservation.
  void saveChatHistory(List<ChatMessage> messages) {
    _chatHistory = List.from(messages);
    DebugLog.network('RoomSession: Saved ${messages.length} messages for room $roomId');
  }

  /// Clear chat history.
  void clearChatHistory() {
    _chatHistory = [];
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

    _cancelToken?.cancel('Session disposed');
    _thread?.dispose();
    _thread = null;
    _state = SessionState.disposed;

    _eventController.add(SessionDisposedEvent(
      roomId: roomId,
      threadId: threadId,
    ));

    _eventController.close();
  }
}
