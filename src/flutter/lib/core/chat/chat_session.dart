import 'dart:async';

import 'package:soliplex/core/chat/unified_message.dart';

/// Abstract base class for a chat session.
///
/// This defines the interface required by the legacy "unified chat" system,
/// primarily used by the CompletionsChatSession and
/// CompletionsSessionManager.
///
/// Note: The primary AG-UI chat system uses a different interface defined
/// in `lib/core/protocol/chat_session.dart`.
abstract class ChatSession {
  /// Unique identifier for this session.
  String get sessionId;

  /// Stream of message updates.
  Stream<List<UnifiedMessage>> get messageStream;

  /// Current list of messages.
  List<UnifiedMessage> get messages;

  /// Whether the session is currently generating a response.
  bool get isGenerating;

  /// Send a user message.
  Future<void> sendMessage(String text);

  /// Cancel the current generation.
  Future<void> cancelGeneration();

  /// Clear the chat history.
  Future<void> clearHistory();

  /// Dispose the session and release resources.
  Future<void> dispose();
}
