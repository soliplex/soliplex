import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../agui/thread.dart';
import '../models/chat_message.dart';
import '../utils/cancel_token.dart';

/// Callback for canvas updates.
typedef CanvasCallback = void Function(Map<String, dynamic> data);

/// Callback for context updates.
typedef ContextCallback =
    void Function(String type, {String? summary, Map<String, dynamic>? data});

/// Callback for activity updates.
typedef ActivityCallback = void Function(bool isActive);

/// Session state.
enum SessionState { active, streaming, suspended, disposed }

/// Manages a session for a single room.
///
/// This is the authoritative source for chat messages in the room.
class RoomSession {
  RoomSession({
    required this.roomId,
    required this.baseUrl,
    required ag_ui.AgUiClient agUiClient,
  }) : _agUiClient = agUiClient;

  final String roomId;
  final String baseUrl;
  final ag_ui.AgUiClient _agUiClient;

  Thread? _thread;
  String? _activeRunId;
  CancelToken? _cancelToken;
  SessionState _state = SessionState.active;

  // Message state - THE source of truth
  final List<ChatMessage> _messages = [];
  late final StreamController<List<ChatMessage>> _messageController =
      StreamController<List<ChatMessage>>.broadcast(
    onListen: () {
      // Schedule emission to ensure subscriber is ready to receive
      Future.microtask(() {
        if (!_messageController.isClosed) {
          _messageController.add(List.unmodifiable(_messages));
        }
      });
    },
  );

  // Event processing state
  final Map<String, String> _messageIdMap = {}; // aguiId → chatId
  final Map<String, StringBuffer> _textBuffers = {};
  final Map<String, String> _toolCallMessageIds =
      {}; // toolCallId → chatMessageId
  final Map<String, String> _thinkingMessageIds = {};

  // Thinking buffering
  StringBuffer? _pendingThinkingBuffer;
  bool _hasPendingThinking = false;
  bool _pendingThinkingFinalized = false;

  // Deduplication
  final Set<String> _processedToolCalls = {};
  final Set<String> _processedToolNotifications = {};

  // Callbacks
  CanvasCallback? onCanvasUpdate;
  ContextCallback? onContextUpdate;
  ActivityCallback? onActivityUpdate;

  /// Current session state.
  SessionState get state => _state;

  /// Thread ID if initialized.
  String? get threadId => _thread?.id;

  /// Active run ID.
  String? get activeRunId => _activeRunId;

  /// Whether the session is streaming.
  bool get isStreaming => _state == SessionState.streaming;

  /// Stream of messages.
  Stream<List<ChatMessage>> get messageStream => _messageController.stream;

  /// Get current messages (immutable copy).
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  /// Initialize the session with a thread.
  void initializeThread(String threadId) {
    _thread = Thread(id: threadId, client: _agUiClient);
  }

  /// Get or create thread.
  Thread? get thread => _thread;

  void _notifyMessageUpdate() {
    if (!_messageController.isClosed) {
      _messageController.add(List.unmodifiable(_messages));
    }
  }

  /// Add a user message.
  void addUserMessage(String text) {
    _messages.add(ChatMessage.text(user: ChatUser.user, text: text));
    _notifyMessageUpdate();
    onContextUpdate?.call('userMessage', summary: text);
  }

  /// Start a new agent message and return its ID.
  String startAgentMessage() {
    final message = ChatMessage.text(
      user: ChatUser.assistant,
      text: '',
      isStreaming: true,
    );
    _messages.add(message);
    _notifyMessageUpdate();
    return message.id;
  }

  /// Append text to a message.
  void appendToMessage(String messageId, String delta) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      final msg = _messages[index];
      _messages[index] = msg.copyWith(text: (msg.text ?? '') + delta);
      _notifyMessageUpdate();
    }
  }

  /// Finalize a message (stop streaming).
  void finalizeMessage(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(isStreaming: false);
      _notifyMessageUpdate();
    }
  }

  /// Add an error message.
  void addErrorMessage(String message, {String? errorCode}) {
    final errorText = errorCode != null ? '[$errorCode] $message' : message;
    _messages.add(ChatMessage.error(message: errorText));
    _notifyMessageUpdate();
  }

  /// Start thinking for a message.
  void startThinking(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(
        isThinkingStreaming: true,
        thinkingText: '',
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

  /// Finalize thinking.
  void finalizeThinking(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      _messages[index] = _messages[index].copyWith(isThinkingStreaming: false);
      _notifyMessageUpdate();
    }
  }

  /// Add a tool call message.
  String addToolCallMessage(String toolName) {
    final message = ChatMessage.toolCall(
      toolCalls: [ToolCallInfo(id: toolName, name: toolName)],
    );
    _messages.add(message);
    _notifyMessageUpdate();
    return message.id;
  }

  /// Update tool call status.
  void updateToolCallStatus(String messageId, String status) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      final msg = _messages[index];
      if (msg.toolCalls != null && msg.toolCalls!.isNotEmpty) {
        final newStatus = status == 'completed'
            ? ToolCallStatus.completed
            : status.startsWith('error')
            ? ToolCallStatus.failed
            : ToolCallStatus.executing;
        _messages[index] = msg.copyWith(
          toolCalls: [msg.toolCalls!.first.copyWith(status: newStatus)],
        );
        _notifyMessageUpdate();
      }
    }
  }

  /// Process an AG-UI event.
  void processEvent(ag_ui.BaseEvent event) {
    switch (event) {
      case ag_ui.RunStartedEvent():
        _state = SessionState.streaming;
        onActivityUpdate?.call(true);
        _pendingThinkingBuffer = null;
        _hasPendingThinking = false;
        _pendingThinkingFinalized = false;

      case ag_ui.TextMessageStartEvent(messageId: final aguiMsgId):
        final chatMessageId = startAgentMessage();
        _messageIdMap[aguiMsgId] = chatMessageId;
        _textBuffers[aguiMsgId] = StringBuffer();

        // Apply pending thinking
        if (_hasPendingThinking && _pendingThinkingBuffer != null) {
          final thinkingText = _pendingThinkingBuffer.toString();
          if (thinkingText.isNotEmpty) {
            startThinking(chatMessageId);
            appendThinking(chatMessageId, thinkingText);
            if (_pendingThinkingFinalized) {
              finalizeThinking(chatMessageId);
            } else {
              _thinkingMessageIds['current'] = chatMessageId;
            }
          }
          _pendingThinkingBuffer = null;
          _hasPendingThinking = false;
          _pendingThinkingFinalized = false;
        }

      case ag_ui.TextMessageContentEvent(
        messageId: final aguiMsgId,
        delta: final delta,
      ):
        final chatMessageId = _messageIdMap[aguiMsgId];
        if (chatMessageId != null) {
          appendToMessage(chatMessageId, delta);
          _textBuffers[aguiMsgId]?.write(delta);
        }

      case ag_ui.TextMessageEndEvent(messageId: final aguiMsgId):
        final chatMessageId = _messageIdMap[aguiMsgId];
        if (chatMessageId != null) {
          finalizeMessage(chatMessageId);
          _messageIdMap.remove(aguiMsgId);
          _textBuffers.remove(aguiMsgId);
        }

      case ag_ui.ThinkingTextMessageStartEvent():
        ChatMessage? targetMessage;
        for (final m in _messages.reversed) {
          if (m.user == ChatUser.assistant && m.isStreaming) {
            targetMessage = m;
            break;
          }
        }
        if (targetMessage != null) {
          startThinking(targetMessage.id);
          _thinkingMessageIds['current'] = targetMessage.id;
        } else {
          _pendingThinkingBuffer = StringBuffer();
          _hasPendingThinking = true;
        }

      case ag_ui.ThinkingTextMessageContentEvent(delta: final delta):
        final chatMessageId = _thinkingMessageIds['current'];
        if (chatMessageId != null) {
          appendThinking(chatMessageId, delta);
        } else if (_hasPendingThinking) {
          _pendingThinkingBuffer?.write(delta);
        }

      case ag_ui.ThinkingTextMessageEndEvent():
        final chatMessageId = _thinkingMessageIds['current'];
        if (chatMessageId != null) {
          finalizeThinking(chatMessageId);
          _thinkingMessageIds.remove('current');
        } else if (_hasPendingThinking) {
          _pendingThinkingFinalized = true;
        }

      case ag_ui.StateSnapshotEvent(snapshot: final snapshot):
        if (snapshot is Map<String, dynamic>) {
          onContextUpdate?.call('stateSnapshot', data: snapshot);
          onCanvasUpdate?.call(snapshot);
        }

      case ag_ui.StateDeltaEvent(delta: final delta):
        if (delta.isNotEmpty && delta.first is Map<String, dynamic>) {
          onContextUpdate?.call(
            'stateDelta',
            data: delta.first as Map<String, dynamic>,
          );
        }

      case ag_ui.RunFinishedEvent():
        _state = SessionState.active;
        onActivityUpdate?.call(false);

      case ag_ui.RunErrorEvent(message: final msg, code: final code):
        addErrorMessage(msg, errorCode: code);
        _state = SessionState.active;
        onActivityUpdate?.call(false);

      default:
        // Other events forwarded via stepsStream
        break;
    }
  }

  /// Mark a tool call as processed.
  bool markToolCallProcessed(String toolCallId) {
    return _processedToolCalls.add(toolCallId);
  }

  /// Mark a tool notification as processed.
  bool markToolNotificationProcessed(String key) {
    return _processedToolNotifications.add(key);
  }

  /// Handle local tool execution.
  void handleLocalToolExecution(
    String toolCallId,
    String toolName,
    String status,
  ) {
    final trackingKey = '$toolCallId:$status';
    if (!markToolNotificationProcessed(trackingKey)) {
      return;
    }

    onContextUpdate?.call('localToolExecution', summary: '$toolName: $status');

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

  /// Set cancel token for current operation.
  void setCancelToken(CancelToken token) {
    _cancelToken = token;
  }

  /// Cancel the current operation.
  void cancel([String? reason]) {
    _cancelToken?.cancel(reason);
    _cancelToken = null;
  }

  /// Suspend the session.
  void suspend() {
    _state = SessionState.suspended;
  }

  /// Resume the session.
  void resume() {
    if (_state == SessionState.suspended) {
      _state = SessionState.active;
    }
  }

  /// Dispose the session.
  void dispose() {
    _state = SessionState.disposed;
    _thread?.dispose();
    _messageController.close();
    _messages.clear();
    _messageIdMap.clear();
    _textBuffers.clear();
    _toolCallMessageIds.clear();
    _thinkingMessageIds.clear();
    _processedToolCalls.clear();
    _processedToolNotifications.clear();
  }

  @override
  String toString() =>
      'RoomSession(roomId: $roomId, threadId: $threadId, state: $_state)';
}
