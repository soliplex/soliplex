import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../models/chat_models.dart' as chat;
import '../network/room_session.dart';
import 'chat_session.dart';
import 'unified_message.dart' as unified;

/// Adapter that wraps [RoomSession] to implement [ChatSession].
///
/// This adapter allows the UI to work with AG-UI sessions through the
/// unified chat interface. It converts [chat.ChatMessage] to [unified.UnifiedMessage]
/// and provides access to AG-UI specific features via capability interfaces.
class AgUiChatSession
    implements ChatSession, ToolCapableSession, RichContentSession, ThreadedSession {
  final RoomSession _roomSession;
  final StreamController<List<unified.UnifiedMessage>> _unifiedMessageController =
      StreamController<List<unified.UnifiedMessage>>.broadcast();
  final StreamController<bool> _streamingStatusController =
      StreamController<bool>.broadcast();
  final StreamController<RichContentUpdate> _richContentController =
      StreamController<RichContentUpdate>.broadcast();

  StreamSubscription<List<chat.ChatMessage>>? _messageSubscription;
  List<unified.UnifiedMessage> _cachedMessages = [];
  bool _lastStreamingStatus = false;

  AgUiChatSession(this._roomSession) {
    // Subscribe to RoomSession messages and convert to UnifiedMessage
    _messageSubscription = _roomSession.messageStream.listen((chatMessages) {
      _cachedMessages = chatMessages.map(_convertMessage).toList();
      _unifiedMessageController.add(_cachedMessages);

      // Update streaming status
      final isNowStreaming = _roomSession.isStreaming;
      if (isNowStreaming != _lastStreamingStatus) {
        _lastStreamingStatus = isNowStreaming;
        _streamingStatusController.add(isNowStreaming);
      }
    });
  }

  // ===========================================================================
  // ChatSession Implementation
  // ===========================================================================

  @override
  String get sessionId => '${_roomSession.serverId ?? 'local'}:${_roomSession.roomId}';

  @override
  List<unified.UnifiedMessage> get messages => _cachedMessages;

  @override
  Stream<List<unified.UnifiedMessage>> get messageStream => _unifiedMessageController.stream;

  @override
  bool get isStreaming => _roomSession.isStreaming;

  @override
  Stream<bool> get streamingStatusStream => _streamingStatusController.stream;

  @override
  Future<void> sendMessage(String content) async {
    // Add user message to RoomSession
    _roomSession.addUserMessage(content);

    // Start the AG-UI run with the message
    final userMsgId = 'user-${DateTime.now().millisecondsSinceEpoch}';
    final messages = [
      ag_ui.UserMessage(id: userMsgId, content: content),
    ];

    await _roomSession.startRun(messages: messages);
  }

  @override
  Future<void> cancelGeneration() async {
    await _roomSession.cancelActiveRun();
  }

  @override
  Future<void> clearHistory() async {
    _roomSession.clearMessages();
  }

  @override
  Future<void> dispose() async {
    await _messageSubscription?.cancel();
    _messageSubscription = null;

    if (!_unifiedMessageController.isClosed) {
      await _unifiedMessageController.close();
    }
    if (!_streamingStatusController.isClosed) {
      await _streamingStatusController.close();
    }
    if (!_richContentController.isClosed) {
      await _richContentController.close();
    }

    // Note: We don't dispose _roomSession here as it may be managed by ConnectionRegistry
  }

  // ===========================================================================
  // ToolCapableSession Implementation
  // ===========================================================================

  @override
  List<ToolDefinition> get availableTools {
    // TODO: Get tools from RoomSession when it exposes them
    return [];
  }

  @override
  Future<void> submitToolResult(String toolCallId, dynamic result) async {
    // Convert result to AG-UI tool message format
    final toolMessage = ag_ui.ToolMessage(
      toolCallId: toolCallId,
      content: result.toString(),
    );

    await _roomSession.sendToolResults(
      runId: _roomSession.activeRunId!,
      toolMessages: [toolMessage],
    );
  }

  // ===========================================================================
  // RichContentSession Implementation
  // ===========================================================================

  @override
  Stream<RichContentUpdate> get richContentStream => _richContentController.stream;

  @override
  Map<String, dynamic>? getState(String contentType) {
    // TODO: Implement state retrieval from canvas/context providers
    return null;
  }

  // ===========================================================================
  // ThreadedSession Implementation
  // ===========================================================================

  @override
  String get currentThreadId => _roomSession.threadId ?? '';

  @override
  List<String> get threadIds {
    // Currently only single thread per room
    final threadId = _roomSession.threadId;
    return threadId != null ? [threadId] : [];
  }

  @override
  Future<void> switchThread(String threadId) async {
    // TODO: Implement thread switching when RoomSession supports it
    throw UnimplementedError('Thread switching not yet supported');
  }

  @override
  Future<String> createThread() async {
    // AG-UI creates threads automatically during initialize
    // This would need to create a new run
    final runId = await _roomSession.createRun();
    return runId;
  }

  // ===========================================================================
  // Message Conversion
  // ===========================================================================

  /// Convert a [chat.ChatMessage] to [unified.UnifiedMessage].
  unified.UnifiedMessage _convertMessage(chat.ChatMessage msg) {
    return switch (msg.type) {
      chat.MessageType.text => _convertTextMessage(msg),
      chat.MessageType.genUi => _convertGenUiMessage(msg),
      chat.MessageType.toolCall => _convertToolCallMessage(msg),
      chat.MessageType.toolCallGroup => _convertToolCallGroupMessage(msg),
      chat.MessageType.error => _convertErrorMessage(msg),
      chat.MessageType.loading => _convertLoadingMessage(msg),
    };
  }

  unified.UnifiedMessage _convertTextMessage(chat.ChatMessage msg) {
    return unified.TextMessage(
      id: msg.id,
      role: _convertUser(msg.user),
      timestamp: msg.createdAt,
      content: msg.text ?? '',
      isComplete: !msg.isStreaming,
      isStreaming: msg.isStreaming,
    );
  }

  unified.UnifiedMessage _convertGenUiMessage(chat.ChatMessage msg) {
    final content = msg.genUiContent!;
    return unified.RichContentMessage(
      id: msg.id,
      role: _convertUser(msg.user),
      timestamp: msg.createdAt,
      contentType: 'genui',
      payload: {
        'toolCallId': content.toolCallId,
        'widgetName': content.widgetName,
        'data': content.data,
      },
    );
  }

  unified.UnifiedMessage _convertToolCallMessage(chat.ChatMessage msg) {
    return unified.ToolCallMessage(
      id: msg.id,
      timestamp: msg.createdAt,
      toolName: msg.toolCallName ?? 'unknown',
      arguments: const {},
      status: _convertToolStatus(msg.toolCallStatus),
    );
  }

  unified.UnifiedMessage _convertToolCallGroupMessage(chat.ChatMessage msg) {
    // For grouped tool calls, convert the first one or create a summary
    final toolCalls = msg.toolCalls ?? [];
    if (toolCalls.isEmpty) {
      return unified.SystemMessage(
        id: msg.id,
        timestamp: msg.createdAt,
        content: 'Tool calls (none)',
      );
    }

    // For simplicity, represent as the first tool call
    // A richer implementation could create a composite message
    final first = toolCalls.first;
    return unified.ToolCallMessage(
      id: msg.id,
      timestamp: msg.createdAt,
      toolName: first.toolName,
      arguments: const {},
      status: _convertToolCallSummaryStatus(first.status),
    );
  }

  unified.UnifiedMessage _convertErrorMessage(chat.ChatMessage msg) {
    return unified.SystemMessage(
      id: msg.id,
      timestamp: msg.createdAt,
      content: msg.errorInfo?.friendlyMessage ?? msg.errorMessage ?? 'An error occurred',
    );
  }

  unified.UnifiedMessage _convertLoadingMessage(chat.ChatMessage msg) {
    return unified.TextMessage(
      id: msg.id,
      role: _convertUser(msg.user),
      timestamp: msg.createdAt,
      content: '',
      isStreaming: true,
    );
  }

  unified.MessageRole _convertUser(chat.ChatUser user) {
    if (user.id == chat.ChatUser.user.id) return unified.MessageRole.user;
    if (user.id == chat.ChatUser.agent.id) return unified.MessageRole.assistant;
    if (user.id == chat.ChatUser.system.id) return unified.MessageRole.system;
    return unified.MessageRole.assistant;
  }

  unified.ToolCallStatus _convertToolStatus(String? status) {
    return switch (status) {
      'executing' => unified.ToolCallStatus.running,
      'completed' => unified.ToolCallStatus.completed,
      'error' => unified.ToolCallStatus.failed,
      _ => unified.ToolCallStatus.pending,
    };
  }

  unified.ToolCallStatus _convertToolCallSummaryStatus(chat.ToolCallStatus status) {
    return switch (status) {
      chat.ToolCallStatus.executing => unified.ToolCallStatus.running,
      chat.ToolCallStatus.completed => unified.ToolCallStatus.completed,
      chat.ToolCallStatus.error => unified.ToolCallStatus.failed,
    };
  }
}
