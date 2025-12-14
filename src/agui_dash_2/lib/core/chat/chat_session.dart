import 'unified_message.dart';

/// Definition of a tool available for execution
class ToolDefinition {
  final String name;
  final String description;
  final Map<String, dynamic> inputSchema;

  const ToolDefinition({
    required this.name,
    required this.description,
    required this.inputSchema,
  });
}

/// Update event for rich content (canvas, genui, state)
class RichContentUpdate {
  final String contentType;
  final Map<String, dynamic> data;
  final bool isSnapshot;  // true for full state, false for delta

  const RichContentUpdate({
    required this.contentType,
    required this.data,
    this.isSnapshot = false,
  });
}

/// Abstract interface for chat sessions across different protocols.
///
/// This interface allows the UI to work with any chat backend (AG-UI,
/// completions, etc.) through a common contract. Protocol-specific
/// adapters implement this interface.
abstract class ChatSession {
  /// Unique identifier for this session
  String get sessionId;

  /// Current messages in the session
  List<UnifiedMessage> get messages;

  /// Stream of message list updates (for reactive UI)
  ///
  /// Emits the full message list whenever it changes.
  /// The list includes updates to streaming messages.
  Stream<List<UnifiedMessage>> get messageStream;

  /// Whether the assistant is currently generating a response
  bool get isStreaming;

  /// Stream of streaming status changes
  Stream<bool> get streamingStatusStream;

  /// Send a user message and get assistant response.
  ///
  /// This adds a user message to the conversation and triggers
  /// the assistant to generate a response.
  Future<void> sendMessage(String content);

  /// Cancel ongoing generation.
  ///
  /// If the assistant is currently generating, this stops the generation.
  /// No-op if not currently generating.
  Future<void> cancelGeneration();

  /// Clear conversation history.
  ///
  /// Removes all messages from the session.
  Future<void> clearHistory();

  /// Dispose resources.
  ///
  /// Should be called when the session is no longer needed.
  Future<void> dispose();
}

/// Mixin for sessions that support tool execution (AG-UI)
abstract class ToolCapableSession {
  /// Tools available in this session
  List<ToolDefinition> get availableTools;

  /// Submit a result for a tool call
  Future<void> submitToolResult(String toolCallId, dynamic result);
}

/// Mixin for sessions that support rich content (canvas, genui, state)
abstract class RichContentSession {
  /// Stream of rich content updates
  Stream<RichContentUpdate> get richContentStream;

  /// Get current state for a content type
  Map<String, dynamic>? getState(String contentType);
}

/// Mixin for sessions with multiple conversation threads (AG-UI rooms)
abstract class ThreadedSession {
  /// Current thread ID
  String get currentThreadId;

  /// All available thread IDs
  List<String> get threadIds;

  /// Switch to a different thread
  Future<void> switchThread(String threadId);

  /// Create a new thread
  Future<String> createThread();
}

/// Mixin for sessions that support system prompts
abstract class SystemPromptSession {
  /// Current system prompt
  String? get systemPrompt;

  /// Update the system prompt
  Future<void> setSystemPrompt(String prompt);
}

/// Extension methods for capability checking
extension ChatSessionCapabilities on ChatSession {
  /// Whether this session supports tool execution
  bool get canUsTools => this is ToolCapableSession;

  /// Whether this session supports rich content
  bool get canUseRichContent => this is RichContentSession;

  /// Whether this session has multiple threads
  bool get hasThreads => this is ThreadedSession;

  /// Whether this session supports system prompts
  bool get canUseSystemPrompt => this is SystemPromptSession;

  /// Get tool capability if available
  ToolCapableSession? get toolCapability =>
      this is ToolCapableSession ? this as ToolCapableSession : null;

  /// Get rich content capability if available
  RichContentSession? get richContentCapability =>
      this is RichContentSession ? this as RichContentSession : null;

  /// Get threaded capability if available
  ThreadedSession? get threadedCapability =>
      this is ThreadedSession ? this as ThreadedSession : null;

  /// Get system prompt capability if available
  SystemPromptSession? get systemPromptCapability =>
      this is SystemPromptSession ? this as SystemPromptSession : null;
}
