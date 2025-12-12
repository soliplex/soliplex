import 'package:dash_chat_2/dash_chat_2.dart' as dash;
import 'package:flutter/material.dart';

import '../../../core/models/chat_models.dart';
import '../widgets/friendly_error_card.dart';
import '../widgets/genui_message_widget.dart';
import '../widgets/tool_call_summary_widget.dart';

/// Custom message builder for Dash Chat 2.
///
/// Routes messages to appropriate widgets based on type:
/// - Text messages → default text bubble
/// - GenUI messages → GenUiMessageWidget (native widget registry)
/// - Loading messages → loading indicator
/// - Error messages → error display
class MessageBuilder {
  final void Function(String eventName, Map<String, Object?> arguments)?
  onGenUiEvent;
  final void Function(String messageId)? onToggleToolGroup;

  MessageBuilder({this.onGenUiEvent, this.onToggleToolGroup});

  /// Build a custom message widget based on message type.
  Widget? build(
    dash.ChatMessage dashMessage, {
    dash.ChatMessage? previousMessage,
    dash.ChatMessage? nextMessage,
    required bool isAfterDateSeparator,
    required bool isBeforeDateSeparator,
  }) {
    // Extract our custom message from customProperties
    final customProps = dashMessage.customProperties;
    if (customProps == null) return null;

    final chatMessage = customProps['chatMessage'] as ChatMessage?;
    if (chatMessage == null) return null;

    return switch (chatMessage.type) {
      MessageType.text => null, // Use default text bubble
      MessageType.genUi => _buildGenUiMessage(chatMessage),
      MessageType.loading => _buildLoadingMessage(),
      MessageType.error => _buildErrorMessage(chatMessage),
      MessageType.toolCall => _buildToolCallMessage(chatMessage),
      MessageType.toolCallGroup => _buildToolCallGroupMessage(chatMessage),
    };
  }

  Widget _buildGenUiMessage(ChatMessage message) {
    if (message.genUiContent == null) {
      return _buildErrorMessage(
        message.copyWith(errorMessage: 'Missing GenUI content'),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: GenUiMessageWidget(
        content: message.genUiContent!,
        onEvent: onGenUiEvent,
      ),
    );
  }

  Widget _buildLoadingMessage() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(width: 12),
            Text(
              'Agent is thinking...',
              style: TextStyle(
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorMessage(ChatMessage message) {
    // Use friendly error card if we have typed error info
    if (message.errorInfo != null) {
      return FriendlyErrorCard(
        errorInfo: message.errorInfo!,
        fallbackMessage: message.errorMessage,
      );
    }

    // Fallback: create error info from legacy error message
    return FriendlyErrorCard.fromMessage(
      message.errorMessage ?? 'An error occurred',
    );
  }

  /// Build a compact, inline tool call indicator.
  Widget _buildToolCallMessage(ChatMessage message) {
    final toolName = message.toolCallName ?? 'Unknown tool';
    final status = message.toolCallStatus ?? 'executing';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: CompactToolCallIndicator(
        toolName: toolName,
        status: status,
      ),
    );
  }

  /// Build a grouped tool call summary widget.
  Widget _buildToolCallGroupMessage(ChatMessage message) {
    if (message.toolCalls == null || message.toolCalls!.isEmpty) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: ToolCallSummaryWidget(
        toolCalls: message.toolCalls!,
        isExpanded: message.isToolGroupExpanded,
        onToggle: () {
          onToggleToolGroup?.call(message.id);
        },
      ),
    );
  }
}

/// Convert our ChatMessage to Dash Chat's ChatMessage format.
dash.ChatMessage toDashChatMessage(ChatMessage message) {
  // For non-text messages, use placeholder text so messageTextBuilder gets called
  String displayText;
  switch (message.type) {
    case MessageType.text:
      displayText = message.text ?? '';
    case MessageType.genUi:
      displayText = '[Widget]'; // Placeholder - will be replaced by builder
    case MessageType.loading:
      displayText = '[Loading...]';
    case MessageType.error:
      displayText = message.errorMessage ?? '[Error]';
    case MessageType.toolCall:
      displayText = '[Tool: ${message.toolCallName}]';
    case MessageType.toolCallGroup:
      displayText = '[Tools: ${message.toolCalls?.length ?? 0}]';
  }

  return dash.ChatMessage(
    user: dash.ChatUser(
      id: message.user.id,
      firstName: message.user.firstName,
      lastName: message.user.lastName,
      profileImage: message.user.profileImage,
    ),
    text: displayText,
    createdAt: message.createdAt,
    customProperties: {'chatMessage': message, 'type': message.type.name},
  );
}

/// Convert Dash Chat's ChatUser to our ChatUser format.
ChatUser fromDashChatUser(dash.ChatUser dashUser) {
  return ChatUser(
    id: dashUser.id,
    firstName: dashUser.firstName,
    lastName: dashUser.lastName,
    profileImage: dashUser.profileImage,
  );
}
