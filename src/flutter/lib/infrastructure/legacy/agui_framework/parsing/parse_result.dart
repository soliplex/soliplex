import 'package:ag_ui/ag_ui.dart';

/// Result of parsing an AG-UI event.
///
/// Events may produce different types of results: messages for the conversation,
/// state updates, thinking logs, lifecycle events, or nothing (still accumulating chunks).
sealed class ParseResult {}

/// A complete message ready to be added to conversation history
class MessageResult extends ParseResult {
  final Message message;
  MessageResult(this.message);
}

/// A state update (either snapshot or delta applied)
class StateUpdateResult extends ParseResult {
  final Map<String, dynamic> state;
  StateUpdateResult(this.state);
}

/// A thinking chunk for debugging/logging
class ThinkingResult extends ParseResult {
  final String content;
  final DateTime timestamp;
  ThinkingResult(this.content, this.timestamp);
}

/// Run lifecycle event
class LifecycleResult extends ParseResult {
  final RunLifecycle lifecycle;
  LifecycleResult(this.lifecycle);
}

enum RunLifecycle {
  started,
  finished,
  error,
}

/// Event is still accumulating, no result yet
class NoResult extends ParseResult {}
