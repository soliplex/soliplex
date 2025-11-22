import 'dart:async';
import 'package:ag_ui/ag_ui.dart';

/// Extension methods for filtering Message streams based on common UI needs.
///
/// These filters provide convenient ways to extract specific message types
/// without imposing a framework opinion on what's "displayable". Different
/// UIs can choose which filters to use based on their requirements.
extension MessageStreamFilters on Stream<Message> {
  /// Messages suitable for a chat UI (text content from users and assistants)
  Stream<Message> get textMessages => where((msg) =>
      (msg is UserMessage) ||
      (msg is AssistantMessage &&
          msg.content != null &&
          msg.content!.isNotEmpty));

  /// Tool call messages (might need custom UI like approval buttons)
  Stream<Message> get toolCallMessages => where((msg) =>
      msg is AssistantMessage &&
      msg.toolCalls != null &&
      msg.toolCalls!.isNotEmpty);

  /// Tool results (usually not shown in UI)
  Stream<ToolMessage> get toolResults =>
      where((msg) => msg is ToolMessage).cast<ToolMessage>();

  /// User messages only
  Stream<UserMessage> get userMessages =>
      where((msg) => msg is UserMessage).cast<UserMessage>();

  /// Assistant messages only (includes both text and tool calls)
  Stream<AssistantMessage> get assistantMessages =>
      where((msg) => msg is AssistantMessage).cast<AssistantMessage>();

  /// Filter tool calls by specific tool name
  Stream<Message> toolCallsNamed(String toolName) => where((msg) {
        if (msg is! AssistantMessage || msg.toolCalls == null) return false;
        return msg.toolCalls!.any((call) => call.function.name == toolName);
      });

  /// Filter by multiple tool names
  Stream<Message> toolCallsNamedAny(List<String> toolNames) => where((msg) {
        if (msg is! AssistantMessage || msg.toolCalls == null) return false;
        return msg.toolCalls!
            .any((call) => toolNames.contains(call.function.name));
      });
}
