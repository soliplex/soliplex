import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/connection_events.dart'; // For SessionState, ConnectionInfo

/// Abstract interface for a chat session.
///
/// Implementations handle specific protocols (AG-UI, OpenAI Completions).
abstract class ChatSession {
  /// Stream of message updates.
  Stream<List<ChatMessage>> get messageStream;

  /// Stream of session lifecycle events (e.g. SessionCreated, RunStarted).
  Stream<ConnectionEvent> get events;

  /// Current list of messages.
  List<ChatMessage> get messages;

  /// Whether the session is currently receiving a response.
  bool get isStreaming;

  /// Current state of the session (active, streaming, backgrounded, etc.).
  SessionState get state;

  /// Last activity timestamp for the session.
  DateTime? get lastActivity;

  /// Whether the agent is currently typing or sending messages.
  bool get isAgentTyping;

  /// Get connection info for observer (for diagnostics).
  ConnectionInfo get connectionInfo;

  /// Add a local error message to the history.
  void addErrorMessage(String message);

  /// Toggle the expanded state of a thinking block in a message.
  void toggleThinkingExpanded(String messageId);

  /// Toggle the expanded state of citations in a message.
  void toggleCitationsExpanded(String messageId);

  /// Send a user message.
  ///
  /// state is an optional map of client-side state (e.g. active canvas data)
  /// that should be sent with the message context.
  Future<void> sendMessage(String text, {Map<String, dynamic>? state});

  /// Cancel the current operation.
  Future<void> cancel();

  /// Suspend the session (e.g. backgrounding).
  void suspend();

  /// Resume the session.
  void resume();

  /// Dispose resources.
  void dispose();
}
