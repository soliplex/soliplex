import 'package:flutter/material.dart'; // For ValueKey

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/features/chat/view_models/chat_message_view_model.dart';

class MessageViewModelMapper {
  /// Converts a ChatMessage domain model to a ChatMessageViewModel
  /// for display in the UI.
  ChatMessageViewModel map(ChatMessage message) {
    // Generate a unique key for Flutter's widget tree reconciliation
    final key = ValueKey(message.id);

    // Common properties for all ViewModels
    final id = message.id;
    final user = message.user;
    final createdAt = message.createdAt;
    final isUserMessage = message.user.id == ChatUser.user.id;

    switch (message.type) {
      case MessageType.text:
        return TextMessageViewModel(
          id: id,
          user: user,
          createdAt: createdAt,
          isUserMessage: isUserMessage,
          key: key,
          text: message.text ?? '',
          isStreaming: message.isStreaming,
          thinkingText: message.thinkingText,
          isThinkingStreaming: message.isThinkingStreaming,
          isThinkingExpanded: message.isThinkingExpanded,
        );
      case MessageType.genUi:
        if (message.genUiContent == null) {
          // Fallback to error if content is missing
          return ErrorMessageViewModel(
            id: id,
            user: user,
            createdAt: createdAt,
            isUserMessage: isUserMessage,
            key: key,
            message: 'GenUI content missing',
            errorInfo: message.errorInfo,
          );
        }
        return GenUiViewModel(
          id: id,
          user: user,
          createdAt: createdAt,
          isUserMessage: isUserMessage,
          key: key,
          content: message.genUiContent!,
        );
      case MessageType.error:
        return ErrorMessageViewModel(
          id: id,
          user: user,
          createdAt: createdAt,
          isUserMessage: isUserMessage,
          key: key,
          message: message.errorMessage ?? 'An error occurred',
          errorInfo: message.errorInfo,
        );
      case MessageType.toolCall:
        return ToolCallViewModel(
          id: id,
          user: user,
          createdAt: createdAt,
          isUserMessage: isUserMessage,
          key: key,
          toolCallName: message.toolCallName ?? 'Unknown Tool',
          status: message.toolCallStatus ?? 'unknown',
        );
      case MessageType.toolCallGroup:
        return ToolCallGroupViewModel(
          id: id,
          user: user,
          createdAt: createdAt,
          isUserMessage: isUserMessage,
          key: key,
          toolCalls: message.toolCalls ?? [],
          isExpanded: message.isToolGroupExpanded,
        );
      case MessageType.loading:
        return LoadingMessageViewModel(
          id: id,
          user: user,
          createdAt: createdAt,
          isUserMessage: isUserMessage,
          key: key,
        );
    }
  }
}
