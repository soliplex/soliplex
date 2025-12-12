import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat_models.dart';
import '../models/error_types.dart';

/// Chat state containing messages and metadata.
class ChatState {
  final List<ChatMessage> messages;
  final bool isAgentTyping;
  final Set<String> streamingMessageIds; // Track multiple concurrent streams
  final Map<String, String> pendingToolCalls; // toolCallId -> accumulated args

  // Thinking state
  final Map<String, StringBuffer> thinkingBuffers; // messageId -> thinking text
  final Set<String> thinkingMessageIds; // messages currently receiving thinking

  // Tool call grouping state
  final List<ToolCallSummary> pendingToolCallSummaries; // tools to be grouped

  const ChatState({
    this.messages = const [],
    this.isAgentTyping = false,
    this.streamingMessageIds = const {},
    this.pendingToolCalls = const {},
    this.thinkingBuffers = const {},
    this.thinkingMessageIds = const {},
    this.pendingToolCallSummaries = const [],
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isAgentTyping,
    Set<String>? streamingMessageIds,
    Map<String, String>? pendingToolCalls,
    Map<String, StringBuffer>? thinkingBuffers,
    Set<String>? thinkingMessageIds,
    List<ToolCallSummary>? pendingToolCallSummaries,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isAgentTyping: isAgentTyping ?? this.isAgentTyping,
      streamingMessageIds: streamingMessageIds ?? this.streamingMessageIds,
      pendingToolCalls: pendingToolCalls ?? this.pendingToolCalls,
      thinkingBuffers: thinkingBuffers ?? this.thinkingBuffers,
      thinkingMessageIds: thinkingMessageIds ?? this.thinkingMessageIds,
      pendingToolCallSummaries:
          pendingToolCallSummaries ?? this.pendingToolCallSummaries,
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

  // =====================
  // Thinking Methods
  // =====================

  /// Start thinking for a message (initialize buffer, set streaming=true).
  void startThinking(String messageId) {
    final buffers = Map<String, StringBuffer>.from(state.thinkingBuffers);
    buffers[messageId] = StringBuffer();

    final thinkingIds = Set<String>.from(state.thinkingMessageIds)
      ..add(messageId);

    // Update message to show thinking is streaming
    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return m.copyWith(isThinkingStreaming: true, isThinkingExpanded: true);
      }
      return m;
    }).toList();

    state = state.copyWith(
      messages: messages,
      thinkingBuffers: buffers,
      thinkingMessageIds: thinkingIds,
    );
  }

  /// Append thinking content chunk.
  void appendThinking(String messageId, String delta) {
    final buffer = state.thinkingBuffers[messageId];
    if (buffer == null) return;

    buffer.write(delta);

    // Update message with current thinking text
    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return m.copyWith(thinkingText: buffer.toString());
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages);
  }

  /// Finalize thinking (set streaming=false, collapse).
  void finalizeThinking(String messageId) {
    final buffer = state.thinkingBuffers[messageId];
    final finalText = buffer?.toString();

    // Update message
    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return m.copyWith(
          thinkingText: finalText,
          isThinkingStreaming: false,
          isThinkingExpanded: false, // Auto-collapse when done
        );
      }
      return m;
    }).toList();

    // Clean up buffers
    final buffers = Map<String, StringBuffer>.from(state.thinkingBuffers)
      ..remove(messageId);
    final thinkingIds = Set<String>.from(state.thinkingMessageIds)
      ..remove(messageId);

    state = state.copyWith(
      messages: messages,
      thinkingBuffers: buffers,
      thinkingMessageIds: thinkingIds,
    );
  }

  /// Toggle thinking expanded state (user action).
  void toggleThinkingExpanded(String messageId) {
    final messages = state.messages.map((m) {
      if (m.id == messageId && m.thinkingText != null) {
        return m.copyWith(isThinkingExpanded: !m.isThinkingExpanded);
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages);
  }

  // =====================
  // Tool Call Grouping Methods
  // =====================

  /// Add a tool call to the pending group.
  void addToolCallToGroup(String toolCallId, String toolName) {
    final summary = ToolCallSummary(
      toolCallId: toolCallId,
      toolName: toolName,
      status: 'executing',
      startedAt: DateTime.now(),
    );

    state = state.copyWith(
      pendingToolCallSummaries: [...state.pendingToolCallSummaries, summary],
    );
  }

  /// Update status of a tool in the pending group.
  void updateToolCallInGroup(String toolCallId, String status) {
    final summaries = state.pendingToolCallSummaries.map((s) {
      if (s.toolCallId == toolCallId) {
        return s.copyWith(
          status: status,
          completedAt:
              status != 'executing' ? DateTime.now() : s.completedAt,
        );
      }
      return s;
    }).toList();

    state = state.copyWith(pendingToolCallSummaries: summaries);
  }

  /// Finalize tool call group - attach to a message or create summary message.
  /// Call this when the response ends to create the grouped tool message.
  void finalizeToolCallGroup(String? attachToMessageId) {
    if (state.pendingToolCallSummaries.isEmpty) return;

    final toolCalls = List<ToolCallSummary>.from(state.pendingToolCallSummaries);

    if (attachToMessageId != null) {
      // Attach tool calls to existing message
      final messages = state.messages.map((m) {
        if (m.id == attachToMessageId) {
          return m.copyWith(toolCalls: toolCalls);
        }
        return m;
      }).toList();

      state = state.copyWith(
        messages: messages,
        pendingToolCallSummaries: const [],
      );
    } else {
      // Create standalone tool call group message
      final message = ChatMessage.toolCallGroup(
        user: ChatUser.system,
        toolCalls: toolCalls,
      );

      state = state.copyWith(
        messages: [...state.messages, message],
        pendingToolCallSummaries: const [],
      );
    }
  }

  /// Toggle tool group expanded state.
  void toggleToolGroupExpanded(String messageId) {
    final messages = state.messages.map((m) {
      if (m.id == messageId) {
        return m.copyWith(isToolGroupExpanded: !m.isToolGroupExpanded);
      }
      return m;
    }).toList();

    state = state.copyWith(messages: messages);
  }

  /// Clear pending tool call summaries (e.g., on error or cancel).
  void clearPendingToolCalls() {
    state = state.copyWith(pendingToolCallSummaries: const []);
  }

  /// Check if there are any pending tool calls.
  bool get hasPendingToolCalls => state.pendingToolCallSummaries.isNotEmpty;
}

/// Riverpod provider for ChatNotifier.
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier();
});
