import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat_models.dart';
import '../models/error_types.dart';

/// Chat state containing messages and metadata.
class ChatState {
  final List<ChatMessage> messages;
  final bool isAgentTyping;
  final Set<String> streamingMessageIds; // Track multiple concurrent streams
  final Map<String, String> pendingToolCalls; // toolCallId -> accumulated args

  const ChatState({
    this.messages = const [],
    this.isAgentTyping = false,
    this.streamingMessageIds = const {},
    this.pendingToolCalls = const {},
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isAgentTyping,
    Set<String>? streamingMessageIds,
    Map<String, String>? pendingToolCalls,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isAgentTyping: isAgentTyping ?? this.isAgentTyping,
      streamingMessageIds: streamingMessageIds ?? this.streamingMessageIds,
      pendingToolCalls: pendingToolCalls ?? this.pendingToolCalls,
    );
  }
}

/// StateNotifier for managing chat state.
class ChatNotifier extends StateNotifier<ChatState> {
  ChatNotifier() : super(const ChatState());

  /// Add a user message.
  void addUserMessage(String text) {
    final message = ChatMessage.text(user: ChatUser.user, text: text);
    state = state.copyWith(messages: [...state.messages, message]);
  }

  /// Start a new agent text message (for streaming).
  String startAgentMessage() {
    final message = ChatMessage.text(
      user: ChatUser.agent,
      text: '',
      isStreaming: true,
    );
    state = state.copyWith(
      messages: [...state.messages, message],
      isAgentTyping: true,
      streamingMessageIds: {...state.streamingMessageIds, message.id},
    );
    return message.id;
  }

  /// Append text to a specific streaming message by ID.
  void appendToStreamingMessage(String messageId, String delta) {
    if (!state.streamingMessageIds.contains(messageId)) return;

    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return m.copyWith(text: (m.text ?? '') + delta);
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages);
  }

  /// Finalize a specific streaming message by ID.
  void finalizeStreamingMessage(String messageId) {
    if (!state.streamingMessageIds.contains(messageId)) return;

    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return m.copyWith(isStreaming: false);
      }
      return m;
    }).toList();

    final newStreamingIds = Set<String>.from(state.streamingMessageIds)
      ..remove(messageId);

    state = state.copyWith(
      messages: messages,
      isAgentTyping: newStreamingIds.isNotEmpty,
      streamingMessageIds: newStreamingIds,
    );
  }

  /// Add a loading placeholder for incoming GenUI.
  String addLoadingPlaceholder() {
    final message = ChatMessage.loading(user: ChatUser.agent);
    state = state.copyWith(
      messages: [...state.messages, message],
      isAgentTyping: true,
    );
    return message.id;
  }

  /// Start buffering a tool call (GenUI payload).
  void startToolCall(String toolCallId) {
    state = state.copyWith(
      pendingToolCalls: {...state.pendingToolCalls, toolCallId: ''},
    );
  }

  /// Append args chunk to a pending tool call.
  void appendToolCallArgs(String toolCallId, String chunk) {
    final pending = Map<String, String>.from(state.pendingToolCalls);
    pending[toolCallId] = (pending[toolCallId] ?? '') + chunk;
    state = state.copyWith(pendingToolCalls: pending);
  }

  /// Get the accumulated args for a tool call.
  String? getToolCallArgs(String toolCallId) {
    return state.pendingToolCalls[toolCallId];
  }

  /// Replace a loading placeholder with a GenUI message.
  void replaceWithGenUi(String messageId, GenUiContent content) {
    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return ChatMessage.genUi(
          id: messageId,
          user: ChatUser.agent,
          content: content,
          createdAt: m.createdAt,
        );
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages, isAgentTyping: false);
  }

  /// Replace a loading placeholder with an error.
  void replaceWithError(String messageId, String errorMessage) {
    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return ChatMessage.error(
          id: messageId,
          user: ChatUser.agent,
          errorMessage: errorMessage,
          createdAt: m.createdAt,
        );
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages, isAgentTyping: false);
  }

  /// Add a complete GenUI message (not from placeholder).
  void addGenUiMessage(GenUiContent content) {
    final message = ChatMessage.genUi(user: ChatUser.agent, content: content);
    state = state.copyWith(messages: [...state.messages, message]);
  }

  /// Add an error message with optional typed error info.
  void addErrorMessage(String errorMessage, {ChatErrorInfo? errorInfo}) {
    final message = ChatMessage.error(
      user: ChatUser.agent,
      errorMessage: errorMessage,
      errorInfo: errorInfo,
    );
    state = state.copyWith(
      messages: [...state.messages, message],
      isAgentTyping: false,
    );
  }

  /// Add a network error (connection issues, timeouts).
  void addNetworkError(String details) {
    addErrorMessage(
      details,
      errorInfo: ChatErrorInfo.network(details: details),
    );
  }

  /// Add a server error (500s, rate limits, etc.).
  void addServerError(String message, {String? errorCode, String? details}) {
    addErrorMessage(
      message,
      errorInfo: ChatErrorInfo.server(
        message: message,
        errorCode: errorCode,
        details: details,
      ),
    );
  }

  /// Add a tool execution error.
  void addToolError(String toolName, String error) {
    addErrorMessage(
      error,
      errorInfo: ChatErrorInfo.tool(toolName: toolName, error: error),
    );
  }

  /// Add a tool call message showing local tool execution.
  /// Returns the message ID for later updates.
  String addToolCallMessage(String toolName, {String status = 'executing'}) {
    final message = ChatMessage.toolCall(
      user: ChatUser.system,
      toolName: toolName,
      status: status,
    );
    state = state.copyWith(messages: [...state.messages, message]);
    return message.id;
  }

  /// Update the status of a tool call message.
  void updateToolCallStatus(String messageId, String status) {
    final messages = state.messages.map((m) {
      if (m.id == messageId && m.type == MessageType.toolCall) {
        return m.copyWith(toolCallStatus: status);
      }
      return m;
    }).toList();
    state = state.copyWith(messages: messages);
  }

  /// Add a system/info message.
  void addSystemMessage(String text) {
    final message = ChatMessage.text(user: ChatUser.system, text: text);
    state = state.copyWith(messages: [...state.messages, message]);
  }

  /// Remove a message by ID.
  void removeMessage(String messageId) {
    final messages = state.messages.where((m) => m.id != messageId).toList();
    final newStreamingIds = Set<String>.from(state.streamingMessageIds)
      ..remove(messageId);
    state = state.copyWith(
      messages: messages,
      isAgentTyping: newStreamingIds.isNotEmpty,
      streamingMessageIds: newStreamingIds,
    );
  }

  /// Update DynamicContent data for a GenUI message.
  void updateGenUiData(String messageId, Map<String, dynamic> newData) {
    final messages = state.messages.map((m) {
      if (m.id == messageId && m.type == MessageType.genUi) {
        return m.copyWith(
          genUiContent: m.genUiContent?.copyWith(data: newData),
        );
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages);
  }

  /// Clear pending tool call.
  void clearToolCall(String toolCallId) {
    final pending = Map<String, String>.from(state.pendingToolCalls);
    pending.remove(toolCallId);
    state = state.copyWith(pendingToolCalls: pending);
  }

  /// Clear all messages.
  void clearMessages() {
    state = const ChatState();
  }

  /// Load messages from thread history.
  ///
  /// This is called when resuming an existing thread to restore
  /// the conversation history to the UI.
  void loadMessages(List<ChatMessage> messages) {
    state = state.copyWith(messages: messages);
  }

  /// Set agent typing state.
  void setAgentTyping(bool isTyping) {
    state = state.copyWith(isAgentTyping: isTyping);
  }
}

/// Riverpod provider for ChatNotifier.
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier();
});
