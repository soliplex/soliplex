import 'dart:async';

import 'package:soliplex/core/chat/chat_session.dart';
import 'package:soliplex/core/chat/completions_models.dart';
import 'package:soliplex/core/chat/unified_message.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:uuid/uuid.dart';

const _uuid = Uuid();

/// Chat session implementation for OpenAI-compatible completions endpoints.
///
/// Uses NetworkTransportLayer for HTTP/SSE communication,
/// providing observability through NetworkInspector.
class CompletionsChatSession implements ChatSession {
  CompletionsChatSession({
    required NetworkTransportLayer transport,
    required String model,
    required String endpointId,
    String? systemPrompt,
  }) : _transport = transport,
       _model = model,
       _endpointId = endpointId,
       _systemPrompt = systemPrompt {
    // Add system prompt to conversation history if provided
    if (systemPrompt != null && systemPrompt.isNotEmpty) {
      _conversationHistory.add(CompletionMessage.system(systemPrompt));
    }
  }
  final NetworkTransportLayer _transport;
  final String _model;
  final String? _systemPrompt;
  final String _endpointId;

  final StreamController<List<UnifiedMessage>> _messageController =
      StreamController<List<UnifiedMessage>>.broadcast();
  final StreamController<bool> _streamingController =
      StreamController<bool>.broadcast();

  final List<UnifiedMessage> _messages = [];
  final List<CompletionMessage> _conversationHistory = [];
  final CompletionsStreamParser _parser = CompletionsStreamParser();

  bool _isStreaming = false;
  bool _disposed = false;
  StreamSubscription<String>? _currentStream;

  // ===========================================================================
  // ChatSession Implementation
  // ===========================================================================

  @override
  String get sessionId => 'completions:$_endpointId:$_model';

  @override
  List<UnifiedMessage> get messages => List.unmodifiable(_messages);

  @override
  Stream<List<UnifiedMessage>> get messageStream => _messageController.stream;

  @override
  bool get isGenerating => _isStreaming;

  @override
  Future<void> sendMessage(String content) async {
    if (_disposed) {
      throw StateError('Cannot use disposed CompletionsChatSession');
    }
    if (_isStreaming) {
      throw StateError('Cannot send message while streaming');
    }

    // Add user message
    final userMessage = TextMessage(
      id: _uuid.v4(),
      role: MessageRole.user,
      timestamp: DateTime.now(),
      content: content,
    );
    _messages.add(userMessage);
    _conversationHistory.add(CompletionMessage.user(content));
    _notifyMessages();

    // Start streaming response
    _isStreaming = true;
    _streamingController.add(true);

    // Create assistant message placeholder
    final assistantMessageId = _uuid.v4();
    var assistantContent = '';
    final assistantMessage = TextMessage(
      id: assistantMessageId,
      role: MessageRole.assistant,
      timestamp: DateTime.now(),
      content: '',
      isStreaming: true,
      isComplete: false,
    );
    _messages.add(assistantMessage);
    _notifyMessages();

    try {
      // Build request
      final request = CompletionRequest(
        model: _model,
        messages: _conversationHistory,
      );

      // Get the completions endpoint URL
      final uri = Uri.parse('${_transport.baseUrl}/v1/chat/completions');

      // Stream the response
      final sseStream = _transport.streamPost(uri, request.toJsonString());

      await for (final chunk in _parser.parse(sseStream)) {
        if (_disposed) break;

        // Extract content from chunk
        for (final choice in chunk.choices) {
          final delta = choice.delta.content;
          if (delta != null && delta.isNotEmpty) {
            assistantContent += delta;

            // Update the assistant message
            final index = _messages.indexWhere(
              (m) => m.id == assistantMessageId,
            );
            if (index >= 0) {
              _messages[index] = TextMessage(
                id: assistantMessageId,
                role: MessageRole.assistant,
                timestamp: assistantMessage.timestamp,
                content: assistantContent,
                isStreaming: true,
                isComplete: false,
              );
              _notifyMessages();
            }
          }

          // Check for finish
          if (choice.finishReason != null) {
            break;
          }
        }
      }

      // Finalize assistant message
      final index = _messages.indexWhere((m) => m.id == assistantMessageId);
      if (index >= 0) {
        _messages[index] = TextMessage(
          id: assistantMessageId,
          role: MessageRole.assistant,
          timestamp: assistantMessage.timestamp,
          content: assistantContent,
        );
        _notifyMessages();
      }

      // Add to conversation history
      _conversationHistory.add(CompletionMessage.assistant(assistantContent));
    } on Object catch (e) {
      // Update message with error state
      final index = _messages.indexWhere((m) => m.id == assistantMessageId);
      if (index >= 0) {
        _messages[index] = TextMessage(
          id: assistantMessageId,
          role: MessageRole.assistant,
          timestamp: assistantMessage.timestamp,
          content: assistantContent.isEmpty
              ? 'Error: $e'
              : '$assistantContent\n\n[Error: $e]',
        );
        _notifyMessages();
      }
      rethrow;
    } finally {
      _isStreaming = false;
      _streamingController.add(false);
      _currentStream = null;
    }
  }

  @override
  Future<void> cancelGeneration() async {
    if (!_isStreaming) return;

    await _currentStream?.cancel();
    _currentStream = null;
    _isStreaming = false;
    _streamingController.add(false);

    // Mark any streaming messages as complete
    for (var i = 0; i < _messages.length; i++) {
      final msg = _messages[i];
      if (msg.isStreaming) {
        _messages[i] = msg.copyWithStreaming();
      }
    }
    _notifyMessages();
  }

  @override
  Future<void> clearHistory() async {
    _messages.clear();
    _conversationHistory.clear();

    // Re-add system prompt if present
    if (_systemPrompt != null && _systemPrompt.isNotEmpty) {
      _conversationHistory.add(CompletionMessage.system(_systemPrompt));
    }

    _notifyMessages();
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;

    await _currentStream?.cancel();
    _currentStream = null;

    if (!_messageController.isClosed) {
      await _messageController.close();
    }
    if (!_streamingController.isClosed) {
      await _streamingController.close();
    }

    // Note: We don't close _transport as it may be shared
  }

  // ===========================================================================
  // Helpers
  // ===========================================================================

  void _notifyMessages() {
    if (!_messageController.isClosed) {
      _messageController.add(List.unmodifiable(_messages));
    }
  }

  /// Get the current model.
  String get model => _model;

  /// Get the system prompt.
  String? get systemPrompt => _systemPrompt;
}
