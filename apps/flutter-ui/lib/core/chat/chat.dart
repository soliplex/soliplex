/// Unified chat abstraction layer.
///
/// This module provides a protocol-agnostic interface for chat sessions,
/// allowing the UI to work with different backends (AG-UI, Completions)
/// through a common contract.
///
/// Key classes:
/// - ChatSession - Abstract interface for chat sessions
/// - UnifiedMessage - Sealed class representing messages from any protocol
/// - AgUiChatSession - Adapter wrapping RoomSession for AG-UI protocol
/// - CompletionsChatSession - Session for OpenAI-compatible completions APIs
library;

export 'chat_session.dart';
export 'completions_chat_session.dart';
export 'unified_message.dart';
