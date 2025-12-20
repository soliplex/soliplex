import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart'; // For Key

import 'package:soliplex/core/models/chat_models.dart'; // For ChatUser, GenUiContent, ToolCallSummary
import 'package:soliplex/core/models/error_types.dart';

/// Base class for all chat message view models.
abstract class ChatMessageViewModel extends Equatable {
  // For Flutter efficient rebuilding

  const ChatMessageViewModel({
    required this.id,
    required this.user,
    required this.createdAt,
    required this.isUserMessage,
    required this.key,
  });
  final String id;
  final ChatUser user;
  final DateTime createdAt;
  final bool isUserMessage;
  final Key key;

  @override
  List<Object?> get props => [id, user, createdAt, isUserMessage, key];
}

/// View model for text messages (user, agent, system).
class TextMessageViewModel extends ChatMessageViewModel {
  const TextMessageViewModel({
    required super.id,
    required super.user,
    required super.createdAt,
    required super.isUserMessage,
    required super.key,
    required this.text,
    this.isStreaming = false,
    this.thinkingText,
    this.isThinkingStreaming = false,
    this.isThinkingExpanded = false,
    this.citations = const [],
    this.isCitationsExpanded = false,
  });
  final String text;
  final bool isStreaming;
  final String? thinkingText;
  final bool isThinkingStreaming;
  final bool isThinkingExpanded;
  final List<Citation> citations;
  final bool isCitationsExpanded;

  @override
  List<Object?> get props => [
    ...super.props,
    text,
    isStreaming,
    thinkingText,
    isThinkingStreaming,
    isThinkingExpanded,
    citations,
    isCitationsExpanded,
  ];
}

/// View model for GenUI messages.
class GenUiViewModel extends ChatMessageViewModel {
  const GenUiViewModel({
    required super.id,
    required super.user,
    required super.createdAt,
    required super.isUserMessage,
    required super.key,
    required this.content,
  });
  final GenUiContent content;

  @override
  List<Object?> get props => [...super.props, content];
}

/// View model for error messages.
class ErrorMessageViewModel extends ChatMessageViewModel {
  const ErrorMessageViewModel({
    required super.id,
    required super.user,
    required super.createdAt,
    required super.isUserMessage,
    required super.key,
    required this.message,
    this.errorInfo,
  });
  final String message;
  final ChatErrorInfo? errorInfo;

  @override
  List<Object?> get props => [...super.props, message, errorInfo];
}

/// View model for tool call messages.
class ToolCallViewModel extends ChatMessageViewModel {
  // executing, completed, error

  const ToolCallViewModel({
    required super.id,
    required super.user,
    required super.createdAt,
    required super.isUserMessage,
    required super.key,
    required this.toolCallName,
    required this.status,
  });
  final String toolCallName;
  final String status;

  @override
  List<Object?> get props => [...super.props, toolCallName, status];
}

/// View model for grouped tool calls.
class ToolCallGroupViewModel extends ChatMessageViewModel {
  const ToolCallGroupViewModel({
    required super.id,
    required super.user,
    required super.createdAt,
    required super.isUserMessage,
    required super.key,
    required this.toolCalls,
    this.isExpanded = false,
  });
  final List<ToolCallSummary> toolCalls;
  final bool isExpanded;

  @override
  List<Object?> get props => [...super.props, toolCalls, isExpanded];
}

/// View model for loading placeholder messages (e.g. typing indicator).
class LoadingMessageViewModel extends ChatMessageViewModel {
  const LoadingMessageViewModel({
    required super.id,
    required super.user,
    required super.createdAt,
    required super.isUserMessage,
    required super.key,
  });
}
