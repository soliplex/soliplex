import 'dart:async';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/connection_events.dart'; // For SessionState, ConnectionInfo
import 'package:soliplex/core/protocol/chat_session.dart';
import 'package:soliplex/core/protocol/completions_client.dart';
import 'package:soliplex/core/protocol/completions_models.dart';

class CompletionsChatSession implements ChatSession {
  CompletionsChatSession({
    required this.model,
    required CompletionsClient client,
    this.serverId = 'completions',
    this.roomId = 'default',
  }) : _client = client;
  final String model;
  final String serverId;
  final String roomId;
  final CompletionsClient _client;

  final List<ChatMessage> _messages = [];
  final StreamController<List<ChatMessage>> _messageController =
      StreamController<List<ChatMessage>>.broadcast();
  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  bool _isStreaming = false;
  SessionState _sessionState = SessionState.active; // Track session state
  DateTime? _lastActivity = DateTime.now(); // Track activity
  final String _threadId =
      'completions-${DateTime.now().millisecondsSinceEpoch}';
  int _runCounter = 0;

  @override
  bool get isStreaming => _isStreaming;

  @override
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  @override
  Stream<List<ChatMessage>> get messageStream => _messageController.stream;

  @override
  Stream<ConnectionEvent> get events => _eventController.stream;

  @override
  SessionState get state => _sessionState;

  @override
  DateTime? get lastActivity => _lastActivity;

  @override
  bool get isAgentTyping => isStreaming; // Assume agent typing when streaming

  @override
  ConnectionInfo get connectionInfo => ConnectionInfo(
    serverId: serverId,
    roomId: roomId,
    threadId: _threadId,
    state: state,
    lastActivity: lastActivity,
  );

  @override
  void addErrorMessage(String message) {
    _messages.add(
      ChatMessage.error(user: ChatUser.system, errorMessage: message),
    );
    _notifyUpdate();
  }

  @override
  void toggleThinkingExpanded(String messageId) {
    final index = _messages.indexWhere((m) => m.id == messageId);
    if (index >= 0) {
      final msg = _messages[index];
      _messages[index] = msg.copyWith(
        isThinkingExpanded: !msg.isThinkingExpanded,
      );
      _notifyUpdate();
    }
  }

  @override
  Future<void> sendMessage(String text, {Map<String, dynamic>? state}) async {
    // Update activity
    _lastActivity = DateTime.now();

    // Generate unique run ID
    _runCounter++;
    final runId = 'run-$_runCounter-${DateTime.now().millisecondsSinceEpoch}';
    String? errorMessage;

    // 1. Add user message
    final userMsg = ChatMessage.text(user: ChatUser.user, text: text);
    _messages.add(userMsg);
    _notifyUpdate();

    // 2. Prepare request
    final completionMessages = _messages
        .map(_toCompletionMessage)
        .whereType<CompletionMessage>()
        .toList();

    final request = CompletionRequest(
      model: model,
      messages: completionMessages,
    );

    // 3. Start streaming response
    _isStreaming = true;
    _sessionState = SessionState.streaming;

    // Emit RunStartedEvent
    _eventController.add(
      RunStartedEvent(
        serverId: serverId,
        roomId: roomId,
        threadId: _threadId,
        runId: runId,
      ),
    );

    final assistantMsg = ChatMessage.text(
      user: ChatUser.agent,
      text: '',
      isStreaming: true,
    );
    _messages.add(assistantMsg);
    _notifyUpdate();

    final sb = StringBuffer();

    try {
      final stream = _client.streamComplete(request);

      await for (final chunk in stream) {
        if (chunk.choices.isNotEmpty) {
          final content = chunk.choices.first.delta.content;
          if (content != null) {
            sb.write(content);
            // Update last message
            _messages.last = assistantMsg.copyWith(text: sb.toString());
            _notifyUpdate();
          }
        }
      }
    } on Object catch (e) {
      errorMessage = e.toString();
      _messages.add(
        ChatMessage.error(user: ChatUser.system, errorMessage: 'Error: $e'),
      );
    } finally {
      _isStreaming = false;
      _sessionState = SessionState.active;
      // Finalize last message
      if (_messages.isNotEmpty && _messages.last.user.id == ChatUser.agent.id) {
        _messages.last = _messages.last.copyWith(isStreaming: false);
      }
      _notifyUpdate();
      _lastActivity = DateTime.now();

      // Emit completion event
      if (errorMessage != null) {
        _eventController.add(
          RunFailedEvent(
            serverId: serverId,
            roomId: roomId,
            threadId: _threadId,
            runId: runId,
            error: errorMessage,
          ),
        );
      } else {
        _eventController.add(
          RunCompletedEvent(
            serverId: serverId,
            roomId: roomId,
            threadId: _threadId,
            runId: runId,
          ),
        );
      }
    }
  }

  CompletionMessage? _toCompletionMessage(ChatMessage msg) {
    if (msg.user.id == ChatUser.user.id) {
      return CompletionMessage.user(msg.text ?? '');
    } else if (msg.user.id == ChatUser.agent.id) {
      return CompletionMessage.assistant(msg.text ?? '');
    } else if (msg.user.id == ChatUser.system.id) {
      // System messages are usually filtered out for completions API
      return null;
    }
    return null;
  }

  void _notifyUpdate() {
    if (!_messageController.isClosed) {
      _messageController.add(List.unmodifiable(_messages));
    }
  }

  @override
  Future<void> cancel() async {
    // TODO(dev): Implement cancellation (needs CancelToken in client)
  }

  @override
  void suspend() {
    _sessionState = SessionState.backgrounded;
    // No-op for client-side resources
  }

  @override
  void resume() {
    _sessionState = SessionState.active;
    _lastActivity = DateTime.now();
  }

  @override
  void dispose() {
    _messageController.close();
    _eventController.close();
    // The client's lifecycle is managed by the ServerConnectionState.
    _sessionState = SessionState.disposed;
  }
}
